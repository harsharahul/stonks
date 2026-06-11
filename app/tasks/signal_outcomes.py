"""Nightly scorer: turn emitted signals into verified per-source track records.

For every directional signal (bullish/bearish) whose horizon window has
closed, look up the realized forward return from the ``prices`` table and
record whether the call was right. Aggregating ``signal_outcomes`` by
``source`` is what lets users judge which signal sources have actually been
worth listening to — the trust layer under the open signal marketplace.

Source attribution:
- plugin signals carry ``model_version = "plugin:<source_id>"`` (and
  ``signal_metadata.source_plugin``) from the dispatcher
- anomaly-detection signals are grouped under ``anomaly_detector``
- everything else is the rule engine (``signal_generator``)
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Tuple

from celery import shared_task
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.signal import Signal
from app.models.signal_outcome import SignalOutcome
from app.tasks.etl_helpers import get_or_create_etl_job

logger = logging.getLogger(__name__)

HORIZON_DAYS = 5
MAX_SIGNAL_AGE_DAYS = 90  # don't rescan ancient unscoreable signals forever
BATCH_LIMIT = 500


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


def _entry_exit_for(db, ticker: str, generated_at: datetime, horizon_days: int) -> Tuple[Optional[float], Optional[float]]:
    """First close on/after signal date, last close inside the horizon window."""
    from app.agents.adapters.tools import fetch_daily_bars

    start = generated_at.date()
    end = start + timedelta(days=horizon_days + 7)  # pad for weekends/holidays
    bars = fetch_daily_bars(ticker, start, end)
    if not bars:
        return None, None
    bars = sorted(bars, key=lambda b: b.date)
    entry = bars[0].close
    window_end = start + timedelta(days=horizon_days)
    in_window = [b for b in bars if b.date <= window_end]
    exit_ = in_window[-1].close if in_window else None
    return entry, exit_


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
    scored = 0
    skipped = 0
    today = date.today()
    horizon_cutoff = datetime.utcnow() - timedelta(days=HORIZON_DAYS)
    age_floor = datetime.utcnow() - timedelta(days=MAX_SIGNAL_AGE_DAYS)

    with SessionLocal() as db:
        job_run = get_or_create_etl_job(db, self.request.id, "signal_outcome_scoring", {"task_id": self.request.id})
        try:
            already = select(SignalOutcome.signal_id)
            pending = (
                db.execute(
                    select(Signal)
                    .where(
                        Signal.direction.in_(["bullish", "bearish"]),
                        Signal.generated_at <= horizon_cutoff,
                        Signal.generated_at >= age_floor,
                        Signal.id.not_in(already),
                    )
                    .order_by(Signal.generated_at.asc())
                    .limit(BATCH_LIMIT)
                )
                .scalars()
                .all()
            )

            for sig in pending:
                entry, exit_ = _entry_exit_for(db, sig.ticker, sig.generated_at, HORIZON_DAYS)
                realized, win = evaluate_outcome(sig.direction, entry, exit_)
                if realized is None:
                    skipped += 1  # no price coverage yet; retried until age floor passes
                    continue
                db.add(
                    SignalOutcome(
                        signal_id=sig.id,
                        ticker=sig.ticker,
                        source=source_for_signal(sig.model_version, sig.signal_metadata, sig.signal_type),
                        signal_type=sig.signal_type,
                        direction=sig.direction,
                        generated_at=sig.generated_at,
                        horizon_days=HORIZON_DAYS,
                        entry_price=entry,
                        exit_price=exit_,
                        realized_return=realized,
                        win=win,
                    )
                )
                scored += 1

            db.commit()
            job_run.status = "success"
            job_run.finished_at = datetime.utcnow()
            job_run.items_processed = scored
            job_run.details = {**(job_run.details or {}), "scored": scored, "skipped": skipped}
            db.commit()
        except Exception as e:
            db.rollback()
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details = {**(job_run.details or {}), "error": str(e), "error_type": type(e).__name__}
            db.commit()
            raise

    logger.info("score_signal_outcomes: scored=%d skipped=%d", scored, skipped)
    return {"task": "score_signal_outcomes", "scored": scored, "skipped": skipped, "as_of": today.isoformat()}
