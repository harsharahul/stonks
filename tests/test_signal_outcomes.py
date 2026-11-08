"""Pure-logic tests for signal outcome scoring (no DB required)."""
import pytest

from app.tasks.signal_outcomes import evaluate_outcome, source_for_signal


class TestSourceForSignal:
    def test_plugin_metadata_wins(self):
        assert source_for_signal("v1.0.0", {"source_plugin": "capitol_trades"}, "insider_buy") == "capitol_trades"

    def test_plugin_model_version_fallback(self):
        assert source_for_signal("plugin:wsb_momentum", {}, "wsb_momentum") == "wsb_momentum"

    def test_anomaly_prefix(self):
        assert source_for_signal("v1.0.0", None, "anomaly_price_spike") == "anomaly_detector"
        assert source_for_signal("v1.0.0", None, "urgent_volume") == "anomaly_detector"

    def test_rule_engine_default(self):
        assert source_for_signal("v1.0.0", None, "momentum_bullish") == "rule_engine"
        assert source_for_signal(None, None, "strong_buy") == "rule_engine"


class TestEvaluateOutcome:
    def test_bullish_win(self):
        ret, win = evaluate_outcome("bullish", 100.0, 105.0)
        assert ret == pytest.approx(0.05)
        assert win is True

    def test_bullish_loss(self):
        ret, win = evaluate_outcome("bullish", 100.0, 95.0)
        assert ret == pytest.approx(-0.05)
        assert win is False

    def test_bearish_win_on_drop(self):
        ret, win = evaluate_outcome("bearish", 100.0, 90.0)
        assert ret == pytest.approx(-0.10)
        assert win is True

    def test_bearish_loss_on_rally(self):
        ret, win = evaluate_outcome("bearish", 100.0, 110.0)
        assert win is False

    def test_neutral_has_no_win(self):
        ret, win = evaluate_outcome("neutral", 100.0, 110.0)
        assert ret == pytest.approx(0.10)
        assert win is None

    def test_missing_prices_unscoreable(self):
        assert evaluate_outcome("bullish", None, 105.0) == (None, None)
        assert evaluate_outcome("bullish", 100.0, None) == (None, None)

    def test_zero_entry_unscoreable(self):
        assert evaluate_outcome("bullish", 0.0, 105.0) == (None, None)


# ---------------------------------------------------------------------------
# Scoring loop: must walk the whole pending set, not just the oldest batch
# ---------------------------------------------------------------------------
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.tasks.signal_outcomes import BarCache, iter_pending_signals, score_signals


@dataclass
class _Bar:
    date: date
    close: float


@dataclass
class _Sig:
    id: str
    ticker: str
    direction: str
    generated_at: datetime
    signal_type: str = "insider_activity"
    model_version: str = "plugin:board_seat_tracker"
    signal_metadata: dict = None


def _bars_for(table):
    """Fake price lookup: {ticker: [(date, close), ...]} filtered to [start, end]."""
    calls = []

    def fetch(ticker, start, end):
        calls.append(ticker)
        return [_Bar(d, c) for d, c in table.get(ticker, []) if start <= d <= end]

    fetch.calls = calls
    return fetch


def _daily(start: date, closes):
    return [(start + timedelta(days=i), c) for i, c in enumerate(closes)]


class TestScoreSignals:
    def test_unpriced_backlog_does_not_block_scoreable_signals(self):
        """Regression: 550 unscoreable signals ahead of 50 scoreable ones.

        The old scorer took the 500 oldest pending rows, all of them for a
        ticker without prices, and never reached the newer signals behind them.
        """
        t0 = datetime(2026, 6, 12, tzinfo=timezone.utc)
        pending = [_Sig(f"old{i}", "NOPX", "bullish", t0 + timedelta(hours=i)) for i in range(550)]
        t1 = datetime(2026, 8, 1, tzinfo=timezone.utc)
        pending += [_Sig(f"new{i}", "NVDA", "bullish", t1 + timedelta(hours=i)) for i in range(50)]
        table = {"NVDA": _daily(date(2026, 7, 25), [100 + i for i in range(30)])}
        sink = []

        stats = score_signals(pending, BarCache(_bars_for(table)), sink.append, horizon_days=5)

        assert stats["scored"] == 50
        assert stats["skipped"] == 550
        assert stats["examined"] == 600
        assert len(sink) == 50
        assert all(o.ticker == "NVDA" and o.win is True for o in sink)

    def test_scored_cap_stops_the_run_but_not_before_scoreable_rows(self):
        t1 = datetime(2026, 8, 1, tzinfo=timezone.utc)
        pending = [_Sig(f"s{i}", "NVDA", "bullish", t1 + timedelta(hours=i)) for i in range(20)]
        table = {"NVDA": _daily(date(2026, 7, 25), [100] * 30)}
        sink = []

        stats = score_signals(pending, BarCache(_bars_for(table)), sink.append, horizon_days=5, max_scored=7)

        assert stats["scored"] == 7
        assert stats["capped"] is True
        assert len(sink) == 7

    def test_outcome_rows_carry_source_and_prices(self):
        t1 = datetime(2026, 8, 3, tzinfo=timezone.utc)
        sig = _Sig("s", "NVDA", "bearish", t1, signal_metadata={"source_plugin": "public_figure_mentions"})
        table = {"NVDA": _daily(date(2026, 8, 3), [100, 101, 99, 98, 97, 96, 95, 94])}
        sink = []

        score_signals([sig], BarCache(_bars_for(table)), sink.append, horizon_days=5)

        (o,) = sink
        assert o.source == "public_figure_mentions"
        assert float(o.entry_price) == 100 and float(o.exit_price) == 96
        assert o.win is True and o.horizon_days == 5


