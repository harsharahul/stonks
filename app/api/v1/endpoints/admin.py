"""
Admin API endpoints
Handles administrative operations and ETL triggers
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db

router = APIRouter()


class ReindexRequest(BaseModel):
    """Request model for reindex operation"""
    job_name: str
    params: Optional[dict] = None


@router.post("/reindex")
async def trigger_reindex(
    request: ReindexRequest,
    db: Session = Depends(get_db)
):
    """
    Trigger backfill or reindex job
    """
    # TODO: Implement Celery task dispatch when worker is ready
    valid_jobs = ["prices_backfill", "news_backfill", "analytics_refresh"]
    
    if request.job_name not in valid_jobs:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid job name. Valid jobs: {', '.join(valid_jobs)}"
        )
    
    # Simulate job dispatch
    job_id = f"job-{request.job_name}-{hash(str(request.params))}"
    
    return {
        "enqueued": True,
        "job_id": job_id,
        "job_name": request.job_name,
        "params": request.params,
        "message": f"Job {request.job_name} has been enqueued"
    }


@router.get("/jobs")
async def list_recent_jobs(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    List recent ETL job runs
    """
    # TODO: Implement database query when models are ready
    return {
        "jobs": [
            {
                "id": "job-1",
                "job_name": "daily_analytics",
                "started_at": "2025-08-15T00:30:00Z",
                "finished_at": "2025-08-15T00:35:00Z",
                "status": "success",
                "items_processed": 2847,
                "details": {
                    "stocks_analyzed": 500,
                    "recommendations_generated": 25,
                    "duration_seconds": 300
                }
            },
            {
                "id": "job-2",
                "job_name": "news_ingestion",
                "started_at": "2025-08-15T10:00:00Z",
                "finished_at": "2025-08-15T10:02:00Z", 
                "status": "success",
                "items_processed": 47,
                "details": {
                    "articles_fetched": 47,
                    "new_articles": 12,
                    "duplicates_skipped": 35
                }
            }
        ],
        "total": 2
    }
