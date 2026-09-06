"""Per-user Alpaca client factory.

Unlike the single-account sibling implementation (module-level singleton
reading env vars), every client here is constructed from a specific
``UserBrokerAccount`` row with credentials decrypted just-in-time. A small
TTL cache avoids rebuilding clients on every request without holding
plaintext keys longer than the process already would.
"""
from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Dict, Optional, Tuple

from alpaca.trading.client import TradingClient

from app.models.user_broker_account import UserBrokerAccount
from app.services.broker.crypto import decrypt_credential

logger = logging.getLogger(__name__)

# account_id -> (client, expires_at_monotonic)
_CACHE: Dict[str, Tuple[TradingClient, float]] = {}
_CACHE_LOCK = Lock()
_CACHE_TTL_SECONDS = 300


def get_trading_client(account: UserBrokerAccount) -> TradingClient:
    """Build (or reuse) a TradingClient for this user's account."""
    cache_key = str(account.id)
    now = time.monotonic()

    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and cached[1] > now:
            return cached[0]

    client = TradingClient(
        api_key=decrypt_credential(account.api_key_encrypted),
        secret_key=decrypt_credential(account.secret_key_encrypted),
        paper=bool(account.paper),
    )

    with _CACHE_LOCK:
        _CACHE[cache_key] = (client, now + _CACHE_TTL_SECONDS)
    return client


def invalidate_client(account_id: str) -> None:
    """Drop a cached client (call on unlink or credential update)."""
    with _CACHE_LOCK:
        _CACHE.pop(str(account_id), None)


def verify_account(account: UserBrokerAccount) -> Optional[dict]:
    """Round-trip the credentials against Alpaca; return account info or None.

    Used at link time and for the /broker/account status endpoint. Never
    raises on auth errors: returns None so callers can surface a clean
    'invalid credentials' message without leaking SDK internals.
    """
    try:
        client = get_trading_client(account)
        acct = client.get_account()
        return {
            "account_number_masked": f"...{str(acct.account_number)[-4:]}" if acct.account_number else None,
            "status": str(acct.status),
            "currency": acct.currency,
            "cash": float(acct.cash) if acct.cash is not None else None,
            "portfolio_value": float(acct.portfolio_value) if acct.portfolio_value is not None else None,
            "buying_power": float(acct.buying_power) if acct.buying_power is not None else None,
            "equity": float(acct.equity) if acct.equity is not None else None,
            "daytrade_count": int(acct.daytrade_count) if acct.daytrade_count is not None else None,
            "pattern_day_trader": bool(acct.pattern_day_trader),
        }
    except Exception as exc:
        logger.warning("verify_account failed for account %s: %s", account.id, type(exc).__name__)
        invalidate_client(str(account.id))
        return None
