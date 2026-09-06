"""Unified Ollama chat client for Stonks.

Single source of truth for LLM construction across:
- AI Trading Desk (vendored TradingAgents)
- analytics_agent (legacy: being migrated)

Goes through Ollama's OpenAI-compat endpoint via LangChain's ``ChatOpenAI``.
Phase 0 verification confirmed the shim handles ``bind_tools()``,
``with_structured_output()``, and JSON mode for qwen3:14b cleanly, so we
delegate to ChatOpenAI rather than wrap ``ollama.Client`` ourselves.
"""
from __future__ import annotations

import logging
from typing import Optional

from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Tier defaults: analysts/researchers want some sampling diversity for debate;
# managers/trader want deterministic consolidation.
QUICK_THINK_TEMPERATURE = 0.3
DEEP_THINK_TEMPERATURE = 0.1
DEFAULT_TIMEOUT_SECONDS = 120


def _normalize_base_url(host: Optional[str]) -> str:
    """Convert ``OLLAMA_HOST`` into the OpenAI-compat ``/v1`` endpoint URL."""
    if not host:
        raise ValueError("OLLAMA_HOST is not configured")
    base = host.rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"http://{base}"
    return base if base.endswith("/v1") else f"{base}/v1"


def get_chat_model(
    *,
    model: Optional[str] = None,
    temperature: float = DEEP_THINK_TEMPERATURE,
    max_tokens: Optional[int] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    base_url: Optional[str] = None,
) -> ChatOpenAI:
    """Return a configured ChatOpenAI pointed at our Ollama OpenAI-compat endpoint.

    The returned object supports ``.bind_tools(tools)``,
    ``.with_structured_output(schema)``, and async invocation via
    ``.ainvoke(...)``. Drop-in for vendored TradingAgents agents and the
    existing LangGraph engine.

    Precedence: explicit kwarg > ``settings.OLLAMA_*`` > raise.
    """
    resolved_model = model or settings.OLLAMA_MODEL
    if not resolved_model:
        raise ValueError("OLLAMA_MODEL is not configured")
    resolved_base = base_url or _normalize_base_url(settings.OLLAMA_HOST)

    logger.debug(
        "ollama_client: model=%s base_url=%s temp=%s timeout=%s",
        resolved_model, resolved_base, temperature, timeout,
    )
    return ChatOpenAI(
        model=resolved_model,
        base_url=resolved_base,
        api_key="ollama",  # required by langchain-openai but unused by Ollama
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        # Streaming is REQUIRED when Ollama sits behind a reverse proxy with an
        # idle-connection timeout (Cloudflare cuts non-streaming requests at
        # ~100s; qwen3 generations regularly exceed that). With streaming the
        # connection carries bytes continuously and never looks idle.
        streaming=True,
        max_retries=2,
    )


def get_quick_thinking_llm(model: Optional[str] = None) -> ChatOpenAI:
    """Higher-temperature tier for analyst tool-use loops and bull/bear debate."""
    return get_chat_model(model=model, temperature=QUICK_THINK_TEMPERATURE)


def get_deep_thinking_llm(model: Optional[str] = None) -> ChatOpenAI:
    """Lower-temperature tier for research manager, trader, portfolio manager.

    Uses OLLAMA_DEEP_MODEL when configured so decisions can run on a stronger
    model than the analyst/debate tier without code changes.
    """
    resolved = model or settings.OLLAMA_DEEP_MODEL or None
    return get_chat_model(model=resolved, temperature=DEEP_THINK_TEMPERATURE)
