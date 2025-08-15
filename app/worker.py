"""
Stonks Celery Worker
Minimal placeholder for Docker build testing
"""
from celery import Celery

# Create Celery instance
worker = Celery('stonks')

# Configure Celery
worker.conf.update(
    broker_url='redis://redis:6379/0',
    result_backend='redis://redis:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)


@worker.task
def test_task():
    """Test task for verification"""
    return "Celery worker is working!"


@worker.task
def run_daily_analytics():
    """Daily analytics task placeholder"""
    return "Analytics task executed!"
