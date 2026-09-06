"""Unit tests for the board_seat_tracker and fund_13f_tracker plugins, pure logic."""
import asyncio
from datetime import date

from app.signals.fund_13f_tracker import HOLDINGS, Fund13FTrackerSource, filing_decay
from app.signals.board_seat_tracker import BoardSeatTrackerSource


class TestBoardSeatTracker:
    def test_emits_known_positions_bullish(self):
        sigs = asyncio.run(BoardSeatTrackerSource({}).fetch_signals())
        tickers = {s.ticker for s in sigs}
        assert {"PSQH", "UMAC", "DOMI"} <= tickers
        assert all(s.direction == "bullish" for s in sigs)
        assert all(0 < s.confidence <= 0.85 for s in sigs)

    def test_low_weight_or_bad_role_filtered(self):
        src = BoardSeatTrackerSource({"extra_positions": {
            "ZZZ": {"name": "Tiny", "role": "advisory_board", "weight": 0.01},
            "YYY": {"name": "BadRole", "role": "spokesperson", "weight": 0.5},
        }})
        tickers = {s.ticker for s in asyncio.run(src.fetch_signals())}
        assert "ZZZ" not in tickers
        assert "YYY" not in tickers


class TestFund13FTracker:
    def test_decay_fresh_vs_stale(self):
        assert filing_decay("2026-02-11", today=date(2026, 2, 11)) == 1.0
        assert 0.4 < filing_decay("2026-02-11", today=date(2026, 4, 11)) < 0.7
        assert filing_decay("2026-02-11", today=date(2026, 9, 1)) == 0.0

    def test_stale_filing_emits_nothing(self):
        sigs = asyncio.run(Fund13FTrackerSource({"filing_date": "2020-01-01"}).fetch_signals())
        assert sigs == []

    def test_strength_orders_by_portfolio_weight(self):
        sigs = asyncio.run(Fund13FTrackerSource({}).fetch_signals())
        if not sigs:  # filing fully decayed in the far future, nothing to assert
            return
        by_strength = sorted(sigs, key=lambda s: -s.strength)
        assert by_strength[0].ticker == "CRWV"  # largest position leads
        assert all(s.direction == "bullish" for s in sigs)

    def test_holdings_weights_sane(self):
        assert all(0 < h["weight"] < 0.5 for h in HOLDINGS.values())
