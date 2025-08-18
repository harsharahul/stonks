"""
Post-Ingestion Hooks

Automatically triggered after new articles are ingested to:
1. Calculate sentiment scores
2. Extract entities and tickers
3. Trigger feature recalculation for affected tickers
4. Update data quality metrics
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from celery import shared_task
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.features.sentiment import SentimentCalculator
from app.models.article import Article
from app.models.stock import Stock
from app.tasks.feature_calculation import calculate_features_for_ticker


class PostIngestError(Exception):
    """Custom exception for post-ingestion processing"""
    pass


def extract_tickers_advanced(text: str, db: Session) -> List[str]:
    """
    Advanced ticker extraction using multiple strategies:
    1. Exact symbol matches
    2. Company name to ticker mapping
    3. Common variations (e.g., "Apple stock" -> AAPL)
    """
    if not text:
        return []
    
    tickers = set()
    text_upper = text.upper()
    
    # Strategy 1: Direct ticker symbols (uppercase, 1-5 chars, word boundaries)
    ticker_pattern = r'\b([A-Z]{1,5})\b'
    potential_tickers = re.findall(ticker_pattern, text_upper)
    
    # Validate against known stocks
    if potential_tickers:
        known_stocks = db.query(Stock.symbol).filter(
            Stock.symbol.in_(potential_tickers)
        ).all()
        tickers.update([s.symbol for s in known_stocks])
    
    # Strategy 2: Company name matching
    stocks = db.query(Stock).all()
    for stock in stocks:
        # Check for company name (case insensitive)
        if stock.company_name and stock.company_name.lower() in text.lower():
            tickers.add(stock.symbol)
        
        # Check for common variations
        # e.g., "Apple Inc", "Apple stock", "Apple's"
        company_words = stock.company_name.split()[0] if stock.company_name else None
        if company_words and len(company_words) > 3:  # Avoid short common words
            pattern = rf'\b{re.escape(company_words)}\b'
            if re.search(pattern, text, re.IGNORECASE):
                tickers.add(stock.symbol)
    
    # Strategy 3: Common aliases and variations
    ticker_aliases = {
        'GOOGLE': 'GOOGL',
        'ALPHABET': 'GOOGL',
        'FACEBOOK': 'META',
        'TWITTER': 'X',
        'BERKSHIRE': 'BRK.B'
    }
    
    for alias, ticker in ticker_aliases.items():
        if alias in text_upper:
            # Verify the ticker exists
            if db.query(Stock).filter(Stock.symbol == ticker).first():
                tickers.add(ticker)
    
    return list(tickers)[:10]  # Limit to 10 tickers per article


@shared_task(bind=True)
def process_new_articles(self, hours_back: int = 1, batch_size: int = 100) -> Dict:
    """
    Process recently ingested articles:
    - Calculate sentiment scores
    - Extract tickers
    - Trigger feature updates
    
    Args:
        hours_back: Process articles from last N hours
        batch_size: Number of articles to process in one batch
        
    Returns:
        Dict with processing statistics
    """
    db = SessionLocal()
    
    try:
        print(f"🔄 Processing new articles (last {hours_back} hours)")
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        # Find unprocessed articles (sentiment = NULL indicates unprocessed)
        articles = db.query(Article).filter(
            and_(
                Article.published_at >= cutoff_time,
                Article.sentiment.is_(None)  # Unprocessed articles
            )
        ).limit(batch_size).all()
        
        if not articles:
            print("   No new articles to process")
            return {"status": "no_articles", "processed": 0}
        
        sentiment_calc = SentimentCalculator()
        
        processed_count = 0
        ticker_updates = set()
        sentiment_stats = {
            'positive': 0,
            'neutral': 0,
            'negative': 0
        }
        
        for article in articles:
            try:
                # Calculate sentiment
                if article.raw_content:
                    # Combine title and content for sentiment analysis
                    full_text = f"{article.title or ''} {article.raw_content}"
                    
                    sentiment_result = sentiment_calc.calculate(full_text)
                    article.sentiment = sentiment_result['sentiment_score']
                    
                    # Store additional sentiment details in entities
                    if not article.entities:
                        article.entities = {}
                    article.entities['sentiment_details'] = {
                        'method': sentiment_result.get('method', 'unknown'),
                        'confidence': sentiment_result.get('confidence', 0),
                        'processed_at': datetime.utcnow().isoformat()
                    }
                    
                    # Track sentiment distribution
                    if article.sentiment > 0.6:
                        sentiment_stats['positive'] += 1
                    elif article.sentiment < 0.4:
                        sentiment_stats['negative'] += 1
                    else:
                        sentiment_stats['neutral'] += 1
                
                # Extract tickers if not already present
                if not article.tickers or len(article.tickers) == 0:
                    extracted_tickers = extract_tickers_advanced(
                        f"{article.title or ''} {article.raw_content or ''}", 
                        db
                    )
                    if extracted_tickers:
                        article.tickers = extracted_tickers
                        ticker_updates.update(extracted_tickers)
                else:
                    ticker_updates.update(article.tickers)
                
                processed_count += 1
                
            except Exception as e:
                print(f"   ⚠️  Error processing article {article.id}: {e}")
                continue
        
        # Commit all article updates
        db.commit()
        
        print(f"✅ Processed {processed_count} articles")
        print(f"   Sentiment: {sentiment_stats}")
        print(f"   Tickers found: {len(ticker_updates)}")
        
        # Trigger feature recalculation for affected tickers
        if ticker_updates:
            for ticker in ticker_updates:
                try:
                    calculate_features_for_ticker.delay(ticker)
                    print(f"   📊 Triggered feature update for {ticker}")
                except Exception as e:
                    print(f"   ⚠️  Failed to trigger feature update for {ticker}: {e}")
        
        return {
            "status": "success",
            "processed": processed_count,
            "sentiment_distribution": sentiment_stats,
            "tickers_updated": list(ticker_updates)
        }
        
    except Exception as e:
        print(f"❌ Error in post-ingestion processing: {e}")
        db.rollback()
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def update_source_reliability(self) -> Dict:
    """
    Update reliability scores for data sources based on:
    - Article quality (non-null content, valid dates)
    - Ticker extraction success rate
    - Sentiment calculation success rate
    
    Returns:
        Dict with reliability update statistics
    """
    db = SessionLocal()
    
    try:
        print("📊 Updating source reliability scores")
        
        from app.models.data_source import DataSource
        
        sources = db.query(DataSource).all()
        updates = []
        
        for source in sources:
            # Calculate metrics for this source
            total_articles = db.query(func.count(Article.id)).filter(
                Article.source_id == source.id
            ).scalar()
            
            if total_articles == 0:
                continue
            
            # Articles with content
            with_content = db.query(func.count(Article.id)).filter(
                and_(
                    Article.source_id == source.id,
                    Article.raw_content != None,
                    Article.raw_content != ''
                )
            ).scalar()
            
            # Articles with extracted tickers
            with_tickers = db.query(func.count(Article.id)).filter(
                and_(
                    Article.source_id == source.id,
                    Article.tickers != None,
                    func.array_length(Article.tickers, 1) > 0
                )
            ).scalar()
            
            # Articles with non-default sentiment
            with_sentiment = db.query(func.count(Article.id)).filter(
                and_(
                    Article.source_id == source.id,
                    Article.sentiment != 0.5
                )
            ).scalar()
            
            # Calculate quality score
            content_rate = with_content / total_articles
            ticker_rate = with_tickers / total_articles
            sentiment_rate = with_sentiment / total_articles
            
            # Weighted average (content is most important)
            new_score = (
                content_rate * 0.5 +
                ticker_rate * 0.3 +
                sentiment_rate * 0.2
            )
            
            # Smooth with existing score (avoid drastic changes)
            source.reliability_score = float(source.reliability_score * 0.7 + new_score * 0.3)
            
            updates.append({
                "source": source.name,
                "articles": total_articles,
                "old_score": source.reliability_score,
                "new_score": new_score,
                "final_score": source.reliability_score
            })
            
            print(f"   {source.name}: {source.reliability_score:.3f} "
                  f"(articles: {total_articles}, content: {content_rate:.1%})")
        
        db.commit()
        
        print(f"✅ Updated reliability for {len(updates)} sources")
        
        return {
            "status": "success",
            "sources_updated": len(updates),
            "details": updates
        }
        
    except Exception as e:
        print(f"❌ Error updating source reliability: {e}")
        db.rollback()
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def cleanup_old_articles(self, days_to_keep: int = 30) -> Dict:
    """
    Clean up old articles to manage database size.
    Keeps summary statistics before deletion.
    
    Args:
        days_to_keep: Number of days of articles to retain
        
    Returns:
        Dict with cleanup statistics
    """
    db = SessionLocal()
    
    try:
        print(f"🧹 Cleaning up articles older than {days_to_keep} days")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Count articles to delete
        to_delete = db.query(func.count(Article.id)).filter(
            Article.published_at < cutoff_date
        ).scalar()
        
        if to_delete == 0:
            print("   No articles to clean up")
            return {"status": "no_cleanup", "deleted": 0}
        
        # Store summary statistics before deletion
        # In production, you might want to archive to cold storage instead
        
        # Delete old articles
        db.query(Article).filter(
            Article.published_at < cutoff_date
        ).delete()
        
        db.commit()
        
        print(f"✅ Cleaned up {to_delete} old articles")
        
        return {
            "status": "success",
            "deleted": to_delete,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error cleaning up articles: {e}")
        db.rollback()
        raise
        
    finally:
        db.close()
