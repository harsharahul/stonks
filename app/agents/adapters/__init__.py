"""Stonks-native adapters that back the vendored TradingAgents tool layer.

The desk uses upstream's agent prompts and graph orchestration verbatim, but
all data tools (`get_stock_data`, `get_news`, `get_fundamentals`, ...) and
the memory log are replaced with implementations that read from our own
Postgres tables. This package houses those replacements.

- ``tools``               Data adapters routed via ``route_to_vendor``
- ``instrument_context``  Per-ticker prompt context (Stock + StockKnowledge)
- ``memory_log``          PostgresMemoryLog implementing upstream's interface
- ``llm_factory``         Bridge to ``app.llm.ollama_client``
"""
