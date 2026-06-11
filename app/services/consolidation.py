"""Unified consolidation layer — every brain, one ranked view.

Merges the platform's three independent voices per ticker into a single
explainable score:

1. **Signal consensus** — active Signal rows (rule engine, plugins, anomaly
   detector), each weighted by its source's VERIFIED track record
   (signal_outcomes win rates). Unproven sources get neutral weight; proven
   winners count more, proven losers count less. This is where the open
   signal marketplace becomes trustworthy instead of noisy.
2. **AI Desk verdict** — latest non-stale AgentDecision (12-agent debate),
   scaled by conviction.
3. **Quant recommendation** — today's rule-based Recommendation score.

The composite is a presence-renormalized blend, and every component ships
with its inputs so the UI can show WHY — no black boxes, no platform
"picks", just arithmetic over verified inputs. Labels are market-stance
words (bullish/bearish), never advice words.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.agent_decision import AgentDecision
from app.models.recommendation import Recommendation
from app.models.signal import Signal
from app.models.stock import Stock

logger = logging.getLogger(__name__)

# Blend weights (renormalized over the components a ticker actually has)
COMPONENT_WEIGHTS = {"signals": 0.40, "desk": 0.35, "recommendation": 0.25}

# Desk decision → score in [-1, 1] (scaled by conviction afterwards)
DESK_DECISION_SCORES = {
    "strong buy": 1.0, "buy": 1.0, "accumulate": 0.75,
    "overweight": 0.5, "hold": 0.0, "neutral": 0.0,
    "underweight": -0.5, "reduce": -0.5, "trim": -0.5,
    "sell": -1.0, "strong sell": -1.0,
}

MIN_SCORED_FOR_WEIGHT = 10   # below this a source's record is noise — stay neutral
DESK_STALENESS_DAYS = 5      # desk verdicts older than this don't vote
SIGNAL_LOOKBACK_HOURS = 48   # active window for signal consensus


def source_weight(track: Optional[Dict[str, Any]]) -> float:
    """Track-record multiplier in [0.5, 1.5]: 1.0 when unproven (neutral),
    above 1 for sources that have actually been right, below for losers."""
    if not track or not track.get("scored") or track["scored"] < MIN_SCORED_FOR_WEIGHT:
        return 1.0
    win_rate = track.get("win_rate")
    if win_rate is None:
        return 1.0
    return max(0.5, min(1.5, 0.5 + 2.0 * float(win_rate)))


def signal_contribution(strength: float, confidence: float, direction: str, weight: float) -> float:
    """One signal's signed vote. Strength is already signed; if a plugin
    emitted zero strength, fall back to direction × confidence."""
    signed = float(strength)
    if signed == 0.0:
        signed = {"bullish": 1.0, "bearish": -1.0}.get(direction, 0.0) * 0.5
    return max(-1.5, min(1.5, signed * float(confidence) * weight))


def desk_component(decision: str, conviction: float) -> float:
    return DESK_DECISION_SCORES.get((decision or "").strip().lower(), 0.0) * float(conviction)


def recommendation_component(score: float) -> float:
    """Recommendation scores live in [0, 1] (0.5 = neutral) → map to [-1, 1]."""
    return max(-1.0, min(1.0, (float(score) - 0.5) * 2.0))


def blend(components: Dict[str, Optional[float]]) -> Optional[float]:
    """Presence-renormalized weighted blend; None when no component voted."""
    present = {k: v for k, v in components.items() if v is not None}
    if not present:
        return None
    total_w = sum(COMPONENT_WEIGHTS[k] for k in present)
    return round(sum(v * COMPONENT_WEIGHTS[k] for k, v in present.items()) / total_w, 4)


def stance_label(score: Optional[float]) -> str:
    if score is None:
        return "no data"
    if score >= 0.45:
        return "strongly bullish"
    if score >= 0.15:
        return "bullish"
    if score > -0.15:
        return "neutral"
    if score > -0.45:
        return "bearish"
    return "strongly bearish"


def consolidated_rankings(db: Session, limit: int = 25) -> Dict[str, Any]:
    """Compute the ranked view across every ticker any brain has spoken on."""
    from app.tasks.signal_outcomes import source_track_records, source_for_signal

    now = datetime.utcnow()
    tracks = source_track_records(db)

    # Voice 1: active signals in the lookback window
    signal_rows = db.execute(
        select(Signal).where(Signal.generated_at >= now - timedelta(hours=SIGNAL_LOOKBACK_HOURS))
    ).scalars().all()
    by_ticker_signals: Dict[str, List[Signal]] = {}
    for s in signal_rows:
        if s.expires_at and s.expires_at.replace(tzinfo=None) < now:
            continue
        by_ticker_signals.setdefault(s.ticker.upper(), []).append(s)

    # Voice 2: latest fresh desk decision per ticker
    desk_rows = db.execute(
        select(AgentDecision)
        .where(AgentDecision.as_of_date >= (now - timedelta(days=DESK_STALENESS_DAYS)).date())
        .order_by(AgentDecision.ticker, desc(AgentDecision.as_of_date))
    ).scalars().all()
    desk_by_ticker: Dict[str, AgentDecision] = {}
    for d in desk_rows:
        desk_by_ticker.setdefault(d.ticker.upper(), d)

    # Voice 3: today's quant recommendations (joined for ticker symbols)
    reco_rows = db.execute(
        select(Recommendation, Stock.symbol)
        .join(Stock, Stock.id == Recommendation.stock_id)
        .where(Recommendation.date >= (now - timedelta(days=2)).date())
        .order_by(desc(Recommendation.date))
    ).all()
    reco_by_ticker: Dict[str, Recommendation] = {}
    for reco, symbol in reco_rows:
        reco_by_ticker.setdefault(symbol.upper(), reco)

    tickers = set(by_ticker_signals) | set(desk_by_ticker) | set(reco_by_ticker)
    rankings: List[Dict[str, Any]] = []

    for ticker in tickers:
        components: Dict[str, Optional[float]] = {"signals": None, "desk": None, "recommendation": None}
        why: Dict[str, Any] = {}

        sigs = by_ticker_signals.get(ticker, [])
        if sigs:
            contributions = []
            contributors = []
            for s in sigs:
                source = source_for_signal(s.model_version, s.signal_metadata, s.signal_type)
                w = source_weight(tracks.get(source))
                c = signal_contribution(float(s.strength), float(s.confidence), s.direction, w)
                contributions.append(c)
                contributors.append({
                    "signal_type": s.signal_type,
                    "source": source,
                    "direction": s.direction,
                    "contribution": round(c, 3),
                    "source_win_rate": (tracks.get(source) or {}).get("win_rate"),
                })
            components["signals"] = round(max(-1.0, min(1.0, sum(contributions) / len(contributions))), 4)
            contributors.sort(key=lambda x: abs(x["contribution"]), reverse=True)
            why["signals"] = contributors[:3]

        desk = desk_by_ticker.get(ticker)
        if desk is not None:
            components["desk"] = round(desk_component(desk.decision, float(desk.conviction)), 4)
            why["desk"] = {
                "decision": desk.decision,
                "conviction": float(desk.conviction),
                "as_of_date": desk.as_of_date.isoformat(),
            }

        reco = reco_by_ticker.get(ticker)
        if reco is not None:
            components["recommendation"] = round(recommendation_component(float(reco.score)), 4)
            why["recommendation"] = {"action": reco.action, "score": float(reco.score)}

        composite = blend(components)
        rankings.append({
            "ticker": ticker,
            "composite": composite,
            "stance": stance_label(composite),
            "components": components,
            "why": why,
        })

    rankings.sort(key=lambda r: (r["composite"] is not None, r["composite"] or 0), reverse=True)
    return {
        "generated_at": now.isoformat(),
        "count": len(rankings[:limit]),
        "weights": COMPONENT_WEIGHTS,
        "track_records": tracks,
        "rankings": rankings[:limit],
        "disclaimer": (
            "Consolidated market stance from verified inputs — not investment advice. "
            "Source weights come from realized signal outcomes."
        ),
    }


# Tiny in-process cache: the view is identical for every visitor for minutes
# at a time, and the underlying tables only change on task cadence.
_cache: Dict[str, Any] = {"at": 0.0, "data": None}
CACHE_TTL_SECONDS = 300


def consolidated_rankings_cached(db: Session, limit: int = 25) -> Dict[str, Any]:
    # Cache the FULL computation and slice per request — otherwise the first
    # caller's limit poisons the cache for everyone (dashboard's limit=10
    # truncated API consumers asking for 30; observed 2026-06-11).
    if _cache["data"] is None or (time.monotonic() - _cache["at"]) >= CACHE_TTL_SECONDS:
        _cache["data"] = consolidated_rankings(db, limit=1000)
        _cache["at"] = time.monotonic()
    full = _cache["data"]
    sliced = dict(full)
    sliced["rankings"] = full["rankings"][:limit]
    sliced["count"] = len(sliced["rankings"])
    return sliced
