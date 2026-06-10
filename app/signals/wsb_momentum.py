"""WSB momentum plugin — the reference implementation of the signal SDK.

Reads the already-ingested WSB features (ticker_features_daily) and emits a
social_momentum trading signal for tickers with unusual retail buzz. This is
deliberately a DB-backed plugin: it shows contributors the full contract
(metadata → fetch_signals → RawSignal with trading hints) without any
external API keys.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import desc, select

from app.core.signal_framework import (
    RawSignal,
    SignalSource,
    SignalSourceMetadata,
    SignalSourceType,
    SignalType,
    register_signal_source,
)

logger = logging.getLogger(__name__)

DEFAULT_MIN_MENTIONS = 25       # 7d WSB mentions below this are noise
DEFAULT_MIN_BUZZ = 0.5          # retail_buzz_score floor (z-ish scale)


@register_signal_source("wsb_momentum", default_enabled=True)
class WSBMomentumSource(SignalSource):
    """Emit social_momentum signals from WSB retail-buzz features."""

    def get_metadata(self) -> SignalSourceMetadata:
        return SignalSourceMetadata(
            name="WSB Momentum",
            description=(
                "Social momentum from r/wallstreetbets: flags tickers whose "
                "7-day mention count and retail buzz score spike, with "
                "direction from aggregated WSB sentiment."
            ),
            source_type=SignalSourceType.SOCIAL_MEDIA,
            supported_signal_types=[SignalType.SOCIAL_MOMENTUM],
            update_frequency=timedelta(minutes=30),
            reliability_score=0.6,
            data_quality_score=0.7,
            required_config=[],  # reads our own DB — no keys needed
        )

    async def configure(self) -> bool:
        return True

    async def health_check(self) -> bool:
        return True

    async def fetch_signals(self, since: Optional[datetime] = None) -> List[RawSignal]:
        # Sync DB access is fine here: the dispatcher runs us inside a Celery
        # worker, not the API event loop.
        from app.core.database import SessionLocal
        from app.models.ticker_features_daily import TickerFeaturesDaily

        min_mentions = int(self.config.get("min_mentions", DEFAULT_MIN_MENTIONS))
        min_buzz = float(self.config.get("min_buzz", DEFAULT_MIN_BUZZ))

        signals: List[RawSignal] = []
        with SessionLocal() as db:
            latest_date = db.execute(
                select(TickerFeaturesDaily.date).order_by(desc(TickerFeaturesDaily.date)).limit(1)
            ).scalar_one_or_none()
            if latest_date is None:
                return signals

            rows = db.execute(
                select(TickerFeaturesDaily).where(
                    TickerFeaturesDaily.date == latest_date,
                    TickerFeaturesDaily.wsb_mention_count_7d >= min_mentions,
                    TickerFeaturesDaily.retail_buzz_score >= min_buzz,
                )
            ).scalars().all()

            for row in rows:
                sentiment = float(row.wsb_sentiment_7d or 0.0)
                buzz = float(row.retail_buzz_score or 0.0)
                mentions = int(row.wsb_mention_count_7d or 0)
                direction = "bullish" if sentiment > 0.05 else "bearish" if sentiment < -0.05 else "neutral"
                # Strength: signed buzz, clamped; confidence grows with mentions.
                strength = max(-1.0, min(1.0, (1 if sentiment >= 0 else -1) * min(buzz / 3.0, 1.0)))
                confidence = max(0.0, min(1.0, mentions / 200.0))

                signals.append(
                    RawSignal(
                        source_id="wsb_momentum",
                        source_type=SignalSourceType.SOCIAL_MEDIA,
                        timestamp=datetime.utcnow(),
                        ticker=row.ticker,
                        raw_data={
                            "feature_date": latest_date.isoformat(),
                            "wsb_mention_count_7d": mentions,
                            "wsb_sentiment_7d": sentiment,
                            "retail_buzz_score": buzz,
                            "meme_stock_indicator": float(row.meme_stock_indicator or 0.0),
                        },
                        metadata={"fingerprint": f"wsb_momentum:{row.ticker}:{latest_date.isoformat()}"},
                        signal_type_hint="social_momentum",
                        direction=direction,
                        strength=strength,
                        confidence=confidence,
                        timeframe="daily",
                    )
                )
        logger.info("wsb_momentum: %d signals at %s", len(signals), latest_date)
        return signals
