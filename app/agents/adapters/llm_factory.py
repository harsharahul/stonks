"""Bridge from desk orchestration to ``app.llm.ollama_client``.

Stonks bypasses upstream's ``tradingagents.llm_clients.factory.create_llm_client``
to keep a single Ollama integration path (``app/llm/ollama_client.py``). This
module exposes the small surface our ``desk_workflow`` needs:

  - ``deep_thinking_llm()`` — Research Manager, Portfolio Manager, Trader
  - ``quick_thinking_llm()`` — analysts, researchers, risk debaters
"""
from __future__ import annotations

import logging
from typing import Any

from app.llm.ollama_client import get_deep_thinking_llm, get_quick_thinking_llm

logger = logging.getLogger(__name__)


def deep_thinking_llm() -> Any:
    """ChatOpenAI wired to our Ollama at deterministic temperature."""
    return get_deep_thinking_llm()


def quick_thinking_llm() -> Any:
    """ChatOpenAI wired to our Ollama at debate-friendly temperature."""
    return get_quick_thinking_llm()
