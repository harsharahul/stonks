"""Order construction + submission for per-user Alpaca accounts.

Built for many users sharing one process:

- No module-level env constants: everything arrives as explicit arguments
  (client, account, order intent) so two users' orders can never share state.
- Idempotent submits: every order carries a deterministic ``client_order_id``
  persisted BEFORE submission: a retried call can't double-place because
  Alpaca rejects duplicate client order IDs and our ledger has a unique
  constraint on it.
- v1 is strictly "user clicked confirm": no auto-execute path. Sizing
  helpers are provided for the UI's "suggested size" but the user's explicit
  qty/notional always wins.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import (
    LimitOrderRequest,
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

logger = logging.getLogger(__name__)

# Default risk knobs for SUGGESTED sizing (the user can override in the ticket).
DEFAULT_RISK_PER_TRADE_PCT = 0.02   # risk 2% of equity per trade
DEFAULT_MAX_POSITION_PCT = 0.05     # never suggest >5% of equity in one name
DEFAULT_STOP_LOSS_PCT = 0.05
DEFAULT_TAKE_PROFIT_PCT = 0.10


def make_client_order_id(user_id: Any) -> str:
    """Deterministic-enough, collision-free, user-scoped client order id."""
    return f"stonks-{str(user_id)[:8]}-{uuid.uuid4().hex[:16]}"


def is_market_open(client: TradingClient) -> bool:
    try:
        clock = client.get_clock()
        return bool(clock.is_open)
    except Exception as e:
        logger.warning("market clock check failed: %s", e)
        return False


def suggest_position_size(
    *,
    equity: float,
    entry_price: float,
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
    risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
    max_position_pct: float = DEFAULT_MAX_POSITION_PCT,
) -> Dict[str, float]:
    """Risk-budgeted suggested qty: min(risk-based size, hard position cap)."""
    if equity <= 0 or entry_price <= 0:
        return {"qty": 0, "position_value": 0.0}
    risk_amount = equity * risk_per_trade_pct
    risk_based_value = risk_amount / stop_loss_pct
    capped_value = min(risk_based_value, equity * max_position_pct)
    qty = int(capped_value / entry_price)
    return {"qty": max(qty, 0), "position_value": round(qty * entry_price, 2)}


def build_order_request(
    *,
    symbol: str,
    side: str,
    qty: Optional[float],
    notional: Optional[float],
    order_type: str,
    limit_price: Optional[float],
    time_in_force: str,
    client_order_id: str,
    stop_loss_price: Optional[float] = None,
    take_profit_price: Optional[float] = None,
):
    """Construct the alpaca-py request object for a (possibly bracket) order."""
    order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
    tif = TimeInForce.DAY if time_in_force == "day" else TimeInForce.GTC

    common: Dict[str, Any] = {
        "symbol": symbol,
        "side": order_side,
        "time_in_force": tif,
        "client_order_id": client_order_id,
    }
    if qty is not None:
        common["qty"] = qty
    elif notional is not None:
        common["notional"] = round(float(notional), 2)
    else:
        raise ValueError("either qty or notional is required")

    # Bracket legs (only valid with qty on Alpaca; the endpoint enforces this)
    if stop_loss_price is not None or take_profit_price is not None:
        common["order_class"] = "bracket"
        if stop_loss_price is not None:
            common["stop_loss"] = StopLossRequest(stop_price=round(stop_loss_price, 2))
        if take_profit_price is not None:
            common["take_profit"] = TakeProfitRequest(limit_price=round(take_profit_price, 2))

    if order_type == "limit":
        if limit_price is None:
            raise ValueError("limit orders require limit_price")
        return LimitOrderRequest(limit_price=round(limit_price, 2), **common)
    return MarketOrderRequest(**common)


def submit_order(client: TradingClient, order_request) -> Dict[str, Any]:
    """Submit and normalize the broker response to a plain dict."""
    order = client.submit_order(order_data=order_request)
    return {
        "alpaca_order_id": str(order.id),
        "status": str(getattr(order.status, "value", order.status)),
        "symbol": order.symbol,
        "qty": float(order.qty) if order.qty is not None else None,
        "notional": float(order.notional) if order.notional is not None else None,
        "filled_qty": float(order.filled_qty) if order.filled_qty is not None else None,
        "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else datetime.utcnow().isoformat(),
        "client_order_id": order.client_order_id,
    }


def sync_order_status(client: TradingClient, alpaca_order_id: str) -> Optional[Dict[str, Any]]:
    """Fetch current order state from Alpaca for ledger reconciliation."""
    try:
        order = client.get_order_by_id(alpaca_order_id)
        return {
            "status": str(getattr(order.status, "value", order.status)),
            "filled_qty": float(order.filled_qty) if order.filled_qty is not None else None,
            "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        }
    except Exception as e:
        logger.warning("sync_order_status failed for %s: %s", alpaca_order_id, e)
        return None
