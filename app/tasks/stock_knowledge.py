"""
Stock Knowledge Task

Builds and maintains an evolving per-ticker analytical memory that survives
article deletion. Runs nightly (4 AM UTC) after the 3 AM cleanup window.

For each tracked ticker:
  - Extracts structured key_events from recent articles
  - Updates weekly sentiment_trend
  - Optionally regenerates an LLM narrative if a provider is configured
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from celery import shared_task
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.article import Article
from app.models.stock import Stock
from app.models.stock_knowledge import StockKnowledge

# Maximum items kept per ticker to bound storage
_MAX_KEY_EVENTS = 50
_MAX_WEEKLY_BUCKETS = 52  # 1 year rolling


def _build_week_key(dt: datetime) -> str:
    """ISO week string, e.g. '2026-W08'."""
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _update_key_events(existing: Optional[dict], new_articles: List[Article]) -> dict:
    """Merge new articles into the key_events log, keeping the most significant."""
    events = (existing or {}).get("events", [])

    # Build new event entries from articles with extreme sentiment
    for art in new_articles:
        if art.sentiment is None:
            continue
        # Include articles whose sentiment deviates notably from neutral (0.5)
        if abs(art.sentiment - 0.5) < 0.1:
            continue
        events.append({
            "date": art.published_at.date().isoformat() if art.published_at else None,
            "title": art.title,
            "sentiment": float(art.sentiment),
            "url": art.url,
        })

    # Sort by absolute deviation from neutral descending, keep top N
    events.sort(key=lambda e: abs(e.get("sentiment", 0.5) - 0.5), reverse=True)
    events = events[:_MAX_KEY_EVENTS]

    return {"events": events}


def _update_sentiment_trend(existing: Optional[dict], new_articles: List[Article]) -> dict:
    """Update the weekly sentiment rolling window."""
    weekly: dict = {}

    # Seed from existing buckets
    for bucket in (existing or {}).get("weekly", []):
        weekly[bucket["week"]] = {
            "week": bucket["week"],
            "avg_sentiment": bucket["avg_sentiment"],
            "count": bucket["count"],
        }

    # Add data from new articles
    for art in new_articles:
        if art.sentiment is None or art.published_at is None:
            continue
        key = _build_week_key(art.published_at)
        if key not in weekly:
            weekly[key] = {"week": key, "avg_sentiment": 0.0, "count": 0}
        bucket = weekly[key]
        # Running average
        n = bucket["count"]
        bucket["avg_sentiment"] = (bucket["avg_sentiment"] * n + float(art.sentiment)) / (n + 1)
        bucket["count"] = n + 1

    # Sort by week, keep last 52 buckets
    sorted_buckets = sorted(weekly.values(), key=lambda b: b["week"])
    sorted_buckets = sorted_buckets[-_MAX_WEEKLY_BUCKETS:]

    return {"weekly": sorted_buckets}


def _build_llm_prompt(ticker: str, existing_narrative: Optional[str], events: list) -> str:
    formatted_events = "\n".join(
        f"- [{e.get('date', '?')}] {e.get('title', 'N/A')} (sentiment: {e.get('sentiment', 0.5):.2f})"
        for e in events[:10]  # Use top 10 events for the prompt
    )
    existing_note = existing_narrative or "No prior notes."
    return (
        f"You are a financial analyst. Here is the existing analytical note for {ticker}:\n"
        f"{existing_note}\n\n"
        f"Recent significant events:\n{formatted_events}\n\n"
        f"Write an updated 3-5 sentence analyst note covering: business context, recent "
        f"developments, sentiment trend, and key risks/opportunities. Be concise and factual."
    )


def _try_generate_narrative(ticker: str, existing_narrative: Optional[str], events: list) -> Optional[str]:
    """Attempt LLM narrative generation. Returns None on any failure."""
    try:
        from app.llm.analytics_agent import get_llm
        llm = get_llm()
        if llm is None:
            return None
        prompt = _build_llm_prompt(ticker, existing_narrative, events)
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        print(f"   ⚠️  LLM narrative skipped for {ticker}: {e}")
        return None


def _process_ticker(db: Session, stock: Stock, knowledge: Optional[StockKnowledge]) -> StockKnowledge:
    """Update or create StockKnowledge for one ticker."""
    # Determine the lookback window: since last_updated or 7 days for first run
    since = (
        knowledge.last_updated
        if knowledge and knowledge.last_updated
        else datetime.utcnow() - timedelta(days=7)
    )

    new_articles = (
        db.query(Article)
        .filter(
            Article.tickers.any(stock.symbol),
            Article.published_at >= since,
        )
        .order_by(Article.published_at.desc())
        .limit(200)
        .all()
    )

    if not new_articles:
        return knowledge  # Nothing to update

    # Structured updates
    key_events = _update_key_events(
        knowledge.key_events if knowledge else None, new_articles
    )
    sentiment_trend = _update_sentiment_trend(
        knowledge.sentiment_trend if knowledge else None, new_articles
    )
    article_count = (knowledge.article_count_processed if knowledge else 0) + len(new_articles)

    # Optional LLM narrative
    events_list = key_events.get("events", [])
    narrative = _try_generate_narrative(
        stock.symbol,
        knowledge.narrative if knowledge else None,
        events_list,
    )

    now = datetime.utcnow()

    if knowledge is None:
        knowledge = StockKnowledge(
            ticker=stock.symbol,
            key_events=key_events,
            sentiment_trend=sentiment_trend,
            article_count_processed=article_count,
            narrative=narrative,
            last_updated=now,
            created_at=now,
        )
        db.add(knowledge)
    else:
        knowledge.key_events = key_events
        knowledge.sentiment_trend = sentiment_trend
        knowledge.article_count_processed = article_count
        knowledge.last_updated = now
        if narrative is not None:
            knowledge.narrative = narrative

    return knowledge


@shared_task(bind=True)
def update_stock_knowledge_task(self, ticker: Optional[str] = None) -> Dict:
    """
    Update the stock_knowledge table for all tracked tickers (or a single ticker).

    Args:
        ticker: If provided, update only this ticker. Otherwise update all active stocks.

    Returns:
        Dict with processing statistics.
    """
    db = SessionLocal()

    try:
        print("🧠 Updating stock knowledge base")

        # Determine which stocks to process
        stock_query = db.query(Stock).filter(Stock.is_active == True)
        if ticker:
            stock_query = stock_query.filter(Stock.symbol == ticker.upper())
        stocks = stock_query.all()

        if not stocks:
            return {"status": "no_stocks", "updated": 0}

        # Preload existing knowledge records
        symbols = [s.symbol for s in stocks]
        existing_map: dict = {
            k.ticker: k
            for k in db.query(StockKnowledge).filter(StockKnowledge.ticker.in_(symbols)).all()
        }

        updated = 0
        skipped = 0

        for stock in stocks:
            try:
                result = _process_ticker(db, stock, existing_map.get(stock.symbol))
                if result is not None:
                    updated += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"   ⚠️  Error processing {stock.symbol}: {e}")
                skipped += 1
                continue

        db.commit()

        print(f"✅ Stock knowledge updated: {updated} tickers, {skipped} skipped")

        return {
            "status": "success",
            "updated": updated,
            "skipped": skipped,
        }

    except Exception as e:
        print(f"❌ Error in update_stock_knowledge_task: {e}")
        db.rollback()
        raise

    finally:
        db.close()
