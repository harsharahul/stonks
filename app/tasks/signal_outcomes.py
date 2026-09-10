"""Nightly scorer: turn emitted signals into verified per-source track records.

For every directional signal (bullish/bearish) whose horizon window has
closed, look up the realized forward return from the ``prices`` table and
record whether the call was right. Aggregating ``signal_outcomes`` by
``source`` is what lets users judge which signal sources have actually been
worth listening to, the trust layer under the open signal marketplace.

The run walks the whole pending set in pages instead of taking one fixed
batch, so signals that cannot be priced yet never block the ones behind
them. Prices are looked up once per ticker per run; tickers with no rows in
the window are backfilled from the market data source, so signals on tickers
outside the tracked stock list still earn a track record.

Source attribution:
- plugin signals carry ``model_version = "plugin:<source_id>"`` (and
  ``signal_metadata.source_plugin``) from the dispatcher
- anomaly-detection signals are grouped under ``anomaly_detector``
- everything else is the rule engine (``signal_generator``)
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Tuple

from celery import shared_task
from sqlalchemy import select, tuple_

from app.core.database import SessionLocal
from app.models.signal import Signal
from app.models.signal_outcome import SignalOutcome
from app.tasks.etl_helpers import get_or_create_etl_job

logger = logging.getLogger(__name__)

HORIZON_DAYS = 5
MAX_SIGNAL_AGE_DAYS = 90  # don't rescan ancient unscoreable signals forever
PAGE_SIZE = 500  # rows per query while walking the pending set
MAX_SCORED_PER_RUN = 5000  # safety valve for a first run over a large backlog
MAX_BACKFILLS_PER_RUN = 40  # tickers fetched from the market data source per run
SPAN_PAD_DAYS = 90  # bars are fetched once per ticker for the whole run window


def source_for_signal(model_version: Optional[str], metadata: Optional[dict], signal_type: str) -> str:
    """Attribute a signal row to the source that emitted it."""
    if isinstance(metadata, dict) and metadata.get("source_plugin"):
        return str(metadata["source_plugin"])
    if model_version and model_version.startswith("plugin:"):
        return model_version.split(":", 1)[1]
    if signal_type.startswith(("anomaly_", "urgent_")):
        return "anomaly_detector"
    return "rule_engine"


def evaluate_outcome(direction: str, entry: Optional[float], exit_: Optional[float]) -> Tuple[Optional[float], Optional[bool]]:
    """(realized_return, win) for a directional call; (None, None) if unscoreable."""
    if entry is None or exit_ is None or entry <= 0:
        return None, None
    realized = (exit_ - entry) / entry
    if direction == "bullish":
        return realized, realized > 0
    if direction == "bearish":
        return realized, realized < 0
    return realized, None  # neutral calls carry no win/loss


class BarCache:
    """Daily bars per ticker, fetched once per run and backfilled on demand.

    ``fetch_bars(ticker, start, end)`` returns objects with ``.date`` and
    ``.close``. ``backfill(ticker, start, end)`` loads missing rows into the
    price store and returns how many it added; it runs at most once per
    ticker and at most ``max_backfills`` times per run.
    """

    def __init__(
        self,
        fetch_bars: Callable[[str, date, date], list],
        backfill: Optional[Callable[[str, date, date], int]] = None,
        max_backfills: int = 0,
    ):
        self._fetch = fetch_bars
        self._backfill = backfill
        self._max_backfills = max_backfills
        self._bars: Dict[str, list] = {}
        self._span: Dict[str, Tuple[date, date]] = {}
        self._attempted: set = set()
        self._backfilled: set = set()

    def bars(self, ticker: str, start: date, end: date) -> list:
        span = self._span.get(ticker)
        if span is None or start < span[0] or end > span[1]:
            lo = min(start, span[0]) if span else start
            hi = max(end, span[1]) if span else end + timedelta(days=SPAN_PAD_DAYS)
            rows = list(self._fetch(ticker, lo, hi))
            if not rows and self._can_backfill(ticker):
                self._attempted.add(ticker)
                try:
                    added = self._backfill(ticker, lo, hi)
                except Exception as exc:  # one bad ticker must not end the run
                    logger.warning("price backfill failed for %s: %s", ticker, exc)
                    added = 0
                if added:
                    self._backfilled.add(ticker)
                    rows = list(self._fetch(ticker, lo, hi))
            self._bars[ticker] = rows
            self._span[ticker] = (lo, hi)
        return [b for b in self._bars[ticker] if start <= b.date <= end]

    def _can_backfill(self, ticker: str) -> bool:
        return (
            self._backfill is not None
            and ticker not in self._attempted
            and len(self._attempted) < self._max_backfills
        )

    def stats(self) -> Dict[str, int]:
        return {
            "tickers": len(self._bars),
            "backfilled": len(self._backfilled),
            "backfill_attempts": len(self._attempted),
            "unpriced": sum(1 for rows in self._bars.values() if not rows),
        }


def entry_exit(bars: list, generated_at: datetime, horizon_days: int) -> Tuple[Optional[float], Optional[float]]:
    """First close on/after the signal date, last close inside the horizon window."""
    if not bars:
        return None, None
    bars = sorted(bars, key=lambda b: b.date)
    start = generated_at.date()
    window_end = start + timedelta(days=horizon_days)
    in_window = [b for b in bars if b.date <= window_end]
    return bars[0].close, (in_window[-1].close if in_window else None)


def iter_pending_signals(db, horizon_cutoff: datetime, age_floor: datetime, page_size: int = PAGE_SIZE) -> Iterator[Signal]:
    """Directional signals with a closed horizon and no outcome yet, oldest first, in pages."""
    already = select(SignalOutcome.signal_id)
    after: Optional[Tuple[datetime, object]] = None
    while True:
        stmt = (
            select(Signal)
            .where(
                Signal.direction.in_(["bullish", "bearish"]),
                Signal.generated_at <= horizon_cutoff,
                Signal.generated_at >= age_floor,
                Signal.id.not_in(already),
            )
            .order_by(Signal.generated_at.asc(), Signal.id.asc())
            .limit(page_size)
        )
        if after is not None:
            stmt = stmt.where(tuple_(Signal.generated_at, Signal.id) > tuple_(after[0], after[1]))
        rows = db.execute(stmt).scalars().all()
        for row in rows:
            yield row
        if len(rows) < page_size:
            return
        after = (rows[-1].generated_at, rows[-1].id)


def score_signals(
    pending: Iterable,
    cache: BarCache,
    sink: Callable[[SignalOutcome], None],
    horizon_days: int = HORIZON_DAYS,
    max_scored: Optional[int] = None,
) -> Dict:
    """Score every pending signal that has price coverage; hand outcomes to ``sink``."""
    scored = skipped = examined = 0
    capped = False
    for sig in pending:
        examined += 1
        start = sig.generated_at.date()
        bars = cache.bars(sig.ticker, start, start + timedelta(days=horizon_days + 7))  # pad for weekends/holidays
        entry, exit_ = entry_exit(bars, sig.generated_at, horizon_days)
        realized, win = evaluate_outcome(sig.direction, entry, exit_)
        if realized is None:
            skipped += 1  # no price coverage yet; retried until the age floor passes
            continue
        sink(
            SignalOutcome(
                signal_id=sig.id,
                ticker=sig.ticker,
                source=source_for_signal(sig.model_version, sig.signal_metadata, sig.signal_type),
                signal_type=sig.signal_type,
                direction=sig.direction,
                generated_at=sig.generated_at,
                horizon_days=horizon_days,
                entry_price=entry,
                exit_price=exit_,
                realized_return=realized,
                win=win,
            )
        )
        scored += 1
        if max_scored is not None and scored >= max_scored:
            capped = True
            break
    return {"scored": scored, "skipped": skipped, "examined": examined, "capped": capped}


def source_track_records(db) -> Dict[str, Dict]:
    """Per-source aggregates over scored outcomes: the verified track record.

    ``avg_signal_return`` is the return from FOLLOWING the signal (bearish
    calls flip sign), so a bearish source that calls drops correctly shows a
    positive number.
    """
    from sqlalchemy import case, func as sa_func

    signed = case(
        (SignalOutcome.direction == "bearish", -SignalOutcome.realized_return),
        else_=SignalOutcome.realized_return,
    )
    rows = (
        db.query(
            SignalOutcome.source,
            sa_func.count().label("scored"),
            sa_func.sum(case((SignalOutcome.win.is_(True), 1), else_=0)).label("wins"),
            sa_func.avg(signed).label("avg_signal_return"),
            sa_func.max(SignalOutcome.evaluated_at).label("last_scored_at"),
        )
        .filter(SignalOutcome.win.isnot(None))
        .group_by(SignalOutcome.source)
        .all()
    )
    return {
        r.source: {
            "scored": int(r.scored),
            "wins": int(r.wins or 0),
            "win_rate": round(float(r.wins or 0) / r.scored, 4) if r.scored else None,
            "avg_signal_return": round(float(r.avg_signal_return), 6) if r.avg_signal_return is not None else None,
            "last_scored_at": r.last_scored_at.isoformat() if r.last_scored_at else None,
        }
        for r in rows
    }


@shared_task(bind=True, queue="analytics", acks_late=True, reject_on_worker_lost=True)
def score_signal_outcomes_task(self) -> Dict:
    """Score directional signals whose horizon window has closed."""
    from app.agents.adapters.tools import fetch_daily_bars
    from app.tasks.price_ingestion import ensure_daily_prices

    now = datetime.now(timezone.utc)
    horizon_cutoff = now - timedelta(days=HORIZON_DAYS)
    age_floor = now - timedelta(days=MAX_SIGNAL_AGE_DAYS)

    with SessionLocal() as db:
        job_run = get_or_create_etl_job(db, self.request.id, "signal_outcome_scoring", {"task_id": self.request.id})
        try:
            # Read within the task's session so bars just backfilled (and
            # flushed) in this session are visible on the re-read.
            session_bars = lambda ticker, start, end: fetch_daily_bars(ticker, start, end, db=db)
            cache = BarCache(
                session_bars,
                backfill=lambda ticker, start, end: ensure_daily_prices(db, ticker, start, end),
                max_backfills=MAX_BACKFILLS_PER_RUN,
            )
            stats = score_signals(
                iter_pending_signals(db, horizon_cutoff, age_floor, PAGE_SIZE),
                cache,
                db.add,
                HORIZON_DAYS,
                max_scored=MAX_SCORED_PER_RUN,
            )
            db.commit()
            details = {**stats, **cache.stats()}
            job_run.status = "success"
            job_run.finished_at = datetime.utcnow()
            job_run.items_processed = stats["scored"]
            job_run.details = {**(job_run.details or {}), **details}
            db.commit()
        except Exception as e:
            db.rollback()
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details = {**(job_run.details or {}), "error": str(e), "error_type": type(e).__name__}
            db.commit()
            raise

    logger.info("score_signal_outcomes: %s", details)
    return {"task": "score_signal_outcomes", "as_of": now.date().isoformat(), **details}
