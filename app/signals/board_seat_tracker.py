"""Board seat tracker plugin.

Emits positioning signals for companies where a tracked individual holds a
board or advisory seat. The individual and the positions come from the
source config. The module carries no names.

Config keys:
    person       display label for the tracked individual
    positions    {ticker: {name, role, joined (YYYY-MM-DD), note, weight}} (required)

``role`` must be ``board_of_directors`` or ``advisory_board``. ``weight``
(0 to 1) is the operator's conviction for the position; entries at or below
0.05 are ignored. Strength is ``min(1, 2 * weight)`` and confidence is
``min(0.85, 2.5 * weight + 0.20)``. Signals re-emit daily (fingerprint keyed
by day) for as long as the position stays configured.
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

SOURCE_ID = "board_seat_tracker"
VALID_ROLES = ("board_of_directors", "advisory_board")
MIN_WEIGHT = 0.05


@register_signal_source(SOURCE_ID, default_enabled=True)
class BoardSeatTrackerSource(SignalSource):
    """Positioning signals for companies where a tracked individual sits on the board."""

    def get_metadata(self) -> SignalSourceMetadata:
        return SignalSourceMetadata(
            name="Board Seat Tracker",
            description=(
                "Positioning signals for companies where a tracked individual "
                "holds a board or advisory seat, weighted by role and by the "
                "configured conviction. The individual and the positions come "
                "from the source config."
            ),
            source_type=SignalSourceType.POLITICIAN_TRADES,
            supported_signal_types=[SignalType.INSIDER_ACTIVITY],
            update_frequency=timedelta(hours=24),
            reliability_score=0.5,
            data_quality_score=0.8,
            required_config=["positions"],
        )

    async def configure(self) -> bool:
        return True

    async def health_check(self) -> bool:
        return True

    @property
    def person(self) -> str:
        return str(self.config.get("person") or "tracked individual")

    @property
    def positions(self) -> Dict[str, dict]:
        raw = self.config.get("positions") or {}
        return raw if isinstance(raw, dict) else {}

    async def fetch_signals(self, since: Optional[datetime] = None) -> List[RawSignal]:
        today_key = date.today().isoformat()
        signals: List[RawSignal] = []
        for ticker, info in self.positions.items():
            if not isinstance(info, dict):
                continue
            try:
                weight = float(info.get("weight", 0))
            except (TypeError, ValueError):
                continue
            role = info.get("role", "")
            if weight <= MIN_WEIGHT or role not in VALID_ROLES:
                continue
            confidence = round(min(0.85, weight * 2.5 + 0.20), 4)
            signals.append(
                RawSignal(
                    source_id=SOURCE_ID,
                    source_type=SignalSourceType.POLITICIAN_TRADES,
                    timestamp=datetime.utcnow(),
                    ticker=ticker,
                    raw_data={
                        "person": self.person,
                        "role": role,
                        "joined": info.get("joined"),
                        "company": info.get("name"),
                        "note": info.get("note", ""),
                        "weight": weight,
                    },
                    metadata={"fingerprint": f"{SOURCE_ID}:{ticker}:{today_key}"},
                    signal_type_hint="insider_activity",
                    direction="bullish",
                    strength=round(min(1.0, weight * 2.0), 4),
                    confidence=confidence,
                    timeframe="weekly",
                )
            )
        logger.info("%s: %d signals", SOURCE_ID, len(signals))
        return signals
