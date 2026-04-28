"""Per-ticker prompt context block — sector + StockKnowledge highlights.

Used by the Trader / Research Manager / Portfolio Manager prompts to anchor
their reasoning on the specific instrument. Phase 1: lightweight enrichment;
Phase 2 may extend to include peer-group context, options-flow flags, etc.

Upstream's ``build_instrument_context`` lives in
``app.agents.tradingagents.agents.utils.agent_utils`` and returns a generic
"preserve the exchange-qualified ticker" string. We don't replace that
function (vendored agents call it directly) — this module is a Stonks-only
extension reachable from `desk_workflow` if it wants to inject richer
context into the initial state.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select

from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


def build_stonks_instrument_context(ticker: str) -> str:
    """Return a richer per-ticker context block for desk prompts.

    Includes sector / industry from `Stock` and a short StockKnowledge
    excerpt. Falls back gracefully when fields are missing.
    """
    sym = ticker.upper()
    bullets: list[str] = [f"Instrument: `{sym}`."]
    try:
        from app.models.stock import Stock
        from app.models.stock_knowledge import StockKnowledge

        with SessionLocal() as db:
            stock = (
                db.execute(select(Stock).where(Stock.symbol == sym).limit(1)).scalar_one_or_none()
            )
            if stock:
                if getattr(stock, "name", None):
                    bullets.append(f"Name: {stock.name}.")
                sector = getattr(stock, "sector", None)
                industry = getattr(stock, "industry", None)
                if sector:
                    bullets.append(f"Sector: {sector}.")
                if industry:
                    bullets.append(f"Industry: {industry}.")

            knowledge = (
                db.execute(
                    select(StockKnowledge).where(StockKnowledge.ticker == sym).limit(1)
                ).scalar_one_or_none()
            )
            if knowledge and getattr(knowledge, "narrative", None):
                narrative: Optional[str] = knowledge.narrative
                if narrative:
                    short = narrative[:600] + ("..." if len(narrative) > 600 else "")
                    bullets.append(f"Per-ticker narrative summary: {short}")
    except Exception as exc:  # pragma: no cover
        logger.warning("build_stonks_instrument_context: DB lookup failed: %s", exc)

    bullets.append(
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )
    return " ".join(bullets)
