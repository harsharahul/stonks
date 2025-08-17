"""
Metrics endpoint for Prometheus scraping
"""
from fastapi import APIRouter, Response
from app.core.metrics import get_metrics

router = APIRouter()


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=get_metrics(),
        media_type="text/plain"
    )
