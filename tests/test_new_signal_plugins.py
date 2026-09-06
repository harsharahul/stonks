"""Unit tests for the configurable tracker plugins: pure logic, fictional config."""
import asyncio
from datetime import date, timedelta

from app.signals.board_seat_tracker import BoardSeatTrackerSource
from app.signals.fund_13f_tracker import Fund13FTrackerSource, filing_decay
from app.signals.public_figure_mentions import PublicFigureMentionsSource

POSITIONS = {
    "AAAA": {"name": "Alpha Holdings", "role": "board_of_directors", "joined": "2025-01-01", "weight": 0.35},
    "BBBB": {"name": "Beta Machines", "role": "advisory_board", "joined": "2025-02-01", "weight": 0.30},
}

HOLDINGS = {
    "CCCC": {"name": "Gamma Compute", "weight": 0.22, "sector": "compute", "position_type": "SH"},
    "DDDD": {"name": "Delta Power", "weight": 0.10, "sector": "power", "position_type": "SH+CALL"},
    "EEEE": {"name": "Epsilon Tiny", "weight": 0.005, "sector": "misc", "position_type": "SH"},
}


class TestBoardSeatTracker:
    def test_requires_positions(self):
        errors = asyncio.run(BoardSeatTrackerSource({}).validate_config())
        assert errors

    def test_emits_configured_positions_bullish(self):
        sigs = asyncio.run(BoardSeatTrackerSource({"person": "Example Person", "positions": POSITIONS}).fetch_signals())
        assert {s.ticker for s in sigs} == {"AAAA", "BBBB"}
        assert all(s.direction == "bullish" for s in sigs)
        assert all(0 < s.confidence <= 0.85 for s in sigs)
        assert all(s.raw_data["person"] == "Example Person" for s in sigs)

    def test_low_weight_or_bad_role_filtered(self):
        src = BoardSeatTrackerSource({"positions": {
            **POSITIONS,
            "ZZZZ": {"name": "Tiny", "role": "advisory_board", "weight": 0.01},
            "YYYY": {"name": "BadRole", "role": "spokesperson", "weight": 0.5},
        }})
        tickers = {s.ticker for s in asyncio.run(src.fetch_signals())}
        assert "ZZZZ" not in tickers
        assert "YYYY" not in tickers


class TestFund13FTracker:
    def test_decay_fresh_vs_stale(self):
        assert filing_decay("2026-02-11", today=date(2026, 2, 11)) == 1.0
        assert 0.4 < filing_decay("2026-02-11", today=date(2026, 4, 11)) < 0.7
        assert filing_decay("2026-02-11", today=date(2026, 9, 1)) == 0.0
        assert filing_decay("not-a-date") == 0.0

    def test_stale_filing_emits_nothing(self):
        src = Fund13FTrackerSource({"filing_date": "2020-01-01", "holdings": HOLDINGS})
        assert asyncio.run(src.fetch_signals()) == []

    def test_strength_orders_by_portfolio_weight(self):
        fresh = (date.today() - timedelta(days=3)).isoformat()
        src = Fund13FTrackerSource({"fund": "Example Fund", "filing_date": fresh, "holdings": HOLDINGS})
        sigs = asyncio.run(src.fetch_signals())
        assert {s.ticker for s in sigs} == {"CCCC", "DDDD"}  # EEEE is below min_weight
        by_strength = sorted(sigs, key=lambda s: -s.strength)
        assert by_strength[0].ticker == "CCCC"
        assert all(s.direction == "bullish" for s in sigs)
        assert all(s.raw_data["fund"] == "Example Fund" for s in sigs)

    def test_requires_filing_date_and_holdings(self):
        assert asyncio.run(Fund13FTrackerSource({"holdings": HOLDINGS}).validate_config())
        assert asyncio.run(Fund13FTrackerSource({"filing_date": "2026-01-01"}).validate_config())


class TestPublicFigureMentions:
    def test_requires_keywords(self):
        assert asyncio.run(PublicFigureMentionsSource({}).validate_config())

    def test_decay_filters_stale_mentions(self):
        src = PublicFigureMentionsSource({"keywords": ["Example"], "mentions": {"ZZZZ": {
            "name": "Stale Corp", "mention_date": "2020-01-01", "statement": "old", "source_type": "speech",
        }}})
        assert "ZZZZ" not in [s.ticker for s in src._curated_mention_signals(date.today().isoformat())]

    def test_fresh_mention_emits_bullish(self):
        fresh = (date.today() - timedelta(days=2)).isoformat()
        src = PublicFigureMentionsSource({"figure": "Example Person", "keywords": ["Example"], "mentions": {"FRSH": {
            "name": "Fresh Corp", "mention_date": fresh, "statement": "new", "source_type": "post",
        }}})
        sigs = [s for s in src._curated_mention_signals(date.today().isoformat()) if s.ticker == "FRSH"]
        assert len(sigs) == 1
        assert sigs[0].direction == "bullish"
        assert sigs[0].confidence > 0.5
        assert sigs[0].raw_data["figure"] == "Example Person"

    def test_prior_position_raises_confidence(self):
        fresh = (date.today() - timedelta(days=1)).isoformat()
        base = {"keywords": ["Example"], "mentions": {"FRSH": {"name": "Fresh", "mention_date": fresh}}}
        plain = PublicFigureMentionsSource(base)._curated_mention_signals(date.today().isoformat())[0]
        held = PublicFigureMentionsSource({**base, "mentions": {"FRSH": {**base["mentions"]["FRSH"], "prior_position": True}}})
        assert held._curated_mention_signals(date.today().isoformat())[0].confidence > plain.confidence

    def test_news_scan_disabled_without_watchlist(self):
        src = PublicFigureMentionsSource({"keywords": ["Example"]})
        assert src._news_scan_signals(date.today().isoformat()) == []
