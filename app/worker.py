"""
Stonks Celery Worker
Real-time analytics and monitoring worker with Beat scheduling
"""
from datetime import datetime, timezone as tz

from celery import Celery
from celery.signals import task_prerun, task_success, task_failure

from app.core.config import settings
from app.celery_beat_config import beat_schedule, timezone, task_routes

# Create Celery instance
worker = Celery('stonks')

# Configure Celery
worker.conf.update(
    broker_url=settings.CELERY_BROKER,
    result_backend=settings.CELERY_BACKEND,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=timezone,
    enable_utc=True,
    # Celery Beat schedule for real-time monitoring
    beat_schedule=beat_schedule,
    # Task routing
    task_routes=task_routes,
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)

# Import tasks directly to ensure they are registered
# This is more reliable than autodiscover_tasks for our use case
import app.tasks.anomaly_detection
import app.tasks.signal_generation
import app.tasks.feature_calculation
import app.tasks.data_ingestion
import app.tasks.earnings_calendar
import app.tasks.post_ingest_hooks
import app.tasks.price_ingestion
import app.tasks.recommendation_generation
import app.tasks.reddit_wsb_ingestion
import app.tasks.sec_edgar_ingestion
import app.tasks.sec_edgar_enhanced
import app.tasks.reddit_wsb_enhanced
import app.tasks.stock_knowledge
import app.tasks.agent_pipeline
import app.tasks.signal_dispatch
import app.tasks.signal_outcomes
import app.tasks.strategy_performance
import app.tasks.strategy_mirror

# Verify task registration
print("🔧 Celery worker initialized with tasks:")
for task_name in worker.tasks.keys():
    if task_name.startswith('app.'):
        print(f"  ✅ {task_name}")

@worker.task
def test_task():
    """Test task for verification"""
    return "Celery worker is working!"


@worker.task
def run_daily_analytics():
    """Daily analytics task placeholder"""
    return "Analytics task executed!"


# ---------------------------------------------------------------------------
# Celery signal handlers — auto-update admin-created ETLJobRun records
# When admin clicks "Run Now", an ETLJobRun is created with status="queued"
# and the celery_task_id stored in details JSON. These handlers close the loop
# by updating that record as the task progresses.
# ---------------------------------------------------------------------------

def _find_admin_job(db, task_id, allowed_statuses):
    """Find ETLJobRun created by admin for this Celery task_id."""
    from app.models.etl_job_run import ETLJobRun
    return db.query(ETLJobRun).filter(
        ETLJobRun.details.op('->>')(
            'celery_task_id') == task_id,
        ETLJobRun.status.in_(allowed_statuses),
    ).first()


@task_prerun.connect
def update_etl_job_on_start(task_id, task, **kwargs):
    """Update admin-created ETLJobRun when task starts."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        job = _find_admin_job(db, task_id, ['queued'])
        if job:
            job.status = 'running'
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@task_success.connect
def update_etl_job_on_success(sender, result, **kwargs):
    """Update admin-created ETLJobRun when task succeeds."""
    from app.core.database import SessionLocal
    from app.models.etl_job_run import ETLJobRun
    task_id = sender.request.id
    db = SessionLocal()
    try:
        job = _find_admin_job(db, task_id, ['queued', 'running'])
        if job:
            job.status = 'success'
            job.finished_at = datetime.now(tz.utc)
            if isinstance(result, dict):
                job.items_processed = (
                    result.get('items_processed')
                    or result.get('total_processed')
                    or result.get('processed')
                    or result.get('processed_count')
                    or None
                )
                # For price ingestion, sum new + updated
                if job.items_processed is None:
                    new = result.get('total_prices_new', 0)
                    updated = result.get('total_prices_updated', 0)
                    if new or updated:
                        job.items_processed = new + updated
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@task_failure.connect
def update_etl_job_on_failure(task_id, exception, **kwargs):
    """Update admin-created ETLJobRun when task fails."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        job = _find_admin_job(db, task_id, ['queued', 'running'])
        if job:
            job.status = 'failed'
            job.finished_at = datetime.now(tz.utc)
            job.details = {**(job.details or {}), 'error': str(exception)}
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
