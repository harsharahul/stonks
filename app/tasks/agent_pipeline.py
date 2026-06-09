"""Celery tasks that drive the AI Trading Desk pipeline.

Phase 1 surface:
- ``refresh_universe_membership_task``  Sun 00:00 UTC — recompute coverage
- ``run_desk_universe_nightly_task``    daily 7:15 UTC — enqueue per-ticker runs
- ``run_desk_for_ticker_task``          triggered (nightly batch / on-demand)
- ``score_past_decisions_task``         daily 23:00 UTC — fill outcomes

Phase 2 will add ``event_triggered_desk_check_task``; Phase 4 adds
``monitor_decision_distribution_task``. The corresponding beat-schedule
entries live in ``app.celery_beat_config``.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from celery import shared_task
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.service import (
    get_active_universe,
    refresh_universe_membership,
    run_for_ticker,
)
from app.core.database import SessionLocal
from app.models.agent_decision import AgentDecision
from app.models.agent_decision_outcome import AgentDecisionOutcome

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Universe membership
# ---------------------------------------------------------------------------


@shared_task(bind=True, queue="analytics")
def refresh_universe_membership_task(self) -> Dict:
    """Refresh the AI Trading Desk's coverage universe."""
    with SessionLocal() as db:
        inserted = refresh_universe_membership(db)
    logger.info("refresh_universe_membership_task: inserted %d active rows", inserted)
    return {"task": "refresh_universe_membership", "inserted": inserted}


# ---------------------------------------------------------------------------
# Per-ticker desk run
# ---------------------------------------------------------------------------


