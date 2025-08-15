"""
Feed API endpoints
Handles mixed feed of articles and signals
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter()


@router.get("/")
async def get_feed(
    symbols: Optional[str] = Query(None, description="Comma-separated symbols filter"),
    since: Optional[str] = Query(None, description="ISO timestamp filter"),
    until: Optional[str] = Query(None, description="ISO timestamp filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Get mixed feed of articles and signals for homepage
    """
    # TODO: Implement database query when models are ready
    return {
        "items": [
            {
                "type": "article",
                "id": "article-1",
                "title": "Apple Reports Strong Q4 Earnings",
                "url": "https://example.com/apple-earnings",
                "published_at": "2025-08-15T09:00:00Z",
                "tickers": ["AAPL"],
                "sentiment": 0.8
            },
            {
                "type": "signal",
                "id": "signal-1", 
                "symbol": "AAPL",
                "signal_type": "momentum_14d",
                "value": 0.15,
                "computed_at": "2025-08-15T10:00:00Z"
            }
        ],
        "total": 2,
        "page": page,
        "page_size": page_size
    }
