"""
Admin API endpoints
Handles administrative operations: task dispatch, ETL job history, task catalog
"""
from typing import Optional
from datetime import datetime, timezone as tz

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from app.core.database import get_db
from app.worker import worker
from app.models.etl_job_run import ETLJobRun
from app.api.dependencies import require_admin

router = APIRouter()

# Map of user-facing job names to Celery task paths and queues
TASK_CATALOG = {
    "news_ingestion": {
        "task": "app.tasks.data_ingestion.ingest_rss_feeds_task",
        "queue": "ingestion",
        "description": "Fetch and process RSS news feeds",
        "schedule": "Every 10 min",
    },
    "wsb_ingestion": {
        "task": "app.tasks.reddit_wsb_enhanced.fetch_wsb_enhanced",
        "queue": "ingestion",
        "description": "Scrape WSB subreddit posts",
        "schedule": "Every 30 min",
    },
    "price_ingestion": {
        "task": "app.tasks.price_ingestion.fetch_prices_for_all_stocks",
        "queue": "ingestion",
        "description": "Fetch price data for all tracked stocks",
        "schedule": "Every hour",
    },
    "feature_calculation": {
        "task": "app.tasks.feature_calculation.calculate_daily_features",
        "queue": "compute",
        "description": "Calculate daily feature vectors",
        "schedule": "Daily 05:00 UTC",
    },
    "signal_generation": {
        "task": "app.tasks.signal_generation.daily_signal_generation_task",
        "queue": "analytics",
        "description": "Generate trading signals from features",
        "schedule": "Daily 06:00 UTC",
    },
    "recommendation_generation": {
        "task": "app.tasks.recommendation_generation.generate_daily_recommendations_task",
        "queue": "analytics",
        "description": "Generate buy/sell recommendations",
        "schedule": "Daily 06:30 UTC",
    },
    "anomaly_detection": {
        "task": "app.tasks.anomaly_detection.continuous_anomaly_monitoring_task",
        "queue": "analytics",
        "description": "Detect market anomalies",
        "schedule": "Every 15 min",
    },
    "alert_generation": {
        "task": "app.tasks.signal_generation.generate_alerts_task",
        "queue": "analytics",
        "description": "Generate alerts from recent signals",
        "schedule": "Every 5 min",
    },
    "earnings_calendar": {
        "task": "app.tasks.earnings_calendar.fetch_nasdaq_earnings_calendar",
        "queue": "ingestion",
        "description": "Fetch upcoming earnings dates",
        "schedule": "Daily 07:00 UTC",
    },
    "post_ingest_processing": {
        "task": "app.tasks.post_ingest_hooks.process_new_articles",
        "queue": "compute",
        "description": "Post-processing for newly ingested articles",
        "schedule": "Every 15 min",
    },
    "stock_knowledge": {
        "task": "app.tasks.stock_knowledge.update_stock_knowledge_task",
        "queue": "compute",
        "description": "Update evolving per-ticker intelligence",
        "schedule": "Daily 02:30 UTC",
    },
    "cleanup_articles": {
        "task": "app.tasks.post_ingest_hooks.cleanup_old_articles",
        "queue": "compute",
        "description": "Archive/delete old articles (tiered)",
        "schedule": "Daily 03:00 UTC",
    },
    "cleanup_etl_runs": {
        "task": "app.tasks.post_ingest_hooks.cleanup_old_etl_runs",
        "queue": "compute",
        "description": "Delete old ETL job run records",
        "schedule": "Daily 03:15 UTC",
    },
    "desk_universe_refresh": {
        "task": "app.tasks.agent_pipeline.refresh_universe_membership_task",
        "queue": "analytics",
        "description": "Refresh the AI Trading Desk coverage universe",
        "schedule": "Weekly Sun 00:00 UTC",
    },
    "desk_nightly_batch": {
        "task": "app.tasks.agent_pipeline.run_desk_universe_nightly_task",
        "queue": "analytics",
        "description": "Run the AI desk for every ticker in the active universe (LLM-heavy)",
        "schedule": "Daily 07:15 UTC",
    },
    "desk_score_outcomes": {
        "task": "app.tasks.agent_pipeline.score_past_decisions_task",
        "queue": "analytics",
        "description": "Score past desk decisions against realized prices",
        "schedule": "Daily 23:00 UTC",
    },
    "desk_run_ticker": {
        "task": "app.tasks.agent_pipeline.run_desk_for_ticker_task",
        "queue": "analytics",
        "description": "Run the AI desk for one ticker (params: {\"ticker\": \"AAPL\"}, optional trigger/trade_date)",
        "schedule": "On demand",
    },
    "signal_dispatch": {
        "task": "app.tasks.signal_dispatch.dispatch_signal_sources_task",
        "queue": "ingestion",
        "description": "Run all enabled signal source plugins (registry-driven)",
        "schedule": "Every 30 min",
    },
    "strategy_performance": {
        "task": "app.tasks.strategy_performance.compute_strategy_performance_task",
        "queue": "analytics",
        "description": "Compute verified strategy track records from broker fills",
        "schedule": "Daily 23:30 UTC",
    },
    "signal_outcome_scoring": {
        "task": "app.tasks.signal_outcomes.score_signal_outcomes_task",
        "queue": "analytics",
        "description": "Score past signals against realized 5d returns (per-source track records)",
        "schedule": "Daily 23:45 UTC",
    },
    "sec_edgar_ingestion": {
        "task": "app.tasks.sec_edgar_ingestion.fetch_sec_edgar_rss",
        "queue": "ingestion",
        "description": "Fetch SEC EDGAR RSS filings (8-K/10-K/10-Q)",
        "schedule": "Every 2 hr",
    },
}


