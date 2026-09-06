# Stonks Patches Applied to Vendored TradingAgents

This directory tracks the deliberate patches Stonks applies on top of the
upstream `tradingagents` source (Apache 2.0, vendored at the commit named in
`../VENDORED_FROM`). When upstream is re-vendored, re-apply these patches.

## Active patches

| # | Target | Purpose |
|---|--------|---------|
| 0001 | `graph/trading_graph.py` | Guard `import yfinance as yf` (Stonks scores outcomes externally via the `score_past_decisions` Celery task: yfinance is unused) |
| 0002 | `graph/checkpointer.py` | Guard `from langgraph.checkpoint.sqlite import SqliteSaver` (Stonks does not pull `langgraph-checkpoint-sqlite`; `checkpoint_enabled=False` in `desk_config`) |
| 0003 | All `*.py` | Rewrite `from tradingagents.X` → `from app.agents.tradingagents.X` (vendored package lives one nesting level deeper) |
| 0004 | `dataflows/__init__.py`, `dataflows/config.py`, `dataflows/interface.py` | Replaced upstream's yfinance/Alpha Vantage adapter routing with Stonks DB adapters via `route_to_vendor` forwarding to `app.agents.adapters.tools` |
| 0005 | `default_config.py` | Replaced with a thin re-export of `app.agents.desk_config.DESK_CONFIG` |

The ordering above mirrors the order in which patches need to be reapplied
on a fresh vendor of upstream. There are no `*.patch` files yet: Stonks
applies these as direct edits during the vendoring step. If a future upgrade
breaks the diff, generate canonical `.patch` files with `git format-patch`.

## What is NOT patched

- `agents/` (analysts, researchers, managers, trader, risk_mgmt, utils, schemas): used as-is. The whole point of vendoring is to keep their prompts, structured-output schemas, and graph wiring verbatim.
- `graph/setup.py`, `graph/conditional_logic.py`, `graph/propagation.py`, `graph/signal_processing.py`, `graph/reflection.py`: used as-is.
- `llm_clients/`: used as-is. Stonks bypasses it from `desk_workflow.py` and constructs LLMs via `app.llm.ollama_client` directly, so upstream's factory is never invoked but stays compileable.

## Re-vendoring procedure

1. Update `../VENDORED_FROM` with the new pinned commit
2. Re-run the rsync filter from `app/agents/tradingagents/`
3. Reapply each patch above in order
4. Run `scripts/spike_phase0_verification.py` to confirm V0.1 / V0.3 still pass on the new upstream
5. Run the Phase 1 import smoke test: `python -c "from app.agents.desk_workflow import build_trading_desk_workflow; print('OK')"`
