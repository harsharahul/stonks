"""Retention wiring: signals must outlive the scoring window and outcomes must
survive signal deletion. These guard the coupling bug where 7-day signal
cleanup deleted signals the 90-day scorer still needed and cascade-deleted the
track record with them.
"""
import inspect

from app.celery_beat_config import beat_schedule
from app.models.signal_outcome import SignalOutcome
from app.tasks.signal_outcomes import MAX_SIGNAL_AGE_DAYS
from app.tasks.signal_generation import cleanup_expired_signals_task
from app.tasks.price_ingestion import cleanup_old_prices


def _default(fn, arg):
    return inspect.signature(fn.run).parameters[arg].default


def test_signal_retention_outlives_the_scoring_window():
    entry = beat_schedule["cleanup-expired-signals"]
    (retention_days,) = entry["args"]
    assert retention_days > MAX_SIGNAL_AGE_DAYS
    assert _default(cleanup_expired_signals_task, "days_old") > MAX_SIGNAL_AGE_DAYS


def test_outcome_survives_signal_deletion():
    fk = next(iter(SignalOutcome.__table__.c.signal_id.foreign_keys))
    assert fk.ondelete == "SET NULL"
    assert SignalOutcome.__table__.c.signal_id.nullable is True


def test_price_retention_is_scheduled_and_bounded():
    entry = beat_schedule["cleanup-old-prices"]
    assert entry["task"] == "app.tasks.price_ingestion.cleanup_old_prices"
    keep = _default(cleanup_old_prices, "days_to_keep")
    assert keep >= 365  # a full year of charts and scoring lookback stays
