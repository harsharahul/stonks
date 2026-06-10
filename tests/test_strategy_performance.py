"""Unit tests for verified track-record math — pure logic, no DB."""
from app.tasks.strategy_performance import compute_round_trips, summarize


def _fill(symbol, side, qty, price):
    return {"symbol": symbol, "side": side, "qty": qty, "price": price}


class TestRoundTrips:
    def test_simple_winning_round_trip(self):
        trips = compute_round_trips([
            _fill("AAPL", "buy", 10, 100.0),
            _fill("AAPL", "sell", 10, 110.0),
        ])
        assert len(trips) == 1
        assert trips[0]["pnl"] == 100.0
        assert trips[0]["return_pct"] == 10.0

    def test_fifo_matching_across_lots(self):
        trips = compute_round_trips([
            _fill("AAPL", "buy", 10, 100.0),
            _fill("AAPL", "buy", 10, 120.0),
            _fill("AAPL", "sell", 15, 130.0),
        ])
        # 10 @ 100 fully closed, 5 of the 120 lot closed
        assert len(trips) == 2
        assert trips[0]["pnl"] == 300.0    # (130-100)*10
        assert trips[1]["pnl"] == 50.0     # (130-120)*5

    def test_open_position_not_counted(self):
        trips = compute_round_trips([_fill("NVDA", "buy", 5, 500.0)])
        assert trips == []

    def test_symbols_isolated(self):
        trips = compute_round_trips([
            _fill("AAPL", "buy", 10, 100.0),
            _fill("TSLA", "sell", 10, 200.0),  # no open TSLA lot → ignored
        ])
        assert trips == []

    def test_unmatched_sell_quantity_ignored(self):
        trips = compute_round_trips([
            _fill("AAPL", "buy", 5, 100.0),
            _fill("AAPL", "sell", 10, 110.0),
        ])
        assert len(trips) == 1
        assert trips[0]["qty"] == 5


class TestSummarize:
    def test_win_rate_and_pnl(self):
        trips = compute_round_trips([
            _fill("AAPL", "buy", 10, 100.0),
            _fill("AAPL", "sell", 10, 110.0),   # +100
            _fill("TSLA", "buy", 10, 200.0),
            _fill("TSLA", "sell", 10, 190.0),   # -100
        ])
        stats = summarize(trips, trade_count=4)
        assert stats["closed_trade_count"] == 2
        assert stats["win_count"] == 1
        assert stats["realized_pnl"] == 0.0
        assert stats["avg_return_pct"] == 2.5  # (+10% + -5%) / 2

    def test_empty_history(self):
        stats = summarize([], trade_count=0)
        assert stats["closed_trade_count"] == 0
        assert stats["realized_pnl"] is None
        assert stats["max_drawdown_pct"] is None

    def test_drawdown_negative_when_losses_follow_gains(self):
        trips = compute_round_trips([
            _fill("A", "buy", 1, 100.0), _fill("A", "sell", 1, 200.0),   # +100
            _fill("B", "buy", 1, 100.0), _fill("B", "sell", 1, 40.0),    # -60
        ])
        stats = summarize(trips, trade_count=4)
        assert stats["max_drawdown_pct"] == -60.0
