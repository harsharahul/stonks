"""
Stonks Celery Worker
Real-time analytics and monitoring worker with Beat scheduling
"""
from celery import Celery
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
import app.tasks.reddit_wsb_ingestion
import app.tasks.sec_edgar_ingestion
import app.tasks.sec_edgar_enhanced
import app.tasks.reddit_wsb_enhanced

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
