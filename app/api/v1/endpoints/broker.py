"""Brokerage endpoints: link Alpaca account, portfolio, order placement.

All endpoints require an authenticated user. Credentials are encrypted at
rest and never returned after the initial link request. v1 safety posture:

- paper accounts by default; linking live requires `confirm_live: true`
- every live order placement requires `confirm_live: true` per order
- sanity gates run fresh (no cache) immediately before submission
- global halt: settings.BROKER_TRADING_HALTED rejects all order placement
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.broker_order import BrokerOrder
from app.models.strategy import Strategy
from app.models.user_broker_account import UserBrokerAccount
from app.services.broker.client import (
    get_trading_client,
    invalidate_client,
    verify_account,
)
from app.services.broker.crypto import BrokerCryptoError, encrypt_credential
from app.services.broker.execution import (
    build_order_request,
    is_market_open,
    make_client_order_id,
    submit_order,
    suggest_position_size,
    sync_order_status,
)
from app.services.broker.sanity import run_all_checks

logger = logging.getLogger(__name__)

router = APIRouter()

_SYMBOL_PATH = Path(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9.\-]+$")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LinkAccountRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=128)
    secret_key: str = Field(min_length=8, max_length=128)
    paper: bool = True
    # Explicit opt-in required to link a LIVE (real money) account.
    confirm_live: bool = False


class PlaceOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9.\-]+$")
    side: str = Field(pattern="^(buy|sell)$")
    qty: Optional[float] = Field(None, gt=0, le=1_000_000)
    notional: Optional[float] = Field(None, gt=0, le=10_000_000)
    order_type: str = Field("market", pattern="^(market|limit)$")
    limit_price: Optional[float] = Field(None, gt=0)
    time_in_force: str = Field("day", pattern="^(day|gtc)$")
    # Optional bracket protection (requires qty, not notional)
    stop_loss_price: Optional[float] = Field(None, gt=0)
    take_profit_price: Optional[float] = Field(None, gt=0)
    # Provenance: what drove this trade (audit trail)
    source: str = Field("manual", pattern="^(manual|desk|signal)$")
    source_ref: Optional[str] = Field(None, max_length=64)
    # Social layer: tag the order to one of the caller's strategies so it
    # appears in the strategy's public trade feed + verified track record.
    strategy_id: Optional[UUID] = None
    # Live-account orders must re-confirm per order.
    confirm_live: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_account_or_404(user, db: Session) -> UserBrokerAccount:
    account = (
        db.query(UserBrokerAccount)
        .filter(
            UserBrokerAccount.user_id == user.id,
            UserBrokerAccount.provider == "alpaca",
            UserBrokerAccount.is_active.is_(True),
        )
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=404,
            detail="No linked Alpaca account. Link one via POST /broker/account.",
        )
    return account


# ---------------------------------------------------------------------------
# Account lifecycle
# ---------------------------------------------------------------------------


@router.post("/account", status_code=201)
async def link_account(
    body: LinkAccountRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Link (or replace) the user's Alpaca account.

    Credentials are validated against Alpaca before being stored encrypted.
    Linking a live account requires confirm_live=true.
    """
    if not body.paper and not body.confirm_live:
        raise HTTPException(
            status_code=400,
            detail="Linking a LIVE account requires confirm_live=true. "
            "Strongly consider starting with a paper account.",
        )

    existing = (
        db.query(UserBrokerAccount)
        .filter(UserBrokerAccount.user_id == user.id, UserBrokerAccount.provider == "alpaca")
        .first()
    )

    try:
        api_key_enc = encrypt_credential(body.api_key)
        secret_key_enc = encrypt_credential(body.secret_key)
    except BrokerCryptoError as exc:
        logger.error("broker crypto unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Broker credential storage is not configured on this server.")

    if existing:
        existing.api_key_encrypted = api_key_enc
        existing.secret_key_encrypted = secret_key_enc
        existing.paper = body.paper
        existing.is_active = True
        account = existing
        invalidate_client(str(account.id))
    else:
        account = UserBrokerAccount(
            user_id=user.id,
            provider="alpaca",
            api_key_encrypted=api_key_enc,
            secret_key_encrypted=secret_key_enc,
            paper=body.paper,
        )
        db.add(account)

    db.flush()

    info = verify_account(account)
    if info is None:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Alpaca rejected these credentials (or the API is unreachable). "
            "Check the key pair and paper/live selection.",
        )

    account.account_label = info.get("account_number_masked")
    account.last_verified_at = datetime.utcnow()
    db.commit()

    return {"account": account.to_dict(), "broker_info": info}


