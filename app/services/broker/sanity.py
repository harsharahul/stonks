"""Pre-trade sanity gates.

Ported from the earlier project's broker layer (Apache
2.0) and adapted for multi-user Stonks:

- No module-level Alpaca client: the caller passes the per-user
  ``TradingClient`` so the asset check runs against the user's own account.
- Fail-open vs fail-closed is explicit: paper accounts tolerate unreachable
  data sources (warn + pass), live accounts REJECT when a gate cannot be
  evaluated. "Fix the signal, not the gate."
- Same conservative thresholds, env-tunable.

Every order Stonks submits must pass ``run_all_checks`` first.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── Tunables (env-overridable) ────────────────────────────────────────────────
MIN_PRICE = float(os.getenv("SANITY_MIN_PRICE", "1.0"))            # no sub-dollar stocks
MAX_PRICE = float(os.getenv("SANITY_MAX_PRICE", "5000.0"))         # avoid ultra-high priced
MIN_MARKET_CAP = float(os.getenv("SANITY_MIN_MARKET_CAP", "1e9"))  # $1B floor
MIN_AVG_VOLUME = float(os.getenv("SANITY_MIN_AVG_VOLUME", "500000"))
EARNINGS_PROXIMITY_DAYS = int(os.getenv("SANITY_EARNINGS_PROXIMITY_DAYS", "2"))
_SANITY_CACHE_TTL = int(os.getenv("SANITY_CACHE_TTL", "900"))      # 15 min

ALLOWED_EXCHANGES = {"NYSE", "NASDAQ", "AMEX", "ARCA", "BATS"}

# Leveraged / inverse ETFs decay over multi-day holds, blocked outright.
LEVERAGED_ETF_BLOCKLIST = {
    "TQQQ", "SQQQ", "SPXL", "SPXS", "TNA", "TZA", "SOXL", "SOXS",
    "UPRO", "SPXU", "UDOW", "SDOW", "FAS", "FAZ", "LABU", "LABD",
    "TMF", "TMV", "UVXY", "SVXY", "VXX",
    "NUGT", "DUST", "JNUG", "JDST", "GUSH", "DRIP",
    "YINN", "YANG", "DPST", "WEBL", "WEBS",
}

# Index/FX symbols that leak through scrapers but cannot be ordered.
NON_TRADEABLE_BLOCKLIST = {
    "SPX", "NDX", "DJX", "RUT", "VIX",
    "USD", "EUR", "JPY", "GBP",
}

# ticker -> (result_dict, monotonic_ts)
_sanity_cache: Dict[str, tuple] = {}


def _cache_get(ticker: str) -> Optional[Dict]:
    entry = _sanity_cache.get(ticker)
    if entry and (time.monotonic() - entry[1]) < _SANITY_CACHE_TTL:
        return entry[0]
    return None


def _cache_set(ticker: str, result: Dict) -> None:
    _sanity_cache[ticker] = (result, time.monotonic())


def _gate_unavailable(reason: str, *, live: bool) -> Dict:
    """Uniform fail-open (paper) / fail-closed (live) behavior."""
    if live:
        return {"ok": False, "reason": f"gate_unavailable_live:{reason}"}
    return {"ok": True, "warning": reason}


def check_ticker(ticker: Optional[str]) -> Dict:
    """Bare-minimum: present, alphabetic, sane length, not blocklisted."""
    if not ticker:
        return {"ok": False, "reason": "no_ticker"}
    t = ticker.upper().strip()
    if not t.isalpha():
        return {"ok": False, "reason": f"non_alpha_ticker:{t}"}
    if len(t) > 5:
        return {"ok": False, "reason": f"bad_ticker_length:{t}"}
    if t in NON_TRADEABLE_BLOCKLIST:
        return {"ok": False, "reason": f"non_tradeable:{t}"}
    if t in LEVERAGED_ETF_BLOCKLIST:
        return {"ok": False, "reason": f"leveraged_etf_blocked:{t}"}
    return {"ok": True, "ticker": t}


def check_alpaca_asset(ticker: str, trading_client, *, live: bool) -> Dict:
    """Asset must be tradable, active, and listed on a major exchange."""
    try:
        asset = trading_client.get_asset(ticker)

        if not getattr(asset, "tradable", True):
            return {"ok": False, "reason": f"alpaca_not_tradable:{ticker}"}

        raw_status = getattr(asset, "status", None)
        status_str = getattr(raw_status, "value", str(raw_status)).lower()
        if status_str not in ("active", "assetstatus.active"):
            return {"ok": False, "reason": f"alpaca_not_active:{raw_status}"}

        raw_exchange = getattr(asset, "exchange", None)
        exchange = getattr(raw_exchange, "value", str(raw_exchange)).upper()
        if "." in exchange:
            exchange = exchange.split(".")[-1]
        if exchange and exchange not in ALLOWED_EXCHANGES:
            return {"ok": False, "reason": f"otc_or_pink_sheet:{exchange}"}
        return {"ok": True, "exchange": exchange}
    except Exception as e:
        logger.warning("Alpaca asset check failed for %s: %s", ticker, e)
        return _gate_unavailable(f"alpaca_unavailable:{type(e).__name__}", live=live)


def fetch_market_context(ticker: str) -> Dict:
    """Price / market cap / avg volume via yfinance (already a project dep)."""
    try:
        import yfinance as yf

        t = yf.Ticker(ticker)
        info = t.info or {}
        hist = t.history(period="20d")
        avg_vol = float(hist["Volume"].mean()) if not hist.empty else 0
        last_price = float(hist["Close"].iloc[-1]) if not hist.empty else 0
        return {
            "last_price": last_price,
            "market_cap": float(info.get("marketCap") or 0),
            "avg_volume_20d": avg_vol,
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange") or info.get("fullExchangeName"),
            "quote_type": info.get("quoteType"),
        }
    except Exception as e:
        logger.warning("market_context fetch failed for %s: %s", ticker, e)
        return {}


def passes_liquidity_and_size_check(ctx: Dict, *, live: bool) -> Dict:
    """Liquidity / market-cap / price gates.

    Unlike the upstream version, "no market data at all" REJECTS for live
    accounts (the upstream fail-open here was flagged RED in its own risk
    review: a delisted ticker sails through every gate).
    """
    if not ctx:
        return _gate_unavailable("no_market_data", live=live) if not live else {
            "ok": False, "reason": "no_market_data",
        }

    last_price = ctx.get("last_price") or 0
    market_cap = ctx.get("market_cap") or 0
    avg_vol = ctx.get("avg_volume_20d") or 0
    currency = ctx.get("currency") or "USD"

    if last_price <= 0 and market_cap <= 0 and avg_vol <= 0:
        return {"ok": False, "reason": "no_market_data"}

    if currency != "USD":
        return {"ok": False, "reason": f"non_usd:{currency}"}

    if 0 < last_price < MIN_PRICE:
        return {"ok": False, "reason": f"penny_stock:${last_price:.2f}<${MIN_PRICE}"}

    if last_price > MAX_PRICE:
        return {"ok": False, "reason": f"price_too_high:${last_price:.2f}>${MAX_PRICE}"}

    if 0 < market_cap < MIN_MARKET_CAP:
        return {"ok": False, "reason": f"market_cap_too_small:${market_cap/1e6:.0f}M"}

    if 0 < avg_vol < MIN_AVG_VOLUME:
        return {"ok": False, "reason": f"illiquid:{avg_vol:.0f}<{MIN_AVG_VOLUME:.0f}"}

    return {"ok": True}


def check_earnings_proximity(ticker: str, *, live: bool) -> Dict:
    """Skip trades within EARNINGS_PROXIMITY_DAYS of an earnings date."""
    try:
        import yfinance as yf

        cal = yf.Ticker(ticker).calendar
        if cal is None:
            return {"ok": True}
        earnings_date = None
        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
            if isinstance(earnings_date, list) and earnings_date:
                earnings_date = earnings_date[0]
        else:
            try:
                if "Earnings Date" in getattr(cal, "columns", []):
                    earnings_date = cal["Earnings Date"].iloc[0]
                elif "Earnings Date" in getattr(cal, "index", []):
                    earnings_date = cal.loc["Earnings Date"].iloc[0]
            except Exception:
                pass
        if earnings_date is None:
            return {"ok": True}
        if isinstance(earnings_date, str):
            earnings_date = datetime.fromisoformat(earnings_date.replace("Z", "+00:00"))
        elif hasattr(earnings_date, "to_pydatetime"):
            earnings_date = earnings_date.to_pydatetime()
        if not isinstance(earnings_date, datetime):
            return {"ok": True}
        if hasattr(earnings_date, "date") and not isinstance(earnings_date, datetime):
            return {"ok": True}
        now = datetime.now(timezone.utc)
        if earnings_date.tzinfo is None:
            earnings_date = earnings_date.replace(tzinfo=timezone.utc)
        days_until = (earnings_date - now).days
        if 0 <= days_until <= EARNINGS_PROXIMITY_DAYS:
            return {"ok": False, "reason": f"earnings_in_{days_until}_days"}
        return {"ok": True}
    except Exception as e:
        logger.warning("Earnings proximity check failed for %s: %s", ticker, e)
        return _gate_unavailable(f"earnings_check_failed:{type(e).__name__}", live=live)


def run_all_checks(
    ticker: Optional[str],
    trading_client,
    *,
    live: bool = False,
    use_cache: bool = True,
) -> Dict:
    """Full pre-trade sanity pass for one ticker against one user's account.

    Returns ``{"ok": True, "ticker": ..., "context": {...}}`` on pass or
    ``{"ok": False, "reason": ...}`` on fail. Cached per-ticker for 15 min;
    pass ``use_cache=False`` immediately before actual order submission.
    Live accounts use fail-closed semantics on every external gate.
    """
    base = check_ticker(ticker)
    if not base["ok"]:
        return base
    t = base["ticker"]

    cache_key = f"{t}:{'live' if live else 'paper'}"
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    alpaca_check = check_alpaca_asset(t, trading_client, live=live)
    if not alpaca_check["ok"]:
        result = {**alpaca_check, "ticker": t}
        _cache_set(cache_key, result)
        return result

    ctx = fetch_market_context(t)
    liq = passes_liquidity_and_size_check(ctx, live=live)
    if not liq["ok"]:
        result = {**liq, "ticker": t, "context": ctx}
        _cache_set(cache_key, result)
        return result

    earnings = check_earnings_proximity(t, live=live)
    if not earnings["ok"]:
        result = {**earnings, "ticker": t, "context": ctx}
        _cache_set(cache_key, result)
        return result

    result = {"ok": True, "ticker": t, "context": ctx}
    _cache_set(cache_key, result)
    return result