@shared_task(bind=True, queue="analytics", soft_time_limit=900, time_limit=1200)
def run_desk_for_ticker_task(
    self,
    ticker: str,
    trigger: str = "manual",
    trade_date: Optional[str] = None,
) -> Dict:
    """Run the desk pipeline for one ticker and persist briefs + decision."""
    parsed_date: Optional[date] = None
    if trade_date:
        try:
            parsed_date = datetime.strptime(trade_date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(
                "run_desk_for_ticker_task: bad trade_date=%s (using today)", trade_date
            )

    run_id = run_for_ticker(ticker, trigger=trigger, trade_date=parsed_date)
    return {"task": "run_desk_for_ticker", "ticker": ticker.upper(), "run_id": str(run_id)}


# ---------------------------------------------------------------------------
# Nightly batch
# ---------------------------------------------------------------------------


@shared_task(bind=True, queue="analytics")
def run_desk_universe_nightly_task(self) -> Dict:
    """Enqueue one ``run_desk_for_ticker_task`` per ticker in the active universe."""
    with SessionLocal() as db:
        members = get_active_universe(db)
    enqueued = 0
    for membership in members:
        run_desk_for_ticker_task.apply_async(
            args=(membership.ticker, "nightly"),
            queue="analytics",
            expires=3 * 3600,  # if not picked up in 3h, drop — next batch supersedes
        )
        enqueued += 1
    logger.info("run_desk_universe_nightly_task: enqueued %d ticker runs", enqueued)
    return {"task": "run_desk_universe_nightly", "enqueued": enqueued}


# ---------------------------------------------------------------------------
# Retrospective scoring
# ---------------------------------------------------------------------------


def _close_to_date(close_dates: List[date], target: date) -> Optional[date]:
    """Closest trading date <= target from a sorted list."""
    candidates = [d for d in close_dates if d <= target]
    return candidates[-1] if candidates else None


def _scoring_for_decision(
    db: Session,
    decision: AgentDecision,
) -> Optional[Dict[str, Optional[float]]]:
    """Compute realized return + alpha vs SPY for one decision; None if too soon."""
    from app.agents.adapters.tools import fetch_daily_bars

    sym = decision.ticker
    as_of = decision.as_of_date
    today = date.today()

    # Pull a wide window and pick the closest <= as_of+5d / +30d.
    end_window = as_of + timedelta(days=45)
    if today < as_of + timedelta(days=5):
        return None  # not enough days to score 5d yet

    sym_bars = fetch_daily_bars(sym, as_of, end_window)
    spy_bars = fetch_daily_bars("SPY", as_of, end_window)
    if not sym_bars or not spy_bars:
        return None

    sym_dict = {b.date: b.close for b in sym_bars}
    spy_dict = {b.date: b.close for b in spy_bars}
    if not sym_dict or not spy_dict:
        return None

    sym_dates = sorted(sym_dict.keys())
    spy_dates = sorted(spy_dict.keys())
    open_date = sym_dates[0]
    open_close = sym_dict[open_date]
    spy_open = spy_dict.get(spy_dates[0])

    def ret_at(target: date, sym_close: Optional[float]) -> Optional[float]:
        if sym_close is None or open_close is None or open_close == 0:
            return None
        return (sym_close - open_close) / open_close

    target_5 = as_of + timedelta(days=5)
    target_30 = as_of + timedelta(days=30)

    sym_5 = sym_dict.get(_close_to_date(sym_dates, target_5))
    sym_30 = sym_dict.get(_close_to_date(sym_dates, target_30)) if today >= target_30 else None
    spy_5 = spy_dict.get(_close_to_date(spy_dates, target_5))
    spy_30 = spy_dict.get(_close_to_date(spy_dates, target_30)) if today >= target_30 else None

    raw_5 = ret_at(target_5, sym_5)
    raw_30 = ret_at(target_30, sym_30) if sym_30 else None
    spy_5_ret = ((spy_5 - spy_open) / spy_open) if (spy_5 is not None and spy_open) else None
    spy_30_ret = ((spy_30 - spy_open) / spy_open) if (spy_30 is not None and spy_open) else None
    alpha_5 = (raw_5 - spy_5_ret) if (raw_5 is not None and spy_5_ret is not None) else None
    alpha_30 = (raw_30 - spy_30_ret) if (raw_30 is not None and spy_30_ret is not None) else None

    return {
        "realized_return_5d": raw_5,
        "realized_return_30d": raw_30,
        "spy_return_5d": spy_5_ret,
        "spy_return_30d": spy_30_ret,
        "alpha_5d": alpha_5,
        "alpha_30d": alpha_30,
    }


@shared_task(bind=True, queue="analytics")
def score_past_decisions_task(self) -> Dict:
    """Compute realized returns + alpha vs SPY for decisions whose 5d/30d windows have closed."""
    scored = 0
    skipped = 0
    today = date.today()
    threshold = today - timedelta(days=5)

    with SessionLocal() as db:
        pending = (
            db.execute(
                select(AgentDecision)
                .where(AgentDecision.pending.is_(True), AgentDecision.as_of_date <= threshold)
                .order_by(AgentDecision.as_of_date.asc())
                .limit(500)
            )
            .scalars()
            .all()
        )
        for dec in pending:
            existing = (
                db.execute(
                    select(AgentDecisionOutcome).where(AgentDecisionOutcome.agent_decision_id == dec.id)
                )
                .scalar_one_or_none()
            )
            scoring = _scoring_for_decision(db, dec)
            if scoring is None:
                skipped += 1
                continue
            if existing:
                existing.realized_return_5d = scoring["realized_return_5d"]
                existing.realized_return_30d = scoring["realized_return_30d"]
                existing.spy_return_5d = scoring["spy_return_5d"]
                existing.spy_return_30d = scoring["spy_return_30d"]
                existing.alpha_5d = scoring["alpha_5d"]
                existing.alpha_30d = scoring["alpha_30d"]
                existing.evaluated_at = datetime.utcnow()
            else:
                db.add(
                    AgentDecisionOutcome(
                        agent_decision_id=dec.id,
                        **scoring,
                    )
                )
            # Flip pending to false only when 30d data is also available
            if scoring["realized_return_30d"] is not None:
                dec.pending = False
            scored += 1
        db.commit()

    logger.info("score_past_decisions_task: scored=%d skipped=%d", scored, skipped)
    return {"task": "score_past_decisions", "scored": scored, "skipped": skipped}
