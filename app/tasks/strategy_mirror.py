"""Paper-auto copy engine: mirror a strategy's trade to opted-in followers.

Dispatched per origin order from the broker endpoint (not scheduled). The
legal/safety posture is enforced in code, not convention:

- PAPER ONLY. A follower is mirrored iff their linked account has
  ``paper=True`` AND ``auto_execute=True`` AND ``copy_mode='paper_auto'``.
  Live accounts are skipped unconditionally — live auto-copy requires RIA
  registration or a BD/RIA partner (In re Weiss Research; Autopilot
  Advisers precedent). Do not "fix" this without that paperwork.
- IDEMPOTENT. The mirror's client_order_id is deterministic per
  (follower, origin order): a redelivered task can't double-place — Alpaca
  rejects duplicate client order ids and the ledger has a unique constraint.
- INDEPENDENT SIZING. Followers are sized from their OWN equity and
  risk_config (never the leader's amounts, which are private): buys use
  ``copy_position_pct`` of equity (default 2%, capped 10%); sells close
  whatever the follower's mirrored position in that symbol is.
- Mirrored orders carry source='copy' + source_ref=<origin order id> and NO
  strategy_id — follower fills must never pollute the leader's verified
  track record or public trade feed.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from celery import shared_task
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.broker_order import BrokerOrder
from app.models.strategy import Strategy
from app.models.strategy_follow import StrategyFollow
from app.models.user_broker_account import UserBrokerAccount

logger = logging.getLogger(__name__)

DEFAULT_COPY_POSITION_PCT = 0.02
MAX_COPY_POSITION_PCT = 0.10


def mirror_client_order_id(follower_user_id, origin_order_id) -> str:
    """Deterministic per (follower, origin) — the idempotency key."""
    return f"stonks-copy-{str(follower_user_id)[:8]}-{str(origin_order_id).replace('-', '')[:16]}"


def copy_notional_for(equity: float, risk_config: Optional[Dict]) -> float:
    """Follower buy size: pct of their own equity, clamped to a hard cap."""
    pct = DEFAULT_COPY_POSITION_PCT
    if risk_config and "copy_position_pct" in risk_config:
        try:
            pct = float(risk_config["copy_position_pct"])
        except (TypeError, ValueError):
            pct = DEFAULT_COPY_POSITION_PCT
    pct = max(0.0, min(pct, MAX_COPY_POSITION_PCT))
    return round(max(equity, 0.0) * pct, 2)


def open_mirrored_qty(db, follower_user_id, origin_strategy_id, symbol: str) -> float:
    """Follower's net open quantity from prior mirrors of this strategy+symbol."""
    rows = db.execute(
        select(BrokerOrder).where(
            BrokerOrder.user_id == follower_user_id,
            BrokerOrder.symbol == symbol,
            BrokerOrder.source == "copy",
            BrokerOrder.status.in_(["filled", "partially_filled", "submitted"]),
        )
    ).scalars().all()
    net = 0.0
    for o in rows:
        qty = float(o.filled_qty or o.qty or 0)
        net += qty if o.side == "buy" else -qty
    return max(net, 0.0)


