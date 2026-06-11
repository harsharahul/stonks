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
