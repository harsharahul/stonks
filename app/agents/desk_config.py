"""Stonks AI Trading Desk configuration.

Single source of truth for desk-pipeline knobs. Replaces upstream
``tradingagents/default_config.py``. Keys mirror upstream's where vendored
code reads them (``data_cache_dir``, ``results_dir``, ``llm_provider``,
``deep_think_llm``, ``quick_think_llm``, ``backend_url``,
``max_debate_rounds``, ``max_risk_discuss_rounds``,
``checkpoint_enabled``, ``output_language``,
``memory_log_path``, ``memory_log_max_entries``, ``data_vendors``,
``tool_vendors``) so vendored agents continue to work without edits.

Stonks values:
- LLMs come from ``app.llm.ollama_client`` (qwen3:14b on Mac Studio)
- Memory log is Postgres-backed (``app.agents.adapters.memory_log``);
  ``memory_log_path`` is unused but populated for upstream compat
- Cache/results dirs default to /tmp inside containers — desk runs persist
  to Postgres, not disk
- Phase 1: full pipeline runs (max_debate_rounds=1, max_risk_discuss_rounds=1)
  but UI hides debate/risk panels until Phase 2 (V0.2 finding)
"""
from __future__ import annotations

import os
import tempfile
from typing import Any, Dict

from app.core.config import settings

_DEFAULT_CACHE = os.path.join(tempfile.gettempdir(), "stonks-desk-cache")
_DEFAULT_RESULTS = os.path.join(tempfile.gettempdir(), "stonks-desk-results")


# Phase 1 desk config. Keep this dict in sync with upstream's expected keys
# so the vendored ``trading_graph.py`` can pull values without surprise.
DESK_CONFIG: Dict[str, Any] = {
    # Filesystem (mostly unused — Stonks persists to Postgres). Upstream's
    # __init__ does os.makedirs on these, so they must be writable paths.
    "project_dir": os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "results_dir": _DEFAULT_RESULTS,
    "data_cache_dir": _DEFAULT_CACHE,

    # Memory log (unused — PostgresMemoryLog overrides) but populated for compat.
    "memory_log_path": os.path.join(_DEFAULT_CACHE, "trading_memory.md"),
    "memory_log_max_entries": None,

    # LLM tier — Stonks uses Ollama for both tiers (qwen3:14b). Two-tier
    # temperature differentiation lives in ``app.llm.ollama_client``.
    "llm_provider": "ollama",
    "deep_think_llm": settings.OLLAMA_MODEL or "qwen3:14b",
    "quick_think_llm": settings.OLLAMA_MODEL or "qwen3:14b",
    "backend_url": (settings.OLLAMA_HOST or "").rstrip("/") + "/v1" if settings.OLLAMA_HOST else None,

    # Provider-specific reasoning knobs — Ollama doesn't use these.
    "google_thinking_level": None,
    "openai_reasoning_effort": None,
    "anthropic_effort": None,

    # Checkpoint/resume — disabled (we don't persist checkpoints to disk).
    "checkpoint_enabled": False,

    "output_language": "English",

    # Debate & discussion settings (Phase 1 ships rounds=1, UI hides panels — V0.2).
    "max_debate_rounds": int(os.getenv("DESK_MAX_DEBATE_ROUNDS", "1")),
    "max_risk_discuss_rounds": int(os.getenv("DESK_MAX_RISK_DISCUSS_ROUNDS", "1")),
    "max_recur_limit": 100,

    # Data vendor configuration — Stonks adapters route through
    # ``app.agents.adapters.tools``. The vendor name here is decorative.
    "data_vendors": {
        "core_stock_apis": "stonks",
        "technical_indicators": "stonks",
        "fundamental_data": "stonks",
        "news_data": "stonks",
    },
    "tool_vendors": {},
}


def get_desk_config() -> Dict[str, Any]:
    """Return a fresh copy of the desk config dict."""
    return dict(DESK_CONFIG)