@shared_task(bind=True, queue="compute", acks_late=True, reject_on_worker_lost=True)
def mirror_strategy_trade_task(self, origin_order_id: str) -> Dict:
    """Mirror one strategy-tagged order to all paper_auto followers."""
    if settings.BROKER_TRADING_HALTED:
        return {"task": "mirror_strategy_trade", "skipped": "trading_halted"}

    # Imports deferred: alpaca client construction pulls broker deps.
    from app.services.broker.client import get_trading_client
    from app.services.broker.execution import build_order_request, submit_order
    from app.services.broker.sanity import run_all_checks

    results: List[Dict] = []
    with SessionLocal() as db:
        origin = db.get(BrokerOrder, origin_order_id)
        if origin is None or origin.strategy_id is None:
            return {"task": "mirror_strategy_trade", "skipped": "no_origin_or_strategy"}
        if origin.side not in ("buy", "sell") or origin.status in ("rejected", "failed", "canceled"):
            return {"task": "mirror_strategy_trade", "skipped": f"origin_{origin.status}"}
        strategy = db.get(Strategy, origin.strategy_id)
        if strategy is None or not strategy.is_active:
            return {"task": "mirror_strategy_trade", "skipped": "strategy_inactive"}

        follows = db.execute(
            select(StrategyFollow).where(
                StrategyFollow.strategy_id == strategy.id,
                StrategyFollow.copy_mode == "paper_auto",
            )
        ).scalars().all()

        for follow in follows:
            outcome = {"follower": str(follow.follower_user_id)[:8]}
            try:
                account = db.execute(
                    select(UserBrokerAccount).where(
                        UserBrokerAccount.user_id == follow.follower_user_id,
                        UserBrokerAccount.is_active.is_(True),
                    )
                ).scalar_one_or_none()
                # The hard gate: paper + explicit auto_execute opt-in, nothing else.
                if account is None or not account.paper or not account.auto_execute:
                    outcome["status"] = "skipped_account_gate"
                    results.append(outcome)
                    continue

                client_order_id = mirror_client_order_id(follow.follower_user_id, origin.id)
                existing = db.execute(
                    select(BrokerOrder).where(BrokerOrder.client_order_id == client_order_id)
                ).scalar_one_or_none()
                if existing is not None:
                    outcome["status"] = "already_mirrored"
                    results.append(outcome)
                    continue

                client = get_trading_client(account)
                sanity = run_all_checks(origin.symbol, client, live=False, use_cache=True)
                if not sanity.get("ok"):
                    outcome["status"] = f"sanity_rejected:{sanity.get('reason')}"
                    results.append(outcome)
                    continue

                qty = None
                notional = None
                if origin.side == "buy":
                    acct = client.get_account()
                    notional = copy_notional_for(float(acct.equity or 0), follow.risk_config)
                    if notional < 1.0:
                        outcome["status"] = "skipped_zero_notional"
                        results.append(outcome)
                        continue
                else:
                    qty = open_mirrored_qty(db, follow.follower_user_id, strategy.id, origin.symbol)
                    if qty <= 0:
                        outcome["status"] = "skipped_no_position"
                        results.append(outcome)
                        continue

                ledger = BrokerOrder(
                    user_id=follow.follower_user_id,
                    broker_account_id=account.id,
                    symbol=origin.symbol,
                    side=origin.side,
                    qty=qty,
                    notional=notional,
                    order_type="market",
                    time_in_force="day",
                    status="pending",
                    paper=True,
                    client_order_id=client_order_id,
                    source="copy",
                    source_ref=str(origin.id),
                    strategy_id=None,  # never pollute the leader's record
                )
                db.add(ledger)
                db.commit()  # persist BEFORE submit (idempotent retries)

                order_request = build_order_request(
                    symbol=origin.symbol,
                    side=origin.side,
                    qty=qty,
                    notional=notional,
                    order_type="market",
                    limit_price=None,
                    time_in_force="day",
                    client_order_id=client_order_id,
                )
                result = submit_order(client, order_request)
                ledger.status = result["status"]
                ledger.alpaca_order_id = result["alpaca_order_id"]
                ledger.filled_qty = result["filled_qty"]
                ledger.filled_avg_price = result["filled_avg_price"]
                ledger.submitted_at = datetime.utcnow()
                db.commit()
                outcome["status"] = f"mirrored:{ledger.status}"
            except Exception as e:
                db.rollback()
                logger.warning("mirror failed for follower %s: %s", follow.follower_user_id, e)
                outcome["status"] = f"error:{type(e).__name__}"
            results.append(outcome)

    mirrored = sum(1 for r in results if str(r.get("status", "")).startswith("mirrored"))
    logger.info(
        "mirror_strategy_trade: origin=%s strategy=%s followers=%d mirrored=%d",
        origin_order_id, strategy.slug if strategy else "?", len(results), mirrored,
    )
    return {"task": "mirror_strategy_trade", "origin": str(origin_order_id), "results": results}
