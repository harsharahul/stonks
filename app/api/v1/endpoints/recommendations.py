"""
Recommendations API endpoints
Handles daily stock recommendations
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter()


@router.get("/daily")
async def get_daily_recommendations(
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD), defaults to today"),
    limit: int = Query(20, ge=1, le=100, description="Maximum recommendations to return"),
    db: Session = Depends(get_db)
):
    """
    Get top daily recommendations for a specific date
    """
    # TODO: Implement database query when models are ready
    return {
        "date": date or "2025-08-15",
        "recommendations": [
            {
                "symbol": "AAPL",
                "score": 0.85,
                "action": "buy",
                "rationale": {
                    "top_signals": [
                        {"signal": "momentum_14d", "contribution": 0.45},
                        {"signal": "sentiment_7d", "contribution": 0.35},
                        {"signal": "volume_ratio_3d", "contribution": 0.20}
                    ],
                    "evidence": {
                        "articles_7d": 15,
                        "price_trend_days_up": 8,
                        "volume_spike_ratio": 1.45
                    },
                    "notes": "Strong momentum with positive sentiment trend"
                },
                "model_version": "v1.0.0"
            },
            {
                "symbol": "MSFT",
                "score": 0.72,
                "action": "buy", 
                "rationale": {
                    "top_signals": [
                        {"signal": "momentum_14d", "contribution": 0.35},
                        {"signal": "sentiment_7d", "contribution": 0.45},
                        {"signal": "volume_ratio_3d", "contribution": 0.15}
                    ],
                    "evidence": {
                        "articles_7d": 12,
                        "price_trend_days_up": 6,
                        "volume_spike_ratio": 1.15
                    },
                    "notes": "Positive sentiment with moderate momentum"
                },
                "model_version": "v1.0.0"
            }
        ],
        "total": 2,
        "model_version": "v1.0.0"
    }
