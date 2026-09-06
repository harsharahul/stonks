"""Build the AI Trading Desk LangGraph workflow.

Stonks owns this orchestration so we can wire our Ollama LLM and our
PostgresMemoryLog without going through upstream's
``TradingAgentsGraph.__init__`` (which expects yfinance, on-disk
checkpoints, and a markdown memory log we don't want).

The vendored upstream pieces we still rely on:
  - ``app.agents.tradingagents.graph.setup.GraphSetup``: node/edge wiring
  - ``app.agents.tradingagents.graph.conditional_logic.ConditionalLogic``
  - ``app.agents.tradingagents.graph.propagation.Propagator``
  - ``app.agents.tradingagents.graph.signal_processing.SignalProcessor``
  - ``app.agents.tradingagents.agents.*``: the agent fns
  - ``app.agents.tradingagents.agents.utils.agent_utils``: tool wrappers

Usage::

    workflow = build_trading_desk_workflow()
    init_state = workflow.create_initial_state("NVDA", "2026-04-28")
    final_state = workflow.invoke(init_state)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langgraph.prebuilt import ToolNode

from app.agents.adapters.instrument_context import build_stonks_instrument_context
from app.agents.adapters.llm_factory import deep_thinking_llm, quick_thinking_llm
from app.agents.adapters.memory_log import PostgresMemoryLog
from app.agents.desk_config import get_desk_config
from app.agents.tradingagents.agents.utils.agent_utils import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_global_news,
    get_income_statement,
    get_indicators,
    get_insider_transactions,
    get_news,
    get_stock_data,
)
from app.agents.tradingagents.dataflows.config import set_config
from app.agents.tradingagents.graph.conditional_logic import ConditionalLogic
from app.agents.tradingagents.graph.propagation import Propagator
from app.agents.tradingagents.graph.setup import GraphSetup
from app.agents.tradingagents.graph.signal_processing import SignalProcessor

logger = logging.getLogger(__name__)


_DEFAULT_ANALYSTS = ["market", "social", "news", "fundamentals"]


@dataclass
class TradingDeskWorkflow:
    """Compiled desk graph + initialisation helpers."""

    graph: Any
    propagator: Propagator
    signal_processor: SignalProcessor
    memory_log: PostgresMemoryLog
    config: Dict[str, Any]

    def create_initial_state(
        self,
        ticker: str,
        trade_date: str,
        *,
        past_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        sym = ticker.upper()
        ctx = past_context if past_context is not None else self.memory_log.get_past_context(sym)
        # The instrument context block lands in the propagation state for any
        # agent that wants to use it (currently injected via prompts that
        # call ``build_instrument_context``; we expose Stonks's enrichment
        # as a separate field so future patches can pick it up).
        state = self.propagator.create_initial_state(sym, str(trade_date), past_context=ctx)
        state["stonks_instrument_context"] = build_stonks_instrument_context(sym)
        return state

    def graph_args(self, callbacks: Optional[List] = None) -> Dict[str, Any]:
        return self.propagator.get_graph_args(callbacks=callbacks)

    def invoke(
        self,
        state: Dict[str, Any],
        *,
        callbacks: Optional[List] = None,
    ) -> Dict[str, Any]:
        """Run the compiled graph on the supplied initial state."""
        return self.graph.invoke(state, **self.graph_args(callbacks=callbacks))

    def extract_decision(self, final_state: Dict[str, Any]) -> str:
        """Pull the structured decision string out of the final state."""
        decision = final_state.get("final_trade_decision") or ""
        return self.signal_processor.process_signal(decision) if decision else ""


def build_trading_desk_workflow(
    *,
    selected_analysts: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> TradingDeskWorkflow:
    """Compile the trading-desk graph using Stonks-injected dependencies.

    Parameters
    ----------
    selected_analysts
        Subset of ``["market", "social", "news", "fundamentals"]`` to enable.
        Defaults to all four.
    config
        Optional override of the desk config. Defaults to
        ``app.agents.desk_config.DESK_CONFIG``.
    """
    cfg = config or get_desk_config()
    analysts = selected_analysts or _DEFAULT_ANALYSTS

    # Make the active config visible to vendored modules that read it via
    # ``app.agents.tradingagents.dataflows.config.get_config``.
    set_config(cfg)

    quick_llm = quick_thinking_llm()
    deep_llm = deep_thinking_llm()

    tool_nodes: Dict[str, ToolNode] = {
        "market": ToolNode([get_stock_data, get_indicators]),
        "social": ToolNode([get_news]),
        "news": ToolNode([get_news, get_global_news, get_insider_transactions]),
        "fundamentals": ToolNode(
            [get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement]
        ),
    }

    conditional_logic = ConditionalLogic(
        max_debate_rounds=int(cfg.get("max_debate_rounds", 1)),
        max_risk_discuss_rounds=int(cfg.get("max_risk_discuss_rounds", 1)),
    )

    setup = GraphSetup(
        quick_thinking_llm=quick_llm,
        deep_thinking_llm=deep_llm,
        tool_nodes=tool_nodes,
        conditional_logic=conditional_logic,
    )
    workflow_graph = setup.setup_graph(analysts).compile()

    propagator = Propagator(max_recur_limit=int(cfg.get("max_recur_limit", 100)))
    signal_processor = SignalProcessor(quick_llm)
    memory_log = PostgresMemoryLog(cfg)

    logger.info(
        "desk_workflow built: analysts=%s, debate_rounds=%s, risk_rounds=%s, model=%s",
        analysts,
        cfg.get("max_debate_rounds"),
        cfg.get("max_risk_discuss_rounds"),
        cfg.get("deep_think_llm"),
    )

    return TradingDeskWorkflow(
        graph=workflow_graph,
        propagator=propagator,
        signal_processor=signal_processor,
        memory_log=memory_log,
        config=cfg,
    )
