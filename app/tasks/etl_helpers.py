"""
Shared helper for ETLJobRun management across Celery tasks.
Prevents duplicate records when admin "Run Now" triggers a task.
"""
from datetime import datetime


def get_or_create_etl_job(db, celery_task_id, job_name, details=None):
    """
    Reuse an admin-created ETLJobRun if one exists for this celery_task_id,
    otherwise create a new one (Beat-triggered or standalone).

    Admin endpoint creates ETLJobRun with status='queued' and stores
    celery_task_id in details JSON. The task_prerun signal handler in
    worker.py transitions it to 'running'. This helper finds that record
    so the task body updates *it* instead of creating a duplicate.
    """
    from app.models.etl_job_run import ETLJobRun

    if celery_task_id:
        existing = db.query(ETLJobRun).filter(
            ETLJobRun.details.op('->>')('celery_task_id') == celery_task_id,
            ETLJobRun.status.in_(['queued', 'running']),
        ).first()
        if existing:
            existing.status = 'running'
            existing.started_at = datetime.utcnow()
            if details:
                existing.details = {**(existing.details or {}), **details}
            db.commit()
            return existing

    # No admin record found: create a new one (Beat-triggered)
    job_run = ETLJobRun(
        job_name=job_name,
        started_at=datetime.utcnow(),
        status="running",
        details=details or {},
    )
    db.add(job_run)
    db.commit()
    return job_run
