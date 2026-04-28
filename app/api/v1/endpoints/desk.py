"""AI Trading Desk API endpoints (Phase 1).

Read-only surface for the flagship `/desk` page:
  GET  /desk/universe          List of covered tickers + decision badges
  GET  /desk/{ticker}           Latest decision + briefs + transcript + outcome
  GET  /desk/{ticker}/history   Past decisions for ticker with outcomes

Phase 2 will extend with `POST /desk/{ticker}/refresh` (on-demand) and
`GET /desk/runs/{run_id}` (in-flight polling). Phase 4 adds
`/desk/track-record`, `/desk/morning-brief`, `/desk/crowd-vs-ai`, and
`POST /desk/{ticker}/ask`.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.agents.service import (
    get_decision_history,
    get_full_desk_view,
    get_universe_view,
)
from app.core.database import get_db

router = APIRouter()


# Symbol validation matches the rest of the API: 1 to 10 characters from
# [A-Za-z0-9.-].
_TICKER_PATH = Path(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9.\-]+$")


@router.get("/universe", summary="List covered tickers with latest decisions")
async def get_universe(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Active desk universe + each ticker's latest decision summary."""
    rows = get_universe_view(db)
    return {
        "count": len(rows),
        "tickers": rows,
    }


@router.get("/{ticker}", summary="Latest decision + briefs + outcome for a ticker")
async def get_desk_for_ticker(
    ticker: str = _TICKER_PATH,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    payload = get_full_desk_view(db, ticker)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"No desk decision found for {ticker.upper()} yet. "
            "The pipeline has not run for this ticker.",
        )
    return payload


@router.get("/{ticker}/history", summary="Past decisions for ticker with realized outcomes")
async def get_history(
    ticker: str = _TICKER_PATH,
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rows = get_decision_history(db, ticker, limit=limit)
    return {
        "ticker": ticker.upper(),
        "count": len(rows),
        "decisions": rows,
    }
