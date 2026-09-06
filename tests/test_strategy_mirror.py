"""Unit tests for the paper-auto copy engine's pure logic: no DB, no broker."""
from app.tasks.strategy_mirror import (
    DEFAULT_COPY_POSITION_PCT,
    MAX_COPY_POSITION_PCT,
    copy_notional_for,
    mirror_client_order_id,
)


class TestMirrorIdempotencyKey:
    def test_deterministic(self):
        a = mirror_client_order_id("11111111-2222-3333-4444-555555555555", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        b = mirror_client_order_id("11111111-2222-3333-4444-555555555555", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        assert a == b
        assert a.startswith("stonks-copy-11111111-")

    def test_distinct_per_follower_and_origin(self):
        base = mirror_client_order_id("11111111-0-0-0-0", "aaaaaaaa-0-0-0-0")
        other_follower = mirror_client_order_id("99999999-0-0-0-0", "aaaaaaaa-0-0-0-0")
        other_origin = mirror_client_order_id("11111111-0-0-0-0", "ffffffff-0-0-0-0")
        assert base != other_follower
        assert base != other_origin

    def test_alpaca_length_limit(self):
        # Alpaca client_order_id max is 128 chars; ours stays far below.
        assert len(mirror_client_order_id("1" * 36, "2" * 36)) < 64


class TestCopySizing:
    def test_default_two_percent(self):
        assert copy_notional_for(100_000, None) == 100_000 * DEFAULT_COPY_POSITION_PCT

    def test_follower_override(self):
        assert copy_notional_for(100_000, {"copy_position_pct": 0.05}) == 5_000.0

    def test_hard_cap(self):
        assert copy_notional_for(100_000, {"copy_position_pct": 0.5}) == 100_000 * MAX_COPY_POSITION_PCT

    def test_garbage_config_falls_back(self):
        assert copy_notional_for(100_000, {"copy_position_pct": "lots"}) == 100_000 * DEFAULT_COPY_POSITION_PCT

    def test_negative_inputs_clamped(self):
        assert copy_notional_for(-5_000, None) == 0.0
        assert copy_notional_for(100_000, {"copy_position_pct": -1}) == 0.0
