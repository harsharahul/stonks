"""Unit tests for the consolidation scoring math — pure logic, no DB."""
from app.services.consolidation import (
    blend,
    desk_component,
    recommendation_component,
    signal_contribution,
    source_weight,
    stance_label,
)


class TestSourceWeight:
    def test_unproven_source_is_neutral(self):
        assert source_weight(None) == 1.0
        assert source_weight({"scored": 3, "win_rate": 1.0}) == 1.0  # too few to trust

    def test_proven_winner_weighs_more(self):
        assert source_weight({"scored": 50, "win_rate": 0.7}) > 1.0

    def test_proven_loser_weighs_less(self):
        assert source_weight({"scored": 50, "win_rate": 0.2}) < 1.0

    def test_bounds(self):
        assert source_weight({"scored": 100, "win_rate": 1.0}) == 1.5
        assert source_weight({"scored": 100, "win_rate": 0.0}) == 0.5


class TestComponents:
    def test_signal_contribution_signed_strength(self):
        assert signal_contribution(0.8, 0.5, "bullish", 1.0) == 0.4
        assert signal_contribution(-0.8, 0.5, "bearish", 1.0) == -0.4

    def test_zero_strength_falls_back_to_direction(self):
        assert signal_contribution(0.0, 0.6, "bearish", 1.0) < 0
        assert signal_contribution(0.0, 0.6, "bullish", 1.0) > 0

    def test_desk_mapping(self):
        assert desk_component("Buy", 0.5) == 0.5
        assert desk_component("Overweight", 0.5) == 0.25
        assert desk_component("Hold", 0.9) == 0.0
        assert desk_component("Sell", 0.5) == -0.5
        assert desk_component("unknown verdict", 0.5) == 0.0

    def test_recommendation_mapping(self):
        assert recommendation_component(0.5) == 0.0
        assert recommendation_component(1.0) == 1.0
        assert recommendation_component(0.0) == -1.0


class TestBlend:
    def test_all_components(self):
        score = blend({"signals": 1.0, "desk": 1.0, "recommendation": 1.0})
        assert score == 1.0

    def test_renormalizes_over_present(self):
        # Only the desk voted: the composite IS the desk score.
        assert blend({"signals": None, "desk": 0.5, "recommendation": None}) == 0.5

    def test_empty_is_none(self):
        assert blend({"signals": None, "desk": None, "recommendation": None}) is None

    def test_mixed_voices_partial_weights(self):
        # signals (.40) bullish, recommendation (.25) bearish, no desk
        score = blend({"signals": 0.8, "desk": None, "recommendation": -0.4})
        expected = (0.8 * 0.40 + -0.4 * 0.25) / 0.65
        assert abs(score - round(expected, 4)) < 1e-9


class TestStance:
    def test_labels(self):
        assert stance_label(0.6) == "strongly bullish"
        assert stance_label(0.3) == "bullish"
        assert stance_label(0.0) == "neutral"
        assert stance_label(-0.3) == "bearish"
        assert stance_label(-0.6) == "strongly bearish"
        assert stance_label(None) == "no data"
