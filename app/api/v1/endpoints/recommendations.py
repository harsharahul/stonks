"""
Recommendations API endpoints
Serves daily stock recommendations generated from signals + feature store
"""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.recommendation import Recommendation
from app.models.stock import Stock

router = APIRouter()


@router.get("/daily")
async def get_daily_recommendations(
    date_str: Optional[str] = Query(None, alias="date", description="Date (YYYY-MM-DD), defaults to most recent"),
    limit: int = Query(20, ge=1, le=100, description="Maximum recommendations to return"),
    db: Session = Depends(get_db)
):
    """
    Get top daily recommendations for a specific date.
    Falls back to the most recent date with data if no date specified or no data for requested date.
    """
    target_date = None
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = None

    # If no date specified or invalid, find the most recent date with recommendations
    if target_date is None:
        latest = db.query(func.max(Recommendation.date)).scalar()
        if latest is None:
            return {
                "date": date.today().isoformat(),
                "recommendations": [],
                "total": 0,
                "model_version": "v1.0.0"
            }
        target_date = latest
    else:
        # Check if data exists for requested date; fall back to most recent
        count = db.query(Recommendation).filter(Recommendation.date == target_date).count()
        if count == 0:
            latest = db.query(func.max(Recommendation.date)).scalar()
            if latest is None:
                return {
                    "date": target_date.isoformat(),
                    "recommendations": [],
                    "total": 0,
                    "model_version": "v1.0.0"
                }
            target_date = latest

    # Query recommendations joined with stocks for symbol
    rows = (
        db.query(Recommendation, Stock.symbol)
        .join(Stock, Recommendation.stock_id == Stock.id)
        .filter(Recommendation.date == target_date)
        .order_by(Recommendation.score.desc())
        .limit(limit)
        .all()
    )

    recommendations = []
    for rec, symbol in rows:
        recommendations.append({
            "symbol": symbol,
            "score": float(rec.score),
            "action": rec.action.lower(),
            "rationale": rec.rationale or {},
            "model_version": rec.model_version,
        })

    return {
        "date": target_date.isoformat(),
        "recommendations": recommendations,
        "total": len(recommendations),
        "model_version": "v1.0.0"
    }
