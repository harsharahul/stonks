"""Nightly verified track-record computation for strategies.

Reads FILLED BrokerOrder rows per (strategy, paper-flag), FIFO-matches buys
against sells per symbol into round trips, and writes one
StrategyPerformanceDaily snapshot per strategy per day. Real Alpaca fills
only — the entire point of the social layer is records nobody can fake.
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from celery import shared_task
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.broker_order import BrokerOrder
from app.models.strategy import Strategy
from app.models.strategy_performance import StrategyPerformanceDaily
from app.tasks.etl_helpers import get_or_create_etl_job

logger = logging.getLogger(__name__)


def compute_round_trips(fills: List[dict]) -> List[dict]:
    """FIFO-match fills into closed round trips.

    ``fills``: chronological dicts with symbol, side, qty, price.
    Returns one dict per closed (possibly partial) round trip:
    {symbol, qty, entry_price, exit_price, pnl, return_pct}.
    """
    lots: Dict[str, deque] = defaultdict(deque)  # symbol -> deque[(qty, price)]
    trips: List[dict] = []

    for f in fills:
        qty = float(f["qty"] or 0)
        price = float(f["price"] or 0)
        if qty <= 0 or price <= 0:
            continue
        symbol = f["symbol"]
        if f["side"] == "buy":
            lots[symbol].append([qty, price])
            continue
        # sell: consume open lots FIFO
        remaining = qty
        while remaining > 1e-9 and lots[symbol]:
            lot = lots[symbol][0]
            matched = min(remaining, lot[0])
            pnl = (price - lot[1]) * matched
            trips.append({
                "symbol": symbol,
                "qty": matched,
                "entry_price": lot[1],
                "exit_price": price,
                "pnl": pnl,
                "return_pct": (price - lot[1]) / lot[1] * 100 if lot[1] else 0.0,
            })
            lot[0] -= matched
            remaining -= matched
            if lot[0] <= 1e-9:
                lots[symbol].popleft()
        # Shorting isn't supported in v1; unmatched sell quantity is ignored.

    return trips


def summarize(trips: List[dict], trade_count: int) -> dict:
    closed = len(trips)
    wins = sum(1 for t in trips if t["pnl"] > 0)
    realized = sum(t["pnl"] for t in trips)
    avg_ret = (sum(t["return_pct"] for t in trips) / closed) if closed else None

    # Max drawdown over the cumulative realized-PnL curve.
    max_dd = None
    if closed:
        peak = 0.0
        cum = 0.0
        dd = 0.0
        for t in trips:
            cum += t["pnl"]
            peak = max(peak, cum)
            dd = min(dd, cum - peak)
        base = max(abs(peak), 1.0)
        max_dd = round(dd / base * 100, 4)

    return {
        "trade_count": trade_count,
        "closed_trade_count": closed,
        "win_count": wins,
        "realized_pnl": round(realized, 2) if closed else None,
        "avg_return_pct": round(avg_ret, 4) if avg_ret is not None else None,
        "max_drawdown_pct": max_dd,
    }


@shared_task(bind=True, queue="analytics", acks_late=True, reject_on_worker_lost=True)
def compute_strategy_performance_task(self) -> dict:
    """Snapshot every active strategy's verified record for today."""
    today = date.today()
    computed = 0

    with SessionLocal() as db:
        job_run = get_or_create_etl_job(db, self.request.id, "strategy_performance", {"task_id": self.request.id})
        try:
            strategies = db.execute(
                select(Strategy).where(Strategy.is_active.is_(True))
            ).scalars().all()

            for strategy in strategies:
                fills = db.execute(
                    select(BrokerOrder)
                    .where(
                        BrokerOrder.strategy_id == strategy.id,
                        BrokerOrder.status.in_(["filled", "partially_filled"]),
                    )
                    .order_by(BrokerOrder.filled_at.asc().nulls_last(), BrokerOrder.created_at.asc())
                ).scalars().all()

                for paper_flag in (True, False):
                    subset = [o for o in fills if o.paper == paper_flag]
                    if not subset:
                        continue
                    trips = compute_round_trips([
                        {
                            "symbol": o.symbol,
                            "side": o.side,
                            "qty": o.filled_qty or o.qty,
                            "price": o.filled_avg_price,
                        }
                        for o in subset
                    ])
                    stats = summarize(trips, trade_count=len(subset))

                    existing = db.execute(
                        select(StrategyPerformanceDaily).where(
                            StrategyPerformanceDaily.strategy_id == strategy.id,
                            StrategyPerformanceDaily.date == today,
                            StrategyPerformanceDaily.paper.is_(paper_flag),
                        )
                    ).scalar_one_or_none()
                    if existing:
                        for k, v in stats.items():
                            setattr(existing, k, v)
                        existing.computed_at = datetime.utcnow()
                    else:
                        db.add(StrategyPerformanceDaily(
                            strategy_id=strategy.id, date=today, paper=paper_flag, **stats
                        ))
                    computed += 1

            db.commit()
            job_run.status = "success"
            job_run.finished_at = datetime.utcnow()
            job_run.items_processed = computed
            db.commit()
        except Exception as e:
            db.rollback()
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details = {**(job_run.details or {}), "error": str(e)}
            db.commit()
            raise

    logger.info("strategy_performance: %d snapshots for %s", computed, today)
    return {"task": "compute_strategy_performance", "snapshots": computed, "date": today.isoformat()}
