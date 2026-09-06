"""Consolidated rankings: the "every brain, one list" view.

Public and cached: signal consensus (track-record-weighted) + AI Desk
verdicts + quant recommendations blended into one explainable stance per
ticker. See app/services/consolidation.py for the arithmetic.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.consolidation import consolidated_rankings_cached

router = APIRouter()


@router.get("/rankings")
async def get_consolidated_rankings(
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Ranked market stance per ticker, merged from every voice on the platform."""
    return consolidated_rankings_cached(db, limit=limit)
