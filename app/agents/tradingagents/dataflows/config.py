"""Stonks-vendored stub for ``tradingagents.dataflows.config``.

Upstream's dataflows layer is a vendor-routing module that fetches data from
yfinance / Alpha Vantage. Stonks replaces it entirely with adapters in
``app.agents.adapters.tools`` that read from our own database. This stub
preserves the import surface (``get_config`` / ``set_config``) so vendored
agent modules that import from here continue to load, but the config it
holds is just our desk config dict.

The real configuration source of truth lives in
``app.agents.desk_config.DESK_CONFIG`` and ``app.core.config.settings``.
"""
from __future__ import annotations

from typing import Any, Dict

_active_config: Dict[str, Any] = {}


def set_config(config: Dict[str, Any]) -> None:
    """Set the active config dict. Called by ``TradingAgentsGraph.__init__``."""
    global _active_config
    _active_config = dict(config) if config else {}


def get_config() -> Dict[str, Any]:
    """Return the currently active config dict."""
    return _active_config
