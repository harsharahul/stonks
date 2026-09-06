"""Fund 13F tracker plugin.

Emits positioning signals from a tracked fund's most recent quarterly 13F
holdings. Strength scales with portfolio weight; confidence blends weight
with filing freshness; both decay linearly to zero as the filing ages, so a
stale filing stops emitting until the holdings are refreshed. The fund, the
filing date, and the holdings come from the source config. Automatic
refresh from EDGAR by CIK is on the roadmap.

Config keys:
    fund              display label for the tracked fund
    cik               the fund's SEC CIK (recorded on each signal)
    filing_date       YYYY-MM-DD of the tracked 13F (required)
    holdings          {ticker: {name, weight, sector, position_type, note}} (required)
    stale_after_days  days until the filing counts as stale (default 150)
    min_weight        skip positions below this portfolio weight (default 0.014)

``weight`` is the position's share of the declared equity portfolio value
(0 to 1). Strength is ``min(1, 4 * weight)`` times the decay; confidence is
``min(0.9, 0.35 + 2 * weight)`` times the decay.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from app.core.signal_framework import (
    RawSignal,
    SignalSource,
    SignalSourceMetadata,
    SignalSourceType,
    SignalType,
    register_signal_source,
)

logger = logging.getLogger(__name__)

SOURCE_ID = "fund_13f_tracker"
DEFAULT_STALE_AFTER_DAYS = 150   # past the next quarter's filing window plus grace
DEFAULT_MIN_WEIGHT = 0.014       # sub-1.4% positions are noise


def filing_decay(filing_date: str, today: Optional[date] = None, stale_after_days: int = DEFAULT_STALE_AFTER_DAYS) -> float:
    """1.0 on filing day, linear decay, 0.0 at ``stale_after_days``."""
    today = today or date.today()
    try:
        filed = datetime.strptime(filing_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return 0.0
    age = (today - filed).days
    if age < 0:
        return 0.0
    return max(0.0, 1.0 - age / max(1, stale_after_days))


@register_signal_source(SOURCE_ID, default_enabled=True)
class Fund13FTrackerSource(SignalSource):
    """Positioning signals from a tracked fund's quarterly 13F holdings."""

    def get_metadata(self) -> SignalSourceMetadata:
        return SignalSourceMetadata(
            name="Fund 13F Tracker",
            description=(
                "Positioning signals from a tracked fund's latest quarterly 13F "
                "holdings, scaled by portfolio weight and decaying as the "
                "filing ages. The fund, filing date, and holdings come from "
                "the source config."
            ),
            source_type=SignalSourceType.REGULATORY,
            supported_signal_types=[SignalType.INSIDER_ACTIVITY],
            update_frequency=timedelta(hours=24),
            reliability_score=0.7,
            data_quality_score=0.9,
            required_config=["filing_date", "holdings"],
        )

    async def configure(self) -> bool:
        return True

    async def health_check(self) -> bool:
        return True

    @property
    def fund(self) -> str:
        return str(self.config.get("fund") or "tracked fund")

    @property
    def holdings(self) -> Dict[str, dict]:
        raw = self.config.get("holdings") or {}
        return raw if isinstance(raw, dict) else {}

    def _number(self, key: str, default: float) -> float:
        try:
            return float(self.config.get(key, default))
        except (TypeError, ValueError):
            return default

    async def fetch_signals(self, since: Optional[datetime] = None) -> List[RawSignal]:
        filing_date = str(self.config.get("filing_date") or "")
        stale_after = int(self._number("stale_after_days", DEFAULT_STALE_AFTER_DAYS))
        min_weight = self._number("min_weight", DEFAULT_MIN_WEIGHT)
        decay = filing_decay(filing_date, stale_after_days=stale_after)
        if decay <= 0:
            logger.info("%s: filing is stale, emitting nothing until the holdings are refreshed", SOURCE_ID)
            return []

        today_key = date.today().isoformat()
        signals: List[RawSignal] = []
        for ticker, info in self.holdings.items():
            if not isinstance(info, dict):
                continue
            try:
                weight = float(info.get("weight", 0))
            except (TypeError, ValueError):
                continue
            if weight < min_weight:
                continue
            strength = round(min(1.0, weight * 4.0) * decay, 4)
            confidence = round(min(0.9, 0.35 + weight * 2.0) * decay, 4)
            signals.append(
                RawSignal(
                    source_id=SOURCE_ID,
                    source_type=SignalSourceType.REGULATORY,
                    timestamp=datetime.utcnow(),
                    ticker=ticker,
                    raw_data={
                        "fund": self.fund,
                        "cik": self.config.get("cik"),
                        "filing_date": filing_date,
                        "portfolio_weight": weight,
                        "sector": info.get("sector"),
                        "position_type": info.get("position_type"),
                        "note": info.get("note", ""),
                    },
                    metadata={"fingerprint": f"{SOURCE_ID}:{ticker}:{today_key}"},
                    signal_type_hint="smart_money_13f",
                    direction="bullish",
                    strength=strength,
                    confidence=confidence,
                    timeframe="weekly",
                )
            )
        logger.info("%s: %d signals (decay %.2f)", SOURCE_ID, len(signals), decay)
        return signals
