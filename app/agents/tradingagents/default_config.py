"""Stonks-vendored stub for ``tradingagents.default_config``.

The real configuration lives in ``app.agents.desk_config.DESK_CONFIG``. This
module exists only so that vendored upstream code (specifically
``trading_graph.py``) can do ``from app.agents.tradingagents.default_config
import DEFAULT_CONFIG`` without crashing at module load. We deliberately do
NOT use upstream's full config: paths, debate rounds, vendor selection are
all owned by Stonks.
"""
from __future__ import annotations

from app.agents.desk_config import DESK_CONFIG

# Upstream code reads ``DEFAULT_CONFIG["data_cache_dir"]`` etc., so expose
# the desk config under that name.
DEFAULT_CONFIG = DESK_CONFIG
