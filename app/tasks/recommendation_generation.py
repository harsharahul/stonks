"""
Recommendation Generation Task

Generates daily BUY/SELL/HOLD recommendations from signals + feature store.
Reads from ticker_features_daily and active signals, computes composite scores,
and persists to the recommendations table.
"""

import logging
from datetime import datetime, timedelta, date as date_type
from typing import Dict, List, Optional
from decimal import Decimal
from celery import shared_task

from app.core.database import SessionLocal
from app.models import Stock, Signal, Recommendation, ETLJobRun
from app.models.ticker_features_daily import TickerFeaturesDaily
from app.tasks.etl_helpers import get_or_create_etl_job

logger = logging.getLogger(__name__)

MODEL_VERSION = "v1.0.0"

# Component weights for composite score
WEIGHTS = {
    "momentum": 0.30,
    "sentiment": 0.25,
    "signal": 0.20,
    "volume": 0.15,
    "retail": 0.10,
}

# Action thresholds
BUY_THRESHOLD = 0.65
SELL_THRESHOLD = 0.35


def _safe_float(val, default=0.0) -> float:
    """Safely convert a potentially None/Decimal value to float."""
    if val is None:
        return default
    return float(val)


def _compute_momentum_component(features: TickerFeaturesDaily) -> float:
    """Score 0-1 based on momentum_14d and ret_5d."""
    momentum = _safe_float(features.momentum_14d)
    ret_5d = _safe_float(features.ret_5d)

    # momentum_14d typically ranges -0.20 to +0.20; normalize to 0-1
    mom_score = max(0.0, min(1.0, (momentum + 0.15) / 0.30))
    # ret_5d typically ranges -0.10 to +0.10
    ret_score = max(0.0, min(1.0, (ret_5d + 0.10) / 0.20))

    return mom_score * 0.6 + ret_score * 0.4


def _compute_sentiment_component(features: TickerFeaturesDaily) -> float:
    """Score 0-1 based on sent_mean_7d (already 0-1)."""
    sent = _safe_float(features.sent_mean_7d, 0.5)
    return max(0.0, min(1.0, sent))


def _compute_volume_component(features: TickerFeaturesDaily) -> float:
    """Score 0-1 based on vol_z. Higher volume z-score = more conviction."""
    vol_z = _safe_float(features.vol_z)
    # vol_z > 2 is notable, > 4 is extreme; map to 0-1
    return max(0.0, min(1.0, vol_z / 4.0))


def _compute_retail_component(features: TickerFeaturesDaily) -> float:
    """Score 0-1 based on WSB sentiment and retail buzz."""
    wsb_sent = _safe_float(features.wsb_sentiment_7d, 0.5)
    buzz = _safe_float(features.retail_buzz_score)

    return wsb_sent * 0.6 + buzz * 0.4


def _compute_signal_component(signals: List[Signal]) -> float:
    """Score 0-1 based on active signals' direction and strength."""
    if not signals:
        return 0.5  # neutral when no signals

    bullish_weight = 0.0
    bearish_weight = 0.0

    for sig in signals:
        strength = abs(_safe_float(sig.strength))
        confidence = _safe_float(sig.confidence)
        weight = strength * confidence

        if sig.direction == "bullish":
            bullish_weight += weight
        elif sig.direction == "bearish":
            bearish_weight += weight

    total = bullish_weight + bearish_weight
    if total == 0:
        return 0.5

    # 0 = fully bearish, 1 = fully bullish
    return max(0.0, min(1.0, bullish_weight / total))


def _build_rationale(
    features: TickerFeaturesDaily,
    signals: List[Signal],
    components: Dict[str, float],
) -> dict:
    """Build a rationale dict with top_signals, evidence, and notes."""
    # Rank components by weighted contribution
    weighted = [
        (name, value * WEIGHTS[name])
        for name, value in components.items()
    ]
    weighted.sort(key=lambda x: x[1], reverse=True)

    total_weighted = sum(w for _, w in weighted) or 1.0
    top_signals = [
        {"signal": name, "contribution": round(w / total_weighted, 2)}
        for name, w in weighted[:3]
    ]

    evidence = {
        "article_count_7d": features.article_count_7d or 0,
        "momentum_14d": round(_safe_float(features.momentum_14d), 4),
        "vol_z": round(_safe_float(features.vol_z), 2),
        "active_signals": len(signals),
    }

    # Generate human-readable notes
    score = sum(w for _, w in weighted)
    momentum = _safe_float(features.momentum_14d)
    sentiment = _safe_float(features.sent_mean_7d, 0.5)

    parts = []
    if momentum > 0.05:
        parts.append("Strong upward momentum")
    elif momentum < -0.05:
        parts.append("Downward momentum pressure")
    else:
        parts.append("Flat momentum")

    if sentiment > 0.65:
        parts.append("positive sentiment trend")
    elif sentiment < 0.35:
        parts.append("negative sentiment trend")
    else:
        parts.append("neutral sentiment")

    if _safe_float(features.vol_z) > 2.0:
        parts.append("elevated volume")

    bullish_sigs = sum(1 for s in signals if s.direction == "bullish")
    bearish_sigs = sum(1 for s in signals if s.direction == "bearish")
    if bullish_sigs > bearish_sigs:
        parts.append(f"{bullish_sigs} bullish signal(s)")
    elif bearish_sigs > bullish_sigs:
        parts.append(f"{bearish_sigs} bearish signal(s)")

    notes = " with ".join([parts[0], ", ".join(parts[1:])]) if len(parts) > 1 else parts[0]

    return {
        "top_signals": top_signals,
        "evidence": evidence,
        "notes": notes,
    }


