"""
Stonks Celery Beat Application
Dedicated configuration for the Celery Beat scheduler
"""
from celery import Celery
from app.core.config import settings
from app.celery_beat_config import beat_schedule, timezone, task_routes

# Create Celery Beat instance
beat_app = Celery('stonks-beat')

# Configure Celery Beat with the same settings as worker
beat_app.conf.update(
    broker_url=settings.CELERY_BROKER,
    result_backend=settings.CELERY_BACKEND,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=timezone,
    enable_utc=True,
    # Celery Beat schedule for real-time monitoring
    beat_schedule=beat_schedule,
    # Task routing - CRITICAL for proper queue assignment
    task_routes=task_routes,
    # Beat-specific settings
    beat_max_loop_interval=60,  # Maximum time between beat iterations
    beat_sync_every=1,  # Sync with broker every N tasks
    # Force Beat to start immediately without waiting for workers
    worker_direct=False,  # Don't wait for workers
    beat_immediate=True,  # Start immediately
)

# Import all tasks to ensure they are registered
# This is critical for task routing to work
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

# Verify configuration is loaded
print("🔧 Celery Beat initialized with configuration:")
print(f"  📅 Beat schedule: {len(beat_schedule)} tasks configured")
print(f"  🚦 Task routes: {len(task_routes)} route patterns")
print(f"  ⏰ Timezone: {timezone}")
print(f"  🔗 Broker: {settings.CELERY_BROKER}")

# List all scheduled tasks
print("\n📋 Scheduled Tasks:")
for task_name, task_config in beat_schedule.items():
    print(f"  ✅ {task_name}: {task_config['task']} (every {task_config['schedule']}s)")

# List all task routes
print("\n🚦 Task Routes:")
for pattern, route_config in task_routes.items():
    print(f"  ✅ {pattern} → {route_config['queue']}")

# Don't start the app when imported - let Celery handle it