@router.get("/account")
async def get_account(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Linked-account status + live equity/buying power from Alpaca."""
    account = _get_account_or_404(user, db)
    info = verify_account(account)
    if info is not None:
        account.last_verified_at = datetime.utcnow()
        db.commit()
    return {
        "account": account.to_dict(),
        "broker_info": info,  # None ⇒ credentials invalid / Alpaca unreachable
        "market_open": is_market_open(get_trading_client(account)) if info else None,
        "trading_halted": settings.BROKER_TRADING_HALTED,
    }


@router.delete("/account")
async def unlink_account(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Unlink the user's Alpaca account (orders history is preserved)."""
    account = _get_account_or_404(user, db)
    invalidate_client(str(account.id))
    account.is_active = False
    db.commit()
    return {"status": "unlinked"}


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


@router.get("/positions")
async def get_positions(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Current open positions from Alpaca."""
    account = _get_account_or_404(user, db)
    try:
        client = get_trading_client(account)
        positions = client.get_all_positions()
    except BrokerCryptoError:
        raise HTTPException(status_code=503, detail="Broker credential storage is not configured.")
    except Exception as exc:
        logger.warning("get_positions failed for user %s: %s", user.id, type(exc).__name__)
        raise HTTPException(status_code=502, detail="Could not fetch positions from Alpaca.")

    def _pos(p) -> dict:
        return {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "side": str(getattr(p.side, "value", p.side)),
            "avg_entry_price": float(p.avg_entry_price) if p.avg_entry_price else None,
            "current_price": float(p.current_price) if p.current_price else None,
            "market_value": float(p.market_value) if p.market_value else None,
            "unrealized_pl": float(p.unrealized_pl) if p.unrealized_pl else None,
            "unrealized_plpc": float(p.unrealized_plpc) if p.unrealized_plpc else None,
        }

    return {"positions": [_pos(p) for p in positions], "count": len(positions)}


@router.get("/orders")
async def list_orders(
    limit: int = 50,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Order history from the local ledger, with live status sync for open orders."""
    account = _get_account_or_404(user, db)
    orders = (
        db.query(BrokerOrder)
        .filter(BrokerOrder.user_id == user.id)
        .order_by(BrokerOrder.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )

    # Reconcile non-terminal orders against Alpaca
    open_statuses = {"pending", "submitted", "partially_filled", "accepted", "new"}
    client = None
    for order in orders:
        if order.status in open_statuses and order.alpaca_order_id:
            if client is None:
                try:
                    client = get_trading_client(account)
                except Exception:
                    break
            synced = sync_order_status(client, order.alpaca_order_id)
            if synced:
                order.status = synced["status"]
                order.filled_qty = synced["filled_qty"]
                order.filled_avg_price = synced["filled_avg_price"]
                if synced.get("filled_at"):
                    order.filled_at = datetime.fromisoformat(synced["filled_at"])
    db.commit()

    return {"orders": [o.to_dict() for o in orders], "count": len(orders)}


# ---------------------------------------------------------------------------
# Order placement
# ---------------------------------------------------------------------------


@router.post("/orders", status_code=201)
async def place_order(
    body: PlaceOrderRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Place an order on the user's linked Alpaca account.

    Pipeline: global halt → account → live re-confirmation → fresh sanity
    gates → persist pending ledger row (idempotent client_order_id) →
    submit → update ledger.
    """
    if settings.BROKER_TRADING_HALTED:
        raise HTTPException(status_code=503, detail="Trading is globally halted by the administrator.")

    if body.qty is None and body.notional is None:
        raise HTTPException(status_code=400, detail="Provide qty or notional.")
    if body.qty is not None and body.notional is not None:
        raise HTTPException(status_code=400, detail="Provide qty OR notional, not both.")
    if (body.stop_loss_price or body.take_profit_price) and body.qty is None:
        raise HTTPException(status_code=400, detail="Bracket orders require qty (not notional).")
    if body.order_type == "limit" and body.limit_price is None:
        raise HTTPException(status_code=400, detail="Limit orders require limit_price.")

    account = _get_account_or_404(user, db)
    is_live = not account.paper
    if is_live and not body.confirm_live:
        raise HTTPException(
            status_code=400,
            detail="This is a LIVE account — re-confirm with confirm_live=true.",
        )

    try:
        client = get_trading_client(account)
    except BrokerCryptoError:
        raise HTTPException(status_code=503, detail="Broker credential storage is not configured.")

    # Fresh sanity pass (no cache) right before submission.
    symbol = body.symbol.upper()
    sanity = run_all_checks(symbol, client, live=is_live, use_cache=False)
    if not sanity.get("ok"):
        raise HTTPException(
            status_code=422,
            detail=f"Pre-trade check rejected {symbol}: {sanity.get('reason', 'unknown')}",
        )

    # Strategy tagging: must be the caller's own active strategy. Desk-driven
    # orders auto-attach to the platform's desk strategy when one exists.
    strategy = None
    if body.strategy_id is not None:
        strategy = (
            db.query(Strategy)
            .filter(Strategy.id == body.strategy_id, Strategy.owner_user_id == user.id, Strategy.is_active.is_(True))
            .first()
        )
        if strategy is None:
            raise HTTPException(status_code=404, detail="Strategy not found (must be your own, active strategy).")
    elif body.source == "desk":
        strategy = db.query(Strategy).filter(Strategy.kind == "desk", Strategy.is_active.is_(True)).first()

    client_order_id = make_client_order_id(user.id)
    ledger = BrokerOrder(
        user_id=user.id,
        broker_account_id=account.id,
        symbol=symbol,
        side=body.side,
        qty=body.qty,
        notional=body.notional,
        order_type=body.order_type,
        time_in_force=body.time_in_force,
        limit_price=body.limit_price,
        stop_loss_price=body.stop_loss_price,
        take_profit_price=body.take_profit_price,
        status="pending",
        paper=account.paper,
        client_order_id=client_order_id,
        source=body.source,
        source_ref=body.source_ref,
        strategy_id=strategy.id if strategy is not None else None,
    )
    db.add(ledger)
    db.commit()  # persist BEFORE submit — submit retries stay idempotent

    try:
        order_request = build_order_request(
            symbol=symbol,
            side=body.side,
            qty=body.qty,
            notional=body.notional,
            order_type=body.order_type,
            limit_price=body.limit_price,
            time_in_force=body.time_in_force,
            client_order_id=client_order_id,
            stop_loss_price=body.stop_loss_price,
            take_profit_price=body.take_profit_price,
        )
        result = submit_order(client, order_request)
    except ValueError as exc:
        ledger.status = "failed"
        ledger.error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        ledger.status = "failed"
        ledger.error = f"{type(exc).__name__}: {exc}"
        db.commit()
        logger.warning("order submit failed for user %s %s %s: %s", user.id, body.side, symbol, exc)
        raise HTTPException(status_code=502, detail="Alpaca rejected the order or is unreachable. See order history for details.")

    ledger.status = result["status"]
    ledger.alpaca_order_id = result["alpaca_order_id"]
    ledger.filled_qty = result["filled_qty"]
    ledger.filled_avg_price = result["filled_avg_price"]
    ledger.submitted_at = datetime.utcnow()
    db.commit()

    logger.info(
        "order placed: user=%s %s %s qty=%s notional=%s paper=%s status=%s",
        user.id, body.side, symbol, body.qty, body.notional, account.paper, ledger.status,
    )

    # Social layer: publish public-strategy trades to the live alerts channel.
    # Privacy: side/symbol/strategy only — never qty, notional, or identities.
    if strategy is not None and strategy.visibility == "public":
        try:
            from app.services.websocket_manager import event_broadcaster

            await event_broadcaster.broadcast_alert({
                "alert_type": "strategy_trade",
                "strategy_slug": strategy.slug,
                "strategy_name": strategy.name,
                "symbol": symbol,
                "side": body.side,
                "paper": account.paper,
                "message": f"{strategy.name}: {body.side.upper()} {symbol}",
            })
        except Exception:
            logger.warning("strategy trade broadcast failed (non-fatal)", exc_info=True)

    return {"order": ledger.to_dict(), "market_open": is_market_open(client)}


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel an open order."""
    order = (
        db.query(BrokerOrder)
        .filter(BrokerOrder.id == order_id, BrokerOrder.user_id == user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if not order.alpaca_order_id:
        raise HTTPException(status_code=400, detail="Order was never submitted to Alpaca.")

    account = _get_account_or_404(user, db)
    try:
        client = get_trading_client(account)
        client.cancel_order_by_id(order.alpaca_order_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cancel failed: {type(exc).__name__}")

    synced = sync_order_status(client, order.alpaca_order_id)
    if synced:
        order.status = synced["status"]
    else:
        order.status = "canceled"
    db.commit()
    return {"order": order.to_dict()}


# ---------------------------------------------------------------------------
# Sizing helper for the trade ticket UI
# ---------------------------------------------------------------------------


@router.get("/sizing/{symbol}")
async def get_suggested_size(
    symbol: str = _SYMBOL_PATH,
    stop_loss_pct: float = 0.05,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Risk-budgeted suggested position size for the trade ticket."""
    account = _get_account_or_404(user, db)
    info = verify_account(account)
    if not info or not info.get("equity"):
        raise HTTPException(status_code=502, detail="Could not fetch account equity.")

    # Latest price from our own price table (no extra Alpaca data subscription needed)
    from app.agents.adapters.tools import fetch_daily_bars
    from datetime import date, timedelta

    bars = fetch_daily_bars(symbol.upper(), date.today() - timedelta(days=7), date.today())
    if not bars:
        raise HTTPException(status_code=404, detail=f"No recent price for {symbol.upper()}.")
    entry_price = bars[-1].close

    suggestion = suggest_position_size(
        equity=info["equity"],
        entry_price=entry_price,
        stop_loss_pct=max(min(stop_loss_pct, 0.5), 0.005),
    )
    return {
        "symbol": symbol.upper(),
        "entry_price": entry_price,
        "equity": info["equity"],
        "suggested_qty": suggestion["qty"],
        "suggested_value": suggestion["position_value"],
        "suggested_stop_loss": round(entry_price * (1 - stop_loss_pct), 2),
        "suggested_take_profit": round(entry_price * 1.10, 2),
    }
