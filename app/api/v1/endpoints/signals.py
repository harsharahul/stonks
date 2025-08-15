"""
Signals API endpoints
Handles computed stock signals
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter()


@router.get("/")
async def get_signals(
    symbol: Optional[str] = Query(None, description="Filter by stock symbol"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    since: Optional[str] = Query(None, description="ISO timestamp filter"),
    until: Optional[str] = Query(None, description="ISO timestamp filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Get computed signals with filtering and pagination
    """
    # TODO: Implement database query when models are ready
    return {
        "items": [
            {
                "id": "signal-1",
                "symbol": "AAPL",
                "signal_type": "momentum_14d",
                "value": 0.15,
                "details": {
                    "raw_return": 0.08,
                    "normalized_score": 0.15,
                    "z_score": 0.75
                },
                "computed_at": "2025-08-15T10:00:00Z"
            },
            {
                "id": "signal-2",
                "symbol": "AAPL", 
                "signal_type": "sentiment_7d",
                "value": 0.65,
                "details": {
                    "articles_count": 15,
                    "avg_sentiment": 0.65,
                    "weighted_sentiment": 0.68
                },
                "computed_at": "2025-08-15T10:00:00Z"
            }
        ],
        "total": 2,
        "page": page,
        "page_size": page_size
    }
