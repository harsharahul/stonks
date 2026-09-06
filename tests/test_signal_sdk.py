"""Unit tests for the signal plugin SDK, pure logic, no network or DB."""
from datetime import datetime

import pytest

from app.core.signal_framework import (
    RawSignal,
    SignalSourceType,
    register_default_sources,
    signal_registry,
)
from app.tasks.signal_dispatch import raw_signal_to_row


def _raw(**overrides) -> RawSignal:
    base = dict(
        source_id="test_source",
        source_type=SignalSourceType.NEWS_FEEDS,
        timestamp=datetime(2026, 6, 10, 12, 0, 0),
        raw_data={"why": "test"},
        metadata={},
        ticker="AAPL",
        signal_type_hint="news_catalyst",
        direction="bullish",
        strength=0.6,
        confidence=0.7,
    )
    base.update(overrides)
    return RawSignal(**base)


class TestRegistry:
    def test_bundled_plugins_register(self):
        register_default_sources()
        sources = signal_registry.list_available_sources()
        assert "wsb_momentum" in sources
        assert "capitol_trades" in sources
        assert "public_figure_mentions" in sources
        assert "board_seat_tracker" in sources
        assert "fund_13f_tracker" in sources

    def test_register_is_idempotent(self):
        register_default_sources()
        before = set(signal_registry.list_available_sources())
        register_default_sources()
        assert set(signal_registry.list_available_sources()) == before


class TestRawSignalMapping:
    def test_full_signal_maps_to_row(self):
        row = raw_signal_to_row(_raw())
        assert row is not None
        assert row.ticker == "AAPL"
        assert row.signal_type == "news_catalyst"
        assert row.direction == "bullish"
        assert float(row.strength) == 0.6
        assert float(row.confidence) == 0.7
        assert row.model_version == "plugin:test_source"
        assert row.signal_metadata["source_plugin"] == "test_source"
        assert row.expires_at is not None

    def test_informational_signal_skipped(self):
        # No direction/strength hints → not a trading signal
        assert raw_signal_to_row(_raw(direction=None, strength=None)) is None
        assert raw_signal_to_row(_raw(ticker=None)) is None

    def test_strength_and_confidence_clamped(self):
        row = raw_signal_to_row(_raw(strength=5.0, confidence=3.0))
        assert float(row.strength) == 1.0
        assert float(row.confidence) == 1.0
        row = raw_signal_to_row(_raw(strength=-5.0, confidence=-1.0))
        assert float(row.strength) == -1.0
        assert float(row.confidence) == 0.0

    def test_default_fingerprint_derived(self):
        row = raw_signal_to_row(_raw())
        assert row.signal_metadata["fingerprint"] == "test_source:AAPL:news_catalyst:2026-06-10"

    def test_explicit_fingerprint_wins(self):
        row = raw_signal_to_row(_raw(metadata={"fingerprint": "custom:1"}))
        assert row.signal_metadata["fingerprint"] == "custom:1"


class TestCapitolTradesParsing:
    def test_size_range_parsing(self):
        from app.signals.capitol_trades import parse_size_range

        assert parse_size_range("1K-15K") == (1_000, 15_000)
        assert parse_size_range("$500K - $1M".replace("$", "")) == (500_000, 1_000_000)
        assert parse_size_range("") == (None, None)

    def test_date_parsing(self):
        from app.signals.capitol_trades import parse_date

        assert parse_date("30 Mar 2026") == datetime(2026, 3, 30)
        assert parse_date("2026-03-30") == datetime(2026, 3, 30)
        assert parse_date("yesterday") is not None
        assert parse_date("3 days ago") is not None
        assert parse_date("") is None

    def test_strength_scales_with_size(self):
        from app.signals.capitol_trades import _trade_to_strength

        small_buy = _trade_to_strength({"trade_type": "buy", "size_min_usd": 1_000})
        big_buy = _trade_to_strength({"trade_type": "buy", "size_min_usd": 1_000_000})
        sell = _trade_to_strength({"trade_type": "sell", "size_min_usd": 1_000_000})
        assert 0 < small_buy < big_buy <= 1.0
        assert sell == -big_buy


class TestSourceConfigLayers:
    def test_env_config_merges_under_database_state(self, monkeypatch):
        from app.core.config import settings
        from app.tasks import signal_dispatch as sd

        monkeypatch.setattr(settings, "SIGNAL_SOURCE_CONFIG", '{"fund_13f_tracker": {"fund": "Env Fund", "min_weight": 0.02}}')

        class State:
            config = {"min_weight": 0.05}

        merged = sd.effective_source_config("fund_13f_tracker", State())
        assert merged == {"fund": "Env Fund", "min_weight": 0.05}
        assert sd.effective_source_config("board_seat_tracker", None) == {}

    def test_invalid_env_config_is_ignored(self, monkeypatch):
        from app.core.config import settings
        from app.tasks import signal_dispatch as sd

        monkeypatch.setattr(settings, "SIGNAL_SOURCE_CONFIG", "{not json")
        assert sd.env_source_config() == {}