def generate_recommendation_for_ticker(
    db,
    stock: Stock,
    features: TickerFeaturesDaily,
    signals: List[Signal],
    today: date_type,
) -> Optional[Recommendation]:
    """Generate a single recommendation for a stock."""
    # Compute individual components
    components = {
        "momentum": _compute_momentum_component(features),
        "sentiment": _compute_sentiment_component(features),
        "volume": _compute_volume_component(features),
        "signal": _compute_signal_component(signals),
        "retail": _compute_retail_component(features),
    }

    # Composite score
    score = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)
    score = max(0.0, min(1.0, score))

    # Determine action
    if score >= BUY_THRESHOLD:
        action = "BUY"
    elif score <= SELL_THRESHOLD:
        action = "SELL"
    else:
        action = "HOLD"

    rationale = _build_rationale(features, signals, components)

    # Upsert: check if recommendation already exists for this stock+date+version
    existing = db.query(Recommendation).filter(
        Recommendation.stock_id == stock.id,
        Recommendation.date == today,
        Recommendation.feature_version == MODEL_VERSION,
    ).first()

    if existing:
        existing.action = action
        existing.score = Decimal(str(round(score, 6)))
        existing.rationale = rationale
        existing.feature_date = features.date
        return existing
    else:
        rec = Recommendation(
            stock_id=stock.id,
            date=today,
            action=action,
            score=Decimal(str(round(score, 6))),
            model_version=MODEL_VERSION,
            rationale=rationale,
            feature_date=features.date,
            feature_version=MODEL_VERSION,
        )
        db.add(rec)
        return rec


@shared_task(bind=True)
def generate_daily_recommendations_task(self) -> Dict:
    """
    Generate daily recommendations for all active stocks with recent features.
    Reads from ticker_features_daily + signals, computes composite scores,
    and persists to recommendations table.
    """
    db = SessionLocal()
    task_id = self.request.id
    today = date_type.today()

    try:
        print(f"📊 Generating daily recommendations for {today}")

        # Get or reuse admin-created ETLJobRun
        job_run = get_or_create_etl_job(db, task_id, "recommendation_generation", {
            "task_id": task_id,
            "date": today.isoformat(),
        })

        # Get all active stocks
        stocks = db.query(Stock).filter(Stock.is_active == True).all()
        stock_map = {s.symbol: s for s in stocks}

        # Get recent features (last 3 days) for all tickers
        cutoff_date = today - timedelta(days=3)
        features_rows = (
            db.query(TickerFeaturesDaily)
            .filter(TickerFeaturesDaily.date >= cutoff_date)
            .order_by(TickerFeaturesDaily.date.desc())
            .all()
        )

        # Deduplicate: keep latest feature per ticker
        latest_features = {}
        for f in features_rows:
            if f.ticker not in latest_features:
                latest_features[f.ticker] = f

        # Get active (non-expired) signals grouped by ticker
        active_signals = db.query(Signal).filter(
            Signal.expires_at > datetime.utcnow()
        ).all()

        signals_by_ticker = {}
        for sig in active_signals:
            signals_by_ticker.setdefault(sig.ticker, []).append(sig)

        # Generate recommendations
        recs_created = 0
        recs_updated = 0
        ticker_results = {}

        for ticker, features in latest_features.items():
            stock = stock_map.get(ticker)
            if not stock:
                continue

            try:
                signals = signals_by_ticker.get(ticker, [])
                existing_count = db.query(Recommendation).filter(
                    Recommendation.stock_id == stock.id,
                    Recommendation.date == today,
                    Recommendation.feature_version == MODEL_VERSION,
                ).count()

                rec = generate_recommendation_for_ticker(
                    db, stock, features, signals, today
                )

                if rec:
                    if existing_count > 0:
                        recs_updated += 1
                    else:
                        recs_created += 1
                    ticker_results[ticker] = {
                        "action": rec.action,
                        "score": float(rec.score),
                    }
                    print(f"   {'📈' if rec.action == 'BUY' else '📉' if rec.action == 'SELL' else '➡️'} {ticker}: {rec.action} (score: {float(rec.score):.3f})")

            except Exception as e:
                logger.error(f"Error generating recommendation for {ticker}: {e}")
                continue

        db.commit()

        # Update job run
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = recs_created + recs_updated
        job_run.details.update({
            "recommendations_created": recs_created,
            "recommendations_updated": recs_updated,
            "tickers_processed": len(ticker_results),
            "ticker_results": ticker_results,
        })
        db.commit()

        print(f"✅ Recommendation generation complete: {recs_created} new, {recs_updated} updated")
        return {
            "status": "success",
            "date": today.isoformat(),
            "recommendations_created": recs_created,
            "recommendations_updated": recs_updated,
            "tickers_processed": len(ticker_results),
        }

    except Exception as e:
        if "job_run" in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({"error": str(e), "error_type": type(e).__name__})
            db.commit()
        print(f"❌ Error in recommendation generation: {e}")
        raise

    finally:
        db.close()