class TestBarCache:
    def test_one_fetch_per_ticker(self):
        fetch = _bars_for({"NVDA": _daily(date(2026, 8, 1), [100] * 40)})
        cache = BarCache(fetch)
        for i in range(25):
            cache.bars("NVDA", date(2026, 8, 1) + timedelta(days=i), date(2026, 8, 1) + timedelta(days=i + 12))
        assert fetch.calls == ["NVDA"]

    def test_backfill_runs_once_for_unpriced_ticker_and_is_bounded(self):
        table = {}
        fetch = _bars_for(table)
        backfilled = []

        def backfill(ticker, start, end):
            backfilled.append(ticker)
            if ticker == "DOMI":
                table["DOMI"] = _daily(start, [10] * ((end - start).days + 1))
                return len(table["DOMI"])
            return 0

        cache = BarCache(fetch, backfill=backfill, max_backfills=2)
        s, e = date(2026, 8, 1), date(2026, 8, 12)
        assert cache.bars("DOMI", s, e)  # backfill fills it in
        assert cache.bars("DOMI", s, e)  # served from cache, no second backfill
        assert cache.bars("NOPX", s, e) == []  # backfill returns nothing
        assert cache.bars("NOPX", s, e) == []  # not retried within the run
        assert cache.bars("ZZZZ", s, e) == []  # cap reached: no backfill attempted
        assert backfilled == ["DOMI", "NOPX"]
        assert cache.stats() == {"tickers": 3, "backfilled": 1, "backfill_attempts": 2, "unpriced": 2}


class TestIterPendingSignals:
    class _FakeDB:
        def __init__(self, pages):
            self.pages = list(pages)
            self.statements = []

        def execute(self, stmt):
            self.statements.append(stmt)
            page = self.pages.pop(0) if self.pages else []
            fake = self

            class _R:
                def scalars(self_inner):
                    return self_inner

                def all(self_inner):
                    return page

            return _R()

    def test_walks_pages_until_a_short_page(self):
        t0 = datetime(2026, 6, 12, tzinfo=timezone.utc)
        rows = [_Sig(f"s{i}", "NVDA", "bullish", t0 + timedelta(hours=i)) for i in range(7)]
        db = self._FakeDB([rows[:3], rows[3:6], rows[6:]])

        got = list(iter_pending_signals(db, horizon_cutoff=datetime(2026, 9, 5, tzinfo=timezone.utc), age_floor=t0, page_size=3))

        assert [s.id for s in got] == [s.id for s in rows]
        assert len(db.statements) == 3

    def test_empty(self):
        db = self._FakeDB([[]])
        assert list(iter_pending_signals(db, horizon_cutoff=datetime.now(timezone.utc), age_floor=datetime.now(timezone.utc), page_size=3)) == []


class TestBackfillSameSessionVisibility:
    """Backfilled bars must be visible to the re-read within the same run.

    Regression: the scorer re-read prices through a helper that opened its own
    database session, so rows the backfill had only flushed (not committed) in
    the run's session were invisible, and backfilled tickers scored a run late.
    The cache must re-read through the same fetch the backfill fed, not a fresh
    one.
    """

    def test_backfilled_bars_score_in_the_same_run(self):
        committed = {}   # what a fresh session would see: nothing yet
        flushed = {}     # what the run's session sees after a flush

        def session_fetch(ticker, start, end):
            return [b for b in flushed.get(ticker, []) if start <= b.date <= end]

        def backfill(ticker, start, end):
            rows = _daily(date(2026, 8, 3), [100 + i for i in range(20)])
            flushed[ticker] = [_Bar(d, c) for d, c in rows]  # flushed, not committed
            return len(flushed[ticker])

        cache = BarCache(session_fetch, backfill=backfill, max_backfills=5)
        sig = _Sig("s", "LMT", "bullish", datetime(2026, 8, 3, tzinfo=timezone.utc),
                   model_version="plugin:fund_13f_tracker")
        sink = []
        stats = score_signals([sig], cache, sink.append, horizon_days=5)

        assert stats["scored"] == 1
        assert sink[0].source == "fund_13f_tracker"
        assert committed == {}  # proves scoring did not depend on a committed/fresh read
