"""Postgres-backed memory log for the AI Trading Desk.

Implements upstream's ``TradingMemoryLog`` interface so the vendored
``trading_graph.py`` can swap implementations via constructor injection.
The data lives in the ``agent_decisions`` and ``agent_decision_outcomes``
tables: same source of truth as the rest of the desk pipeline.

Phase 1 supports the read/write surface; the markdown formatting in
``get_past_context`` mirrors upstream's exact shape so prompts read it
identically. Phase 3 extends ``update_with_outcome`` to consume scored
outcomes from the ``score_past_decisions`` Celery task.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


class PostgresMemoryLog:
    """Drop-in replacement for upstream's ``TradingMemoryLog``."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        # We don't read/write a path, but accept it for signature compat.
        self._log_path = self.config.get("memory_log_path")

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def store_decision(
        self,
        ticker: str,
        trade_date: str,
        final_trade_decision: str,
    ) -> None:
        """Idempotently insert an `agent_decisions` row in pending state.

        Called from upstream `TradingAgentsGraph._run_graph` at the end of a
        propagate() run. Stonks orchestration in `desk_workflow.py` writes
        the more detailed `AgentDecision` row directly with the structured
        portfolio output, but we keep this method working for compat with
        any code path that calls it.
        """
        from app.models.agent_decision import AgentDecision
        from app.models.agent_run import AgentRun

        as_of = self._parse_date(trade_date)
        if not as_of:
            logger.warning("store_decision: bad trade_date=%s", trade_date)
            return

        try:
            with SessionLocal() as db:
                # Idempotency: skip if a pending decision already exists
                # for this (ticker, as_of_date).
                existing = (
                    db.execute(
                        select(AgentDecision).where(
                            AgentDecision.ticker == ticker.upper(),
                            AgentDecision.as_of_date == as_of,
                            AgentDecision.pending.is_(True),
                        )
                    )
                    .scalar_one_or_none()
                )
                if existing:
                    return

                # Synthetic run record (we don't have the run_id here);
                # desk_workflow normally creates this row first.
                run = AgentRun(
                    ticker=ticker.upper(),
                    status="succeeded",
                    trigger="memory_log_store",
                )
                db.add(run)
                db.flush()  # populate run.id
                db.add(
                    AgentDecision(
                        agent_run_id=run.id,
                        ticker=ticker.upper(),
                        as_of_date=as_of,
                        decision=self._extract_action(final_trade_decision),
                        conviction=0.5,
                        thesis_text=final_trade_decision[:8000],
                        pending=True,
                    )
                )
                db.commit()
        except SQLAlchemyError as exc:
            logger.exception("store_decision: DB write failed: %s", exc)

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def load_entries(self) -> List[Dict[str, Any]]:
        """Return all decisions as dicts (most recent first)."""
        return self._load(limit=200)

    def get_pending_entries(self) -> List[Dict[str, Any]]:
        """Return decisions that haven't been scored yet."""
        return [e for e in self._load(limit=500) if e.get("pending")]

    def get_past_context(
        self,
        ticker: str,
        n_same: int = 5,
        n_cross: int = 3,
    ) -> str:
        """Return upstream-formatted past-context string for prompt injection."""
        entries = [e for e in self._load(limit=500) if not e.get("pending")]
        if not entries:
            return ""

        sym = ticker.upper()
        same, cross = [], []
        for e in entries:  # already most-recent-first
            if len(same) >= n_same and len(cross) >= n_cross:
                break
            if e["ticker"] == sym and len(same) < n_same:
                same.append(e)
            elif e["ticker"] != sym and len(cross) < n_cross:
                cross.append(e)

        if not same and not cross:
            return ""

        parts: List[str] = []
        if same:
            parts.append(f"Past analyses of {sym} (most recent first):")
            parts.extend(self._format_full(e) for e in same)
        if cross:
            parts.append("Recent cross-ticker lessons:")
            parts.extend(self._format_reflection_only(e) for e in cross)
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Update path (called from score_past_decisions Celery task)
    # ------------------------------------------------------------------

    def update_with_outcome(
        self,
        ticker: str,
        trade_date: str,
        raw_return: float,
        alpha_return: float,
        holding_days: int,
        reflection: str,
    ) -> None:
        self.batch_update_with_outcomes(
            [
                {
                    "ticker": ticker,
                    "trade_date": trade_date,
                    "raw_return": raw_return,
                    "alpha_return": alpha_return,
                    "holding_days": holding_days,
                    "reflection": reflection,
                }
            ]
        )

    def batch_update_with_outcomes(self, updates: List[Dict[str, Any]]) -> None:
        """Atomically score multiple pending decisions in one transaction."""
        from app.models.agent_decision import AgentDecision
        from app.models.agent_decision_outcome import AgentDecisionOutcome

        if not updates:
            return
        try:
            with SessionLocal() as db:
                for u in updates:
                    as_of = self._parse_date(u.get("trade_date"))
                    if not as_of:
                        continue
                    decision = (
                        db.execute(
                            select(AgentDecision)
                            .where(
                                AgentDecision.ticker == u["ticker"].upper(),
                                AgentDecision.as_of_date == as_of,
                                AgentDecision.pending.is_(True),
                            )
                            .order_by(desc(AgentDecision.created_at))
                            .limit(1)
                        )
                        .scalar_one_or_none()
                    )
                    if decision is None:
                        continue
                    outcome = AgentDecisionOutcome(
                        agent_decision_id=decision.id,
                        realized_return_5d=u.get("raw_return"),
                        alpha_5d=u.get("alpha_return"),
                        reflection_text=u.get("reflection"),
                    )
                    db.add(outcome)
                    decision.pending = False
                db.commit()
        except SQLAlchemyError as exc:
            logger.exception("batch_update_with_outcomes: DB write failed: %s", exc)

    # ------------------------------------------------------------------
    # Helpers (private)
    # ------------------------------------------------------------------

    def _load(self, limit: int = 200) -> List[Dict[str, Any]]:
        from app.models.agent_decision import AgentDecision
        from app.models.agent_decision_outcome import AgentDecisionOutcome

        out: List[Dict[str, Any]] = []
        try:
            with SessionLocal() as db:
                rows = (
                    db.execute(
                        select(AgentDecision)
                        .order_by(desc(AgentDecision.created_at))
                        .limit(limit)
                    )
                    .scalars()
                    .all()
                )
                for r in rows:
                    outcome = (
                        db.execute(
                            select(AgentDecisionOutcome)
                            .where(AgentDecisionOutcome.agent_decision_id == r.id)
                            .limit(1)
                        )
                        .scalar_one_or_none()
                    )
                    out.append(
                        {
                            "ticker": r.ticker,
                            "date": r.as_of_date.isoformat() if r.as_of_date else None,
                            "rating": r.decision,
                            "decision": r.thesis_text or "",
                            "pending": r.pending,
                            "raw_return": float(outcome.realized_return_5d)
                            if outcome and outcome.realized_return_5d is not None
                            else None,
                            "alpha_return": float(outcome.alpha_5d)
                            if outcome and outcome.alpha_5d is not None
                            else None,
                            "holding_days": 5,
                            "reflection": outcome.reflection_text if outcome else None,
                        }
                    )
        except SQLAlchemyError as exc:
            logger.warning("PostgresMemoryLog._load failed: %s", exc)
        return out

    @staticmethod
    def _parse_date(s: Optional[str]) -> Optional[date]:
        if not s:
            return None
        if isinstance(s, date) and not isinstance(s, datetime):
            return s
        if isinstance(s, datetime):
            return s.date()
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _extract_action(text: str) -> str:
        upper = (text or "").upper()
        for token in ("STRONG BUY", "OVERWEIGHT", "UNDERWEIGHT", "BUY", "SELL", "HOLD"):
            if token in upper:
                return token.title()
        return "Hold"

    @staticmethod
    def _format_full(e: Dict[str, Any]) -> str:
        raw = e.get("raw_return")
        alpha = e.get("alpha_return")
        days = e.get("holding_days")
        rating = e.get("rating") or "?"
        if raw is not None and alpha is not None and days is not None:
            tag = f"[{e['date']} | {e['ticker']} | {rating} | {raw:+.1%} | {alpha:+.1%} | {days}d]"
        else:
            tag = f"[{e['date']} | {e['ticker']} | {rating} | pending]"
        body = (e.get("decision") or "").strip()
        reflection = (e.get("reflection") or "").strip()
        parts = [tag, "", "DECISION:", body]
        if reflection:
            parts.extend(["", "REFLECTION:", reflection])
        return "\n".join(parts)

    @staticmethod
    def _format_reflection_only(e: Dict[str, Any]) -> str:
        ref = (e.get("reflection") or "").strip()
        if not ref:
            return f"[{e['date']} | {e['ticker']}] (no reflection)"
        return f"[{e['date']} | {e['ticker']}] {ref}"
