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
    broker_url=f'redis://{settings.redis_host}:{settings.redis_port}/0',
    result_backend=f'redis://{settings.redis_host}:{settings.redis_port}/0',
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

# Auto-discover tasks from all app.tasks modules
worker.autodiscover_tasks([
    'app.tasks.anomaly_detection',
    'app.tasks.signal_generation', 
    'app.tasks.feature_calculation',
    'app.tasks.data_ingestion',
    'app.tasks.price_ingestion',
    'app.tasks.reddit_wsb_ingestion'
])


@worker.task
def test_task():
    """Test task for verification"""
    return "Celery worker is working!"


@worker.task
def run_daily_analytics():
    """Daily analytics task placeholder"""
    return "Analytics task executed!"
