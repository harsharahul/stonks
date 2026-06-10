"""TradingDeskService — orchestration around the desk workflow.

Single entry point for:
- Universe selection (top-N composite score + watchlists + movers reserve)
- Running the desk pipeline for one ticker (workflow + persistence)
- Read-side helpers used by API endpoints

The agent execution itself runs synchronously inside the calling process;
in production that's a Celery worker (see ``app.tasks.agent_pipeline``).
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.agents.adapters.memory_log import PostgresMemoryLog
from app.agents.desk_config import get_desk_config
from app.agents.desk_workflow import TradingDeskWorkflow, build_trading_desk_workflow
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.agent_brief import AgentBrief
from app.models.agent_decision import AgentDecision
from app.models.agent_decision_outcome import AgentDecisionOutcome
from app.models.agent_run import AgentRun
from app.models.agent_universe_membership import AgentUniverseMembership

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Universe selection
# ---------------------------------------------------------------------------


# Tunable knobs for universe sizing — kept module-scope so tests / overrides
# can monkeypatch without touching the desk_config dict.
TOP_N_BY_SCORE = 45
RESERVE_MOVERS = 5
COMPOSITE_BASELINE_DAYS = 30  # cross-ticker rolling baseline used for z-scoring


def select_universe(db: Session) -> List[Tuple[str, float, str]]:
    """Compute the desk's covered universe.

    Composite score (cross-ticker rolling 30-day baseline):

        score(ticker) = z(article_count_7d) + z(wsb_mention_count_7d)
                       + z(abs(vol_z))      + 0.5 * z(abs(sent_shock))

    Returns list of (ticker, score, reason) tuples — sorted by relevance.
    Reasons: ``top_activity`` | ``mover_reserve`` | ``watchlist``.

    NaN handling: any ticker with < 7 days of features is excluded from
    score-based candidates (mover reserve and watchlist still admit them).
    """
    from app.models.ticker_features_daily import TickerFeaturesDaily
    from app.models.watchlist import WatchlistItem

    cutoff = date.today() - timedelta(days=COMPOSITE_BASELINE_DAYS)

    # Pull the latest row per ticker to score against; assumes
    # ticker_features_daily has one row per (ticker, date).
    latest_per_ticker = (
        db.execute(
            select(
                TickerFeaturesDaily.ticker,
                func.max(TickerFeaturesDaily.date).label("max_date"),
                func.count().label("days_count"),
            )
            .where(TickerFeaturesDaily.date >= cutoff)
            .group_by(TickerFeaturesDaily.ticker)
        )
        .all()
    )
    candidate_tickers = [t for t, _, n in latest_per_ticker if n >= 7]

    rows = (
        db.execute(
            select(TickerFeaturesDaily)
            .where(
                TickerFeaturesDaily.ticker.in_(candidate_tickers),
                TickerFeaturesDaily.date >= cutoff,
            )
        )
        .scalars()
        .all()
    )

    # Aggregate per-ticker mean of the score components (the rolling
    # baseline is implicit in the population we standardize against).
    by_ticker: Dict[str, Dict[str, List[float]]] = {}
    for r in rows:
        bucket = by_ticker.setdefault(
            r.ticker,
            {"article_count_7d": [], "wsb_mention_count_7d": [], "vol_z": [], "sent_shock": []},
        )
        for col in bucket:
            v = getattr(r, col, None)
            if v is not None:
                try:
                    bucket[col].append(float(v))
                except (TypeError, ValueError):
                    continue

    def latest(values: List[float]) -> Optional[float]:
        return values[-1] if values else None

    raw_components: Dict[str, Dict[str, Optional[float]]] = {}
    for ticker, cols in by_ticker.items():
        raw_components[ticker] = {
            "article_count_7d": latest(cols["article_count_7d"]),
            "wsb_mention_count_7d": latest(cols["wsb_mention_count_7d"]),
            "vol_z_abs": abs(latest(cols["vol_z"])) if latest(cols["vol_z"]) is not None else None,
            "sent_shock_abs": abs(latest(cols["sent_shock"])) if latest(cols["sent_shock"]) is not None else None,
        }

    def z(values: List[float], v: Optional[float]) -> float:
        if v is None or not values:
            return 0.0
        mean = sum(values) / len(values)
        var = sum((x - mean) ** 2 for x in values) / max(len(values), 1)
        std = var ** 0.5
        return (v - mean) / std if std > 1e-9 else 0.0

    populations = {
        "article_count_7d": [c["article_count_7d"] for c in raw_components.values() if c["article_count_7d"] is not None],
        "wsb_mention_count_7d": [c["wsb_mention_count_7d"] for c in raw_components.values() if c["wsb_mention_count_7d"] is not None],
        "vol_z_abs": [c["vol_z_abs"] for c in raw_components.values() if c["vol_z_abs"] is not None],
        "sent_shock_abs": [c["sent_shock_abs"] for c in raw_components.values() if c["sent_shock_abs"] is not None],
    }

    scored: List[Tuple[str, float]] = []
    for ticker, comp in raw_components.items():
        score = (
            z(populations["article_count_7d"], comp["article_count_7d"]) +
            z(populations["wsb_mention_count_7d"], comp["wsb_mention_count_7d"]) +
            z(populations["vol_z_abs"], comp["vol_z_abs"]) +
            0.5 * z(populations["sent_shock_abs"], comp["sent_shock_abs"])
        )
        scored.append((ticker, score))

    scored.sort(key=lambda t: t[1], reverse=True)
    top_activity = [(t, s, "top_activity") for t, s in scored[:TOP_N_BY_SCORE]]

    # Mover reserve — biggest |ret_1d| from the latest day.
    movers_today = (
        db.execute(
            select(TickerFeaturesDaily.ticker, TickerFeaturesDaily.ret_1d)
            .where(TickerFeaturesDaily.date == func.current_date())
            .where(TickerFeaturesDaily.ret_1d.isnot(None))
        )
        .all()
    )
    movers_sorted = sorted(
        ((t, float(abs(v))) for t, v in movers_today if v is not None),
        key=lambda x: x[1],
        reverse=True,
    )
    seen = {t for t, _, _ in top_activity}
    mover_reserve: List[Tuple[str, float, str]] = []
    for t, abs_ret in movers_sorted:
        if len(mover_reserve) >= RESERVE_MOVERS:
            break
        if t in seen:
            continue
        mover_reserve.append((t, abs_ret, "mover_reserve"))
        seen.add(t)

    # Watchlist union — pull all distinct watchlist tickers.
    watchlist_tickers = (
        db.execute(
            select(WatchlistItem.stock_id).distinct()
        )
        .scalars()
        .all()
    )
    # WatchlistItem.stock_id is a UUID FK to stocks.id, not a ticker symbol.
    # Resolve to ticker via the Stock model.
    from app.models.stock import Stock

    if watchlist_tickers:
        watchlist_symbols = (
            db.execute(
                select(Stock.symbol).where(Stock.id.in_(watchlist_tickers))
            )
            .scalars()
            .all()
        )
    else:
        watchlist_symbols = []

    watchlist_extras: List[Tuple[str, float, str]] = []
    for sym in watchlist_symbols:
        if sym in seen:
            continue
        watchlist_extras.append((sym, 0.0, "watchlist"))
        seen.add(sym)

    return top_activity + mover_reserve + watchlist_extras


def refresh_universe_membership(db: Session) -> int:
    """Close out previous active rows and insert today's membership.

    Returns the count of rows inserted.
    """
    now = datetime.utcnow()
    db.execute(
        AgentUniverseMembership.__table__.update()
        .where(AgentUniverseMembership.included_until.is_(None))
        .values(included_until=now)
    )

    members = select_universe(db)
    inserted = 0
    for ticker, score, reason in members:
        db.add(
            AgentUniverseMembership(
                ticker=ticker,
                included_at=now,
                included_until=None,
                score=score,
                reason=reason,
            )
        )
        inserted += 1
    db.commit()
    logger.info("refresh_universe_membership: inserted %d active rows", inserted)
    return inserted


def get_active_universe(db: Session) -> List[AgentUniverseMembership]:
    """Return rows currently considered in the active universe."""
    return (
        db.execute(
            select(AgentUniverseMembership)
            .where(AgentUniverseMembership.included_until.is_(None))
            .order_by(desc(AgentUniverseMembership.score))
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# Run orchestration
# ---------------------------------------------------------------------------


_AGENT_TO_BRIEF_FIELD = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}


def _model_descriptor() -> str:
    base = settings.OLLAMA_MODEL or "unknown"
    return f"ollama/{base}"


def run_for_ticker(
    ticker: str,
    *,
    trigger: str = "manual",
    trade_date: Optional[date] = None,
    workflow: Optional[TradingDeskWorkflow] = None,
) -> uuid.UUID:
    """Run the desk pipeline for one ticker, persist briefs + decision, return run id.

    Caller may pass a pre-built workflow to amortise the LangGraph compile
    cost across many tickers (Celery batch path); otherwise we build a
    fresh one per call (on-demand path).
    """
    sym = ticker.upper()
    as_of = trade_date or date.today()
    desk_workflow = workflow or build_trading_desk_workflow()

    started = datetime.utcnow()
    perf_start = time.perf_counter()

    with SessionLocal() as db:
        run = AgentRun(
            ticker=sym,
            status="running",
            trigger=trigger,
            model=_model_descriptor(),
        )
        db.add(run)
        db.commit()
        run_id = run.id

    final_state: Optional[Dict[str, Any]] = None
    error_text: Optional[str] = None

    try:
        init_state = desk_workflow.create_initial_state(sym, as_of.isoformat())
        final_state = desk_workflow.invoke(init_state)
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("desk_workflow invocation failed for %s: %s", sym, exc)
        error_text = f"{type(exc).__name__}: {exc}"

    latency_ms = int((time.perf_counter() - perf_start) * 1000)

    with SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        if run is None:
            return run_id

        if final_state is None:
            run.status = "failed"
            run.error = error_text or "unknown error"
            run.run_completed_at = datetime.utcnow()
            run.latency_ms = latency_ms
            db.commit()
            return run_id

        # Persist analyst briefs
        for agent_name, field in _AGENT_TO_BRIEF_FIELD.items():
            text = (final_state.get(field) or "").strip()
            if not text:
                continue
            db.add(
                AgentBrief(
                    agent_run_id=run_id,
                    agent_name=agent_name,
                    round_index=0,
                    output_text=text,
                )
            )

        # Persist debate (research manager output) and trader plan
        invest_state = final_state.get("investment_debate_state") or {}
        bull_history = (invest_state.get("bull_history") or "").strip()
        bear_history = (invest_state.get("bear_history") or "").strip()
        if bull_history:
            db.add(AgentBrief(agent_run_id=run_id, agent_name="bull", round_index=1, output_text=bull_history))
        if bear_history:
            db.add(AgentBrief(agent_run_id=run_id, agent_name="bear", round_index=1, output_text=bear_history))

        plan_text = (final_state.get("investment_plan") or "").strip()
        if plan_text:
            db.add(AgentBrief(agent_run_id=run_id, agent_name="research_manager", round_index=0, output_text=plan_text))

        trader_text = (final_state.get("trader_investment_plan") or "").strip()
        if trader_text:
            db.add(AgentBrief(agent_run_id=run_id, agent_name="trader", round_index=0, output_text=trader_text))

        # Risk team rounds (history strings keyed by latest_speaker; we
        # split on the upstream's per-speaker markers).
        risk_state = final_state.get("risk_debate_state") or {}
        for kind in ("aggressive", "conservative", "neutral"):
            history = (risk_state.get(f"{kind}_history") or "").strip()
            if history:
                db.add(
                    AgentBrief(
                        agent_run_id=run_id,
                        agent_name=kind,
                        round_index=1,
                        output_text=history,
                    )
                )

        # Final decision
        final_decision_text = (final_state.get("final_trade_decision") or "").strip()
        decision_label, conviction = _parse_decision(final_decision_text)
        if final_decision_text:
            db.add(
                AgentBrief(
                    agent_run_id=run_id,
                    agent_name="portfolio_manager",
                    round_index=0,
                    output_text=final_decision_text,
                    conviction=conviction,
                )
            )
            db.add(
                AgentDecision(
                    agent_run_id=run_id,
                    ticker=sym,
                    as_of_date=as_of,
                    decision=decision_label,
                    conviction=conviction,
                    thesis_text=final_decision_text[:8000],
                    pending=True,
                    features_snapshot_json=_features_snapshot(sym, db),
                )
            )

        run.status = "succeeded"
        run.run_completed_at = datetime.utcnow()
        run.latency_ms = latency_ms
        db.commit()

    logger.info(
        "desk run for %s succeeded in %dms (run_id=%s, decision=%s)",
        sym, latency_ms, run_id, decision_label,
    )
    return run_id


def _parse_decision(text: str) -> Tuple[str, float]:
    """Extract a portfolio rating + provisional conviction from the PM output."""
    upper = (text or "").upper()
    rating_order = ["STRONG BUY", "OVERWEIGHT", "BUY", "UNDERWEIGHT", "SELL", "HOLD"]
    label = "Hold"
    for token in rating_order:
        if token in upper:
            label = token.title()
            break
    # Conviction heuristic: presence of "FINAL TRANSACTION PROPOSAL" + explicit
    # action gives 0.7; bare mention 0.5; missing signal 0.3.
    if "FINAL TRANSACTION PROPOSAL" in upper:
        conviction = 0.7
    elif label != "Hold":
        conviction = 0.5
    else:
        conviction = 0.3
    return label, conviction


def _features_snapshot(ticker: str, db: Session) -> Optional[Dict[str, Any]]:
    """Return latest TickerFeaturesDaily row as a JSON-safe dict."""
    try:
        from app.models.ticker_features_daily import TickerFeaturesDaily

        row = (
            db.execute(
                select(TickerFeaturesDaily)
                .where(TickerFeaturesDaily.ticker == ticker)
                .order_by(desc(TickerFeaturesDaily.date))
                .limit(1)
            )
            .scalar_one_or_none()
        )
        if not row:
            return None
        snap = {}
        for col in (
            "date", "sent_mean_7d", "sent_shock", "novelty_mean_3d",
            "ret_1d", "ret_5d", "momentum_14d", "vol_z", "article_count_7d",
            "wsb_mention_count_7d", "wsb_sentiment_7d", "retail_buzz_score",
            "meme_stock_indicator",
        ):
            v = getattr(row, col, None)
            if v is None:
                continue
            if hasattr(v, "isoformat"):
                snap[col] = v.isoformat()
            else:
                try:
                    snap[col] = float(v)
                except (TypeError, ValueError):
                    snap[col] = str(v)
        return snap
    except Exception:
        logger.exception("_features_snapshot failed for %s", ticker)
        return None


# ---------------------------------------------------------------------------
# Read-side helpers (consumed by API endpoints)
# ---------------------------------------------------------------------------


def get_latest_decision(db: Session, ticker: str) -> Optional[AgentDecision]:
    sym = ticker.upper()
    return (
        db.execute(
            select(AgentDecision)
            .where(AgentDecision.ticker == sym)
            .order_by(desc(AgentDecision.created_at))
            .limit(1)
        )
        .scalar_one_or_none()
    )


def get_run_briefs(db: Session, run_id: uuid.UUID) -> List[AgentBrief]:
    return (
        db.execute(
            select(AgentBrief)
            .where(AgentBrief.agent_run_id == run_id)
            .order_by(AgentBrief.created_at.asc())
        )
        .scalars()
        .all()
    )


def get_decision_outcome(db: Session, decision_id: uuid.UUID) -> Optional[AgentDecisionOutcome]:
    return (
        db.execute(
            select(AgentDecisionOutcome).where(AgentDecisionOutcome.agent_decision_id == decision_id)
        )
        .scalar_one_or_none()
    )


def get_universe_view(db: Session) -> List[Dict[str, Any]]:
    """Return active universe with most-recent decision joined for each ticker."""
    rows = get_active_universe(db)
    out: List[Dict[str, Any]] = []
    for membership in rows:
        latest = get_latest_decision(db, membership.ticker)
        out.append(
            {
                "ticker": membership.ticker,
                "score": float(membership.score) if membership.score is not None else None,
                "reason": membership.reason,
                "included_at": membership.included_at.isoformat() if membership.included_at else None,
                "latest_decision": latest.to_dict() if latest else None,
            }
        )
    return out


def get_decision_history(
    db: Session, ticker: str, limit: int = 30
) -> List[Dict[str, Any]]:
    sym = ticker.upper()
    decisions = (
        db.execute(
            select(AgentDecision)
            .where(AgentDecision.ticker == sym)
            .order_by(desc(AgentDecision.created_at))
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        {
            "decision": d.to_dict(),
            "outcome": (get_decision_outcome(db, d.id).to_dict() if get_decision_outcome(db, d.id) else None),
        }
        for d in decisions
    ]


def get_full_desk_view(db: Session, ticker: str) -> Optional[Dict[str, Any]]:
    """Return the Phase-1 read-side payload for `GET /desk/{ticker}`."""
    decision = get_latest_decision(db, ticker)
    if decision is None:
        return None
    briefs = get_run_briefs(db, decision.agent_run_id)
    outcome = get_decision_outcome(db, decision.id)
    run = db.get(AgentRun, decision.agent_run_id)

    return {
        "ticker": decision.ticker,
        "as_of_date": decision.as_of_date.isoformat(),
        "run": run.to_dict() if run else None,
        "decision": decision.to_dict(),
        "outcome": outcome.to_dict() if outcome else None,
        "briefs": [b.to_dict() for b in briefs],
    }
