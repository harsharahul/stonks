"""Stonks-vendored stub for ``tradingagents.dataflows.interface``.

Upstream defines ``route_to_vendor(method, *args, **kwargs)`` which dispatches
get_stock_data / get_indicators / get_fundamentals / get_news etc. to a
vendor-specific implementation (yfinance or Alpha Vantage), with rate-limit
fallback.

Stonks replaces all those vendor implementations with DB-backed adapters in
``app.agents.adapters.tools``. This stub forwards the same method names to
those adapters so vendored upstream tool wrappers (e.g.
``app.agents.tradingagents.agents.utils.core_stock_tools.get_stock_data``) keep
working unmodified: they call ``route_to_vendor("get_stock_data", ...)``,
which lands in our adapter.

If a method is invoked that we haven't implemented, returns a deterministic
"not available" stub-string so downstream prompts never see ``None`` /
``""``. This is the missing-data fallback specified in the plan.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_NOT_AVAILABLE_TEMPLATE = (
    "Data not available for `{method}({args})` in this environment. "
    "Phase 1 fallback: upstream agents should rely on the analyst's narrative "
    "and the per-ticker StockKnowledge context window."
)


def _format_args(args: tuple, kwargs: dict) -> str:
    parts = [repr(a) for a in args]
    parts.extend(f"{k}={v!r}" for k, v in kwargs.items())
    return ", ".join(parts)


def route_to_vendor(method: str, *args: Any, **kwargs: Any) -> str:
    """Dispatch upstream tool calls to Stonks adapters.

    Lazy-imports the adapter module so that simply importing this stub does
    not pull in DB / settings / SQLAlchemy machinery. The first invocation
    pays the import cost; subsequent calls are direct function lookups.
    """
    try:
        from app.agents.adapters import tools as stonks_tools
    except Exception as exc:
        logger.warning(
            "route_to_vendor: Stonks adapters import failed (%s); returning not-available stub",
            exc,
        )
        return _NOT_AVAILABLE_TEMPLATE.format(method=method, args=_format_args(args, kwargs))

    impl = getattr(stonks_tools, f"adapter_{method}", None) or getattr(stonks_tools, method, None)
    if impl is None:
        logger.info(
            "route_to_vendor: no adapter implementation for %s: returning not-available stub",
            method,
        )
        return _NOT_AVAILABLE_TEMPLATE.format(method=method, args=_format_args(args, kwargs))

    try:
        return impl(*args, **kwargs)
    except Exception as exc:
        logger.warning(
            "route_to_vendor: %s raised %s; returning not-available stub",
            method, exc,
        )
        return _NOT_AVAILABLE_TEMPLATE.format(method=method, args=_format_args(args, kwargs))


# Upstream defines AlphaVantageRateLimitError at this level for a few try/except
# blocks. We don't need it but provide the symbol so any straggler import resolves.
class AlphaVantageRateLimitError(Exception):
    """Stub: Stonks doesn't use Alpha Vantage in the desk pipeline."""
