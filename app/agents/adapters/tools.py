"""Stonks adapters for TradingAgents tool layer.

Vendored upstream tool wrappers (e.g.
``app.agents.tradingagents.agents.utils.core_stock_tools.get_stock_data``)
delegate to ``route_to_vendor("get_stock_data", ...)`` which lives in the
vendored stub at ``app.agents.tradingagents.dataflows.interface``. The stub
forwards to the matching function in this module.

Naming contract: a function named exactly ``<method>`` here is invoked by
``route_to_vendor("<method>", *args, **kwargs)``. The signatures match the
``@tool``-decorated wrappers upstream:

  get_stock_data(symbol, start_date, end_date) -> str
  get_indicators(symbol, indicator, curr_date, look_back_days=30) -> str
  get_news(ticker, start_date, end_date) -> str
  get_global_news(curr_date, look_back_days=7, limit=5) -> str
  get_insider_transactions(ticker) -> str
  get_fundamentals(ticker, curr_date) -> str
  get_balance_sheet(ticker, freq="quarterly", curr_date=None) -> str
  get_cashflow(ticker, freq="quarterly", curr_date=None) -> str
  get_income_statement(ticker, freq="quarterly", curr_date=None) -> str

Every adapter returns a deterministic non-empty markdown string. On missing
data we return a "Not available: see narrative" stub so downstream prompts
never see ``None``/``""`` (the missing-data fallback specified in the plan).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import desc, select

from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOT_AVAILABLE = "_Not available._ Phase 1 fallback: rely on the per-ticker narrative."


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _stock_knowledge_excerpt(ticker: str, db) -> str:
    """Return a short markdown excerpt from `StockKnowledge` for fallback paths."""
    from app.models.stock_knowledge import StockKnowledge  # local import to avoid hard cycle

    row = db.execute(
        select(StockKnowledge).where(StockKnowledge.ticker == ticker.upper()).limit(1)
    ).scalar_one_or_none()
    if not row:
        return _NOT_AVAILABLE
    parts = []
    if getattr(row, "narrative", None):
        narrative = row.narrative if len(row.narrative) <= 1200 else row.narrative[:1200] + "..."
        parts.append(f"**Narrative**\n{narrative}")
    key_events = getattr(row, "key_events", None)
    if key_events:
        try:
            if isinstance(key_events, list):
                bullets = key_events[:5]
            else:
                bullets = list(key_events)[:5]
            if bullets:
                lines = [f"- {ev}" for ev in bullets]
                parts.append("**Recent key events**\n" + "\n".join(lines))
        except Exception:
            pass
    if not parts:
        return _NOT_AVAILABLE
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Core stock data
# ---------------------------------------------------------------------------

def fetch_daily_bars(symbol: str, start: date, end: date, db=None) -> list:
    """Daily OHLCV bars for `symbol` from the `prices` table.

    The Price model stores `symbol` + `timestamp` (DateTime) with OHLCV in
    `open_price`/`high`/`low`/`close`/`volume`; intraday snapshots may coexist
    with daily bars, so we keep the LAST row per calendar day that has a
    close. Returns a list of objects with .date/.open/.high/.low/.close/.volume.

    Pass ``db`` to read within an existing session so rows just written (and
    flushed) in that session are visible, for example bars a caller backfilled
    moments earlier. Without it a fresh session is opened.
    """
    from dataclasses import dataclass as _dc

    from app.models.price import Price

    @_dc
    class Bar:
        date: date
        open: Optional[float]
        high: Optional[float]
        low: Optional[float]
        close: float
        volume: Optional[int]

    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())

    def _read(session):
        return (
            session.execute(
                select(Price)
                .where(
                    Price.symbol == symbol.upper(),
                    Price.timestamp >= start_dt,
                    Price.timestamp <= end_dt,
                )
                .order_by(Price.timestamp.asc())
            )
            .scalars()
            .all()
        )

    if db is not None:
        rows = _read(db)
    else:
        with SessionLocal() as _db:
            rows = _read(_db)

    by_day: dict = {}
    for r in rows:
        close = r.close if r.close is not None else r.price
        if close is None:
            continue
        day = r.timestamp.date()
        by_day[day] = Bar(
            date=day,
            open=float(r.open_price) if r.open_price is not None else None,
            high=float(r.high) if r.high is not None else None,
            low=float(r.low) if r.low is not None else None,
            close=float(close),
            volume=int(r.volume) if r.volume is not None else None,
        )
    return [by_day[d] for d in sorted(by_day)]


def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """OHLCV summary from our `prices` table for the [start_date, end_date] window."""
    sd = _parse_date(start_date) or (date.today() - timedelta(days=90))
    ed = _parse_date(end_date) or date.today()
    sym = symbol.upper()

    rows = fetch_daily_bars(sym, sd, ed)
    if not rows:
        return f"# {sym}: OHLCV ({start_date} → {end_date})\n\n{_NOT_AVAILABLE}"

    first = rows[0]
    last = rows[-1]
    ret = (last.close - first.close) / first.close if first.close else None
    highs = [r.high for r in rows if r.high is not None]
    lows = [r.low for r in rows if r.low is not None]
    vols = [r.volume for r in rows if r.volume is not None]
    avg_vol = sum(vols) / len(vols) if vols else None

    lines = [
        f"# {sym}: OHLCV ({start_date} → {end_date})",
        "",
        f"- Bars: {len(rows)}",
        f"- First close ({first.date}): {first.close:.4f}",
        f"- Last close ({last.date}):  {last.close:.4f}",
        f"- Period return: {ret:+.2%}" if ret is not None else "- Period return: n/a",
        f"- High over period: {max(highs):.4f}" if highs else "- High over period: n/a",
        f"- Low over period: {min(lows):.4f}" if lows else "- Low over period: n/a",
        f"- Avg daily volume: {avg_vol:,.0f}" if avg_vol else "- Avg daily volume: n/a",
        "",
        "| date | open | high | low | close | volume |",
        "|------|------|------|-----|-------|--------|",
    ]
    # Show the last 15 bars to keep the prompt compact
    for r in rows[-15:]:
        def _fmt(v: Optional[float]) -> str:
            return f"{v:.2f}" if v is not None else "n/a"
        lines.append(
            f"| {r.date} | {_fmt(r.open)} | {_fmt(r.high)} | "
            f"{_fmt(r.low)} | {r.close:.2f} | {r.volume or 0:,} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Technical indicators (Phase 1: derive a few from Price; expand in Phase 4)
# ---------------------------------------------------------------------------

def _sma(values: list[float], n: int) -> Optional[float]:
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def _rsi(values: list[float], period: int = 14) -> Optional[float]:
    if len(values) <= period:
        return None
    gains, losses = [], []
    for prev, curr in zip(values[-period - 1 : -1], values[-period:]):
        diff = curr - prev
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def get_indicators(
    symbol: str,
    indicator: str = "summary",
    curr_date: Optional[str] = None,
    look_back_days: int = 30,
) -> str:
    """RSI / SMA / momentum summary for a ticker over a look-back window."""
    end = _parse_date(curr_date) or date.today()
    start = end - timedelta(days=max(look_back_days, 60))
    sym = symbol.upper()

    rows = fetch_daily_bars(sym, start, end)
    if len(rows) < 5:
        return f"# {sym}: Indicators ({indicator})\n\n{_NOT_AVAILABLE}"

    closes = [r.close for r in rows]
    sma_20 = _sma(closes, 20)
    sma_50 = _sma(closes, 50)
    rsi_14 = _rsi(closes, 14)
    last = closes[-1]
    first = closes[0]
    period_return = (last - first) / first if first else None

    lines = [
        f"# {sym}: Indicators ({indicator}, look_back={look_back_days}d)",
        "",
        f"- Last close: {last:.4f} on {rows[-1].date}",
        f"- Period return: {period_return:+.2%}" if period_return is not None else "- Period return: n/a",
        f"- SMA(20): {sma_20:.4f}" if sma_20 is not None else "- SMA(20): n/a",
        f"- SMA(50): {sma_50:.4f}" if sma_50 is not None else "- SMA(50): n/a",
        f"- RSI(14): {rsi_14:.2f}" if rsi_14 is not None else "- RSI(14): n/a",
    ]
    if sma_20 is not None and sma_50 is not None:
        trend = "bullish" if sma_20 > sma_50 else "bearish" if sma_20 < sma_50 else "neutral"
        lines.append(f"- 20/50 trend: {trend}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# News data
# ---------------------------------------------------------------------------

def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """Most-relevant articles for ticker in [start_date, end_date]."""
    from app.models.article import Article

    sd = _parse_date(start_date) or (date.today() - timedelta(days=7))
    ed = _parse_date(end_date) or date.today()
    sym = ticker.upper()

    with SessionLocal() as db:
        # Article rows with the ticker tag in their tickers JSON or title.
        # We do a permissive title-substring match plus optional tickers
        # field to keep this Phase-1 simple.
        try:
            articles = (
                db.execute(
                    select(Article)
                    .where(
                        Article.published_at >= datetime.combine(sd, datetime.min.time()),
                        Article.published_at <= datetime.combine(ed, datetime.max.time()),
                    )
                    .order_by(desc(Article.published_at))
                    .limit(40)
                )
                .scalars()
                .all()
            )
        except Exception as exc:
            logger.warning("get_news: query failed: %s", exc)
            return f"# News: {sym} ({start_date} → {end_date})\n\n{_NOT_AVAILABLE}"

        # Filter by ticker tag (best-effort across schema variations).
        filtered = []
        for art in articles:
            tickers_field = getattr(art, "tickers", None) or getattr(art, "ticker", None)
            title = (getattr(art, "title", "") or "").upper()
            if tickers_field:
                if isinstance(tickers_field, list) and sym in [t.upper() for t in tickers_field]:
                    filtered.append(art)
                    continue
                if isinstance(tickers_field, str) and sym in tickers_field.upper():
                    filtered.append(art)
                    continue
            if sym in title.split() or f"({sym})" in title or f"${sym}" in title:
                filtered.append(art)

        rows = filtered[:10] if filtered else articles[:5]
        if not rows:
            return f"# News: {sym} ({start_date} → {end_date})\n\n{_NOT_AVAILABLE}"

        lines = [f"# News: {sym} ({start_date} → {end_date})", ""]
        for r in rows:
            sentiment = getattr(r, "sentiment", None)
            sent_str = f" sentiment={float(sentiment):+.2f}" if sentiment is not None else ""
            published = r.published_at.strftime("%Y-%m-%d") if r.published_at else "?"
            title = (r.title or "").strip()
            lines.append(f"- {published}: {title}{sent_str}")
        return "\n".join(lines)


def get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 5) -> str:
    """Top macro / global news in the last `look_back_days` days, untagged by ticker."""
    from app.models.article import Article

    end = _parse_date(curr_date) or date.today()
    start = end - timedelta(days=max(look_back_days, 1))

    with SessionLocal() as db:
        articles = (
            db.execute(
                select(Article)
                .where(
                    Article.published_at >= datetime.combine(start, datetime.min.time()),
                    Article.published_at <= datetime.combine(end, datetime.max.time()),
                )
                .order_by(desc(Article.published_at))
                .limit(60)
            )
            .scalars()
            .all()
        )
        # Macro-ish proxy: untagged or mentions multiple tickers.
        rows = []
        for art in articles:
            tickers_field = getattr(art, "tickers", None)
            if not tickers_field:
                rows.append(art)
            elif isinstance(tickers_field, list) and len(tickers_field) >= 3:
                rows.append(art)
            if len(rows) >= limit:
                break

        if not rows:
            return f"# Global news ({start} → {end})\n\n{_NOT_AVAILABLE}"

        lines = [f"# Global news ({start} → {end})", ""]
        for r in rows:
            published = r.published_at.strftime("%Y-%m-%d") if r.published_at else "?"
            lines.append(f"- {published}: {(r.title or '').strip()}")
        return "\n".join(lines)


def get_insider_transactions(ticker: str) -> str:
    """Recent politician-trade rows for `ticker` (Stonks treats these as insider proxy)."""
    sym = ticker.upper()
    try:
        from app.models.politician_trade import PoliticianTrade  # type: ignore
    except ImportError:
        return f"# Insider transactions: {sym}\n\n{_NOT_AVAILABLE}"

    cutoff = date.today() - timedelta(days=120)
    with SessionLocal() as db:
        try:
            rows = (
                db.execute(
                    select(PoliticianTrade)
                    .where(PoliticianTrade.ticker == sym)
                    .order_by(desc(PoliticianTrade.transaction_date))
                    .limit(15)
                )
                .scalars()
                .all()
            )
        except Exception as exc:
            logger.info("get_insider_transactions: query failed: %s", exc)
            return f"# Insider transactions: {sym}\n\n{_NOT_AVAILABLE}"

    if not rows:
        return f"# Insider transactions: {sym}\n\n{_NOT_AVAILABLE}"

    lines = [f"# Insider / political trades: {sym}", ""]
    for r in rows:
        when = getattr(r, "transaction_date", None) or getattr(r, "filing_date", None)
        when_str = when.isoformat() if when else "?"
        actor = getattr(r, "politician_name", None) or getattr(r, "name", None) or "?"
        side = getattr(r, "transaction_type", None) or "?"
        amt = getattr(r, "amount_label", None) or getattr(r, "amount", None) or "?"
        lines.append(f"- {when_str}: {actor} {side} {amt}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fundamentals (Phase 1 leans on StockKnowledge until SEC EDGAR enhanced is restored)
# ---------------------------------------------------------------------------

def get_fundamentals(ticker: str, curr_date: Optional[str] = None) -> str:
    sym = ticker.upper()
    with SessionLocal() as db:
        excerpt = _stock_knowledge_excerpt(sym, db)
    return f"# Fundamentals: {sym}\n\n{excerpt}"


def get_balance_sheet(
    ticker: str,
    freq: str = "quarterly",
    curr_date: Optional[str] = None,
) -> str:
    sym = ticker.upper()
    return (
        f"# Balance sheet: {sym} ({freq})\n\n{_NOT_AVAILABLE}\n\n"
        "Phase-1 Stonks fundamentals lean on the per-ticker narrative; "
        "structured XBRL parsing is on the SEC EDGAR enhanced backlog."
    )


def get_cashflow(
    ticker: str,
    freq: str = "quarterly",
    curr_date: Optional[str] = None,
) -> str:
    sym = ticker.upper()
    return (
        f"# Cash flow: {sym} ({freq})\n\n{_NOT_AVAILABLE}\n\n"
        "Phase-1 Stonks fundamentals lean on the per-ticker narrative; "
        "structured XBRL parsing is on the SEC EDGAR enhanced backlog."
    )


def get_income_statement(
    ticker: str,
    freq: str = "quarterly",
    curr_date: Optional[str] = None,
) -> str:
    sym = ticker.upper()
    return (
        f"# Income statement: {sym} ({freq})\n\n{_NOT_AVAILABLE}\n\n"
        "Phase-1 Stonks fundamentals lean on the per-ticker narrative; "
        "structured XBRL parsing is on the SEC EDGAR enhanced backlog."
    )
