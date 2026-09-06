"""Registry-driven dispatcher for signal source plugins.

Every 30 minutes (and on admin Run Now) this task walks the plugin registry,
runs each enabled source, and persists trading-grade RawSignals into the
existing ``signals`` table with full provenance:

- ``signal_type``   ← plugin's ``signal_type_hint``
- ``model_version`` ← ``plugin:<source_id>``
- ``signal_metadata.source_plugin`` / ``.fingerprint`` for dedupe

RawSignals without direction+strength hints are informational and skipped.
Per-source admin state (enabled toggle, config overrides, last-run health)
lives in ``signal_source_states``.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from celery import shared_task
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.config import settings
from app.core.signal_framework import (
    RawSignal,
    register_default_sources,
    signal_registry,
)
from app.models.signal import Signal
from app.models.signal_source_state import SignalSourceState
from app.tasks.etl_helpers import get_or_create_etl_job

logger = logging.getLogger(__name__)

DEDUPE_WINDOW_HOURS = 48
SIGNAL_TTL_HOURS = 24  # emitted signals expire after a day unless re-emitted


def raw_signal_to_row(raw: RawSignal) -> Optional[Signal]:
    """Map a plugin RawSignal onto the Signal ORM model (None = not tradable)."""
    if not raw.ticker or raw.direction is None or raw.strength is None:
        return None
    fingerprint = raw.metadata.get("fingerprint") or (
        f"{raw.source_id}:{raw.ticker}:{raw.signal_type_hint}:{raw.timestamp.date().isoformat()}"
    )
    return Signal(
        ticker=raw.ticker.upper(),
        signal_type=raw.signal_type_hint or "plugin_signal",
        strength=max(-1.0, min(1.0, float(raw.strength))),
        confidence=max(0.0, min(1.0, float(raw.confidence if raw.confidence is not None else 0.5))),
        direction=raw.direction,
        timeframe=raw.timeframe,
        expires_at=datetime.utcnow() + timedelta(hours=SIGNAL_TTL_HOURS),
        signal_metadata={
            "source_plugin": raw.source_id,
            "fingerprint": fingerprint,
            "priority": raw.priority,
            **raw.raw_data,
        },
        model_version=f"plugin:{raw.source_id}",
    )


def _get_or_create_state(db, source_id: str, source_cls) -> SignalSourceState:
    state = db.execute(
        select(SignalSourceState).where(SignalSourceState.source_id == source_id)
    ).scalar_one_or_none()
    if state is None:
        state = SignalSourceState(
            source_id=source_id,
            enabled=getattr(source_cls, "default_enabled", True),
        )
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def env_source_config() -> Dict[str, Dict]:
    """Per-source config from ``SIGNAL_SOURCE_CONFIG`` (JSON object keyed by source id)."""
    raw = settings.SIGNAL_SOURCE_CONFIG
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError as exc:
        logger.error("SIGNAL_SOURCE_CONFIG is not valid JSON: %s", exc)
        return {}
    return data if isinstance(data, dict) else {}


def effective_source_config(source_id: str, state: Optional["SignalSourceState"]) -> Dict:
    """Environment config as the base, database state layered on top."""
    base = env_source_config().get(source_id) or {}
    override = (state.config if state is not None else None) or {}
    return {**base, **override}


def _existing_fingerprints(db, source_id: str) -> set:
    """Fingerprints this plugin emitted inside the dedupe window."""
    cutoff = datetime.utcnow() - timedelta(hours=DEDUPE_WINDOW_HOURS)
    rows = db.execute(
        select(Signal.signal_metadata).where(
            Signal.model_version == f"plugin:{source_id}",
            Signal.generated_at >= cutoff,
        )
    ).scalars().all()
    return {m.get("fingerprint") for m in rows if isinstance(m, dict) and m.get("fingerprint")}


def _run_source(db, source_id: str, state: SignalSourceState) -> Dict:
    """Run one plugin end-to-end; returns a per-source result summary."""
    source_cls = signal_registry._sources[source_id]
    source = source_cls({**effective_source_config(source_id, state), "enabled": True})

    config_errors = asyncio.run(source.validate_config())
    if config_errors:
        state.last_status = "skipped_config"
        state.last_error = "; ".join(config_errors)
        db.commit()
        return {"source": source_id, "status": "skipped_config", "errors": config_errors}

    raws: List[RawSignal] = asyncio.run(source.fetch_signals(since=state.last_run_at))

    seen = _existing_fingerprints(db, source_id)
    persisted = 0
    skipped_dupe = 0
    skipped_informational = 0
    for raw in raws:
        row = raw_signal_to_row(raw)
        if row is None:
            skipped_informational += 1
            continue
        if row.signal_metadata["fingerprint"] in seen:
            skipped_dupe += 1
            continue
        seen.add(row.signal_metadata["fingerprint"])
        db.add(row)
        persisted += 1

    state.last_run_at = datetime.utcnow()
    state.last_status = "success"
    state.last_error = None
    state.signals_emitted_total = (state.signals_emitted_total or 0) + persisted
    db.commit()
    return {
        "source": source_id,
        "status": "success",
        "fetched": len(raws),
        "persisted": persisted,
        "skipped_dupe": skipped_dupe,
        "skipped_informational": skipped_informational,
    }


@shared_task(bind=True, queue="ingestion", acks_late=True, reject_on_worker_lost=True)
def dispatch_signal_sources_task(self, source_id: Optional[str] = None) -> Dict:
    """Run all enabled signal plugins (or one, when ``source_id`` is given)."""
    register_default_sources()
    results: List[Dict] = []

    with SessionLocal() as db:
        job_run = get_or_create_etl_job(
            db, self.request.id, "signal_dispatch", {"task_id": self.request.id, "source_id": source_id}
        )
        targets = [source_id] if source_id else signal_registry.list_available_sources()
        total_persisted = 0
        try:
            for sid in targets:
                if sid not in signal_registry._sources:
                    results.append({"source": sid, "status": "unknown_source"})
                    continue
                state = _get_or_create_state(db, sid, signal_registry._sources[sid])
                if not state.enabled:
                    state.last_status = "disabled"
                    db.commit()
                    results.append({"source": sid, "status": "disabled"})
                    continue
                try:
                    result = _run_source(db, sid, state)
                except Exception as e:  # one bad plugin must not sink the batch
                    db.rollback()
                    state.last_status = "error"
                    state.last_error = str(e)[:2000]
                    db.commit()
                    logger.exception("signal_dispatch: source %s failed", sid)
                    result = {"source": sid, "status": "error", "error": str(e)}
                results.append(result)
                total_persisted += result.get("persisted", 0)

            job_run.status = "success"
            job_run.finished_at = datetime.utcnow()
            job_run.items_processed = total_persisted
            job_run.details = {**(job_run.details or {}), "results": results}
            db.commit()
        except Exception as e:
            db.rollback()
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details = {**(job_run.details or {}), "error": str(e), "results": results}
            db.commit()
            raise

    logger.info("signal_dispatch: %s", results)
    return {"task": "dispatch_signal_sources", "persisted": total_persisted, "results": results}