class ReindexRequest(BaseModel):
    """Request model for task dispatch"""
    job_name: str
    params: Optional[dict] = None


@router.get("/task-catalog")
async def get_task_catalog(admin=Depends(require_admin)):
    """Return the catalog of available tasks."""
    return {
        "tasks": {
            name: {
                "task": info["task"],
                "queue": info["queue"],
                "description": info["description"],
                "schedule": info["schedule"],
            }
            for name, info in TASK_CATALOG.items()
        }
    }


@router.post("/reindex")
async def trigger_reindex(
    request: ReindexRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """Dispatch a Celery task by job name."""
    if request.job_name not in TASK_CATALOG:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid job name '{request.job_name}'. Valid jobs: {', '.join(sorted(TASK_CATALOG.keys()))}",
        )

    catalog_entry = TASK_CATALOG[request.job_name]
    task_path = catalog_entry["task"]
    queue = catalog_entry["queue"]

    # Create ETLJobRun record
    job = ETLJobRun(
        job_name=request.job_name,
        started_at=datetime.now(tz.utc),
        status="queued",
        details={"params": request.params, "celery_task": task_path},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch to Celery
    try:
        result = worker.send_task(task_path, queue=queue, kwargs=request.params or {})
        # Update with Celery task ID
        job.details = {**(job.details or {}), "celery_task_id": result.id}
        db.commit()
    except Exception as e:
        job.status = "failed"
        job.finished_at = datetime.now(tz.utc)
        job.details = {**(job.details or {}), "error": str(e)}
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to dispatch task: {e}")

    return {
        "enqueued": True,
        "job_id": str(job.id),
        "job_name": request.job_name,
        "celery_task_id": result.id,
        "queue": queue,
        "message": f"Task '{request.job_name}' dispatched to '{queue}' queue",
    }


@router.get("/jobs")
async def list_recent_jobs(
    limit: int = Query(default=50, le=200),
    job_name: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """List recent ETL job runs with optional filters."""
    query = db.query(ETLJobRun).order_by(desc(ETLJobRun.started_at))

    if job_name:
        query = query.filter(ETLJobRun.job_name == job_name)
    if status:
        query = query.filter(ETLJobRun.status == status)

    jobs = query.limit(limit).all()

    return {
        "jobs": [
            {
                "id": str(j.id),
                "job_name": j.job_name,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
                "status": j.status,
                "items_processed": j.items_processed,
                "details": j.details,
            }
            for j in jobs
        ],
        "total": len(jobs),
    }


# ── Signal plugin SDK ─────────────────────────────────────────────────────────


@router.get("/signal-sources")
async def list_signal_sources(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """List every registered signal plugin with metadata + per-deployment state."""
    from app.core.signal_framework import register_default_sources, signal_registry
    from app.models.signal_source_state import SignalSourceState
    from app.tasks.signal_outcomes import source_track_records

    register_default_sources()
    track_records = source_track_records(db)
    sources = []
    for source_id in signal_registry.list_available_sources():
        source_cls = signal_registry._sources[source_id]
        meta = source_cls({}).get_metadata()
        state = db.query(SignalSourceState).filter_by(source_id=source_id).first()
        sources.append({
            "source_id": source_id,
            "name": meta.name,
            "description": meta.description,
            "source_type": meta.source_type.value,
            "signal_types": [t.value for t in meta.supported_signal_types],
            "update_frequency_seconds": int(meta.update_frequency.total_seconds()),
            "required_config": meta.required_config,
            "enabled": state.enabled if state else getattr(source_cls, "default_enabled", True),
            "state": state.to_dict() if state else None,
            "track_record": track_records.get(source_id),
        })
    # Non-plugin emitters (rule engine, anomaly detector) so the full picture shows
    builtin = {
        sid: rec for sid, rec in track_records.items()
        if sid not in {s["source_id"] for s in sources}
    }
    return {"sources": sources, "builtin_track_records": builtin, "total": len(sources)}


@router.post("/signal-sources/{source_id}/toggle")
async def toggle_signal_source(
    source_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """Flip a signal plugin's enabled state for this deployment."""
    from app.core.signal_framework import register_default_sources, signal_registry
    from app.models.signal_source_state import SignalSourceState

    register_default_sources()
    if source_id not in signal_registry.list_available_sources():
        raise HTTPException(status_code=404, detail=f"Unknown signal source '{source_id}'")

    state = db.query(SignalSourceState).filter_by(source_id=source_id).first()
    if state is None:
        source_cls = signal_registry._sources[source_id]
        state = SignalSourceState(
            source_id=source_id,
            enabled=not getattr(source_cls, "default_enabled", True),
        )
        db.add(state)
    else:
        state.enabled = not state.enabled
    db.commit()
    return {"source_id": source_id, "enabled": state.enabled}
