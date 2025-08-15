"""
Stocks API endpoints
Handles stock information and details
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter()


@router.get("/")
async def list_stocks(
    q: Optional[str] = Query(None, description="Search by symbol or company name"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    exchange: Optional[str] = Query(None, description="Filter by exchange"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    List stocks with optional filtering and pagination
    """
    # TODO: Implement database query when models are ready
    return {
        "items": [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "exchange": "NASDAQ",
                "is_active": True
            },
            {
                "id": "550e8400-e29b-41d4-a716-446655440001", 
                "symbol": "MSFT",
                "company_name": "Microsoft Corporation",
                "sector": "Technology",
                "exchange": "NASDAQ",
                "is_active": True
            }
        ],
        "total": 2,
        "page": page,
        "page_size": page_size,
        "pages": 1
    }


@router.get("/{symbol}")
async def get_stock(
    symbol: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed stock information by symbol
    """
    # TODO: Implement database query when models are ready
    if symbol.upper() not in ["AAPL", "MSFT", "GOOGL", "TSLA"]:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "symbol": symbol.upper(),
        "company_name": "Apple Inc." if symbol.upper() == "AAPL" else f"{symbol.upper()} Corporation",
        "sector": "Technology",
        "exchange": "NASDAQ",
        "latest_price": {
            "ts": "2025-08-15T10:30:00Z",
            "open": 185.50,
            "high": 187.20,
            "low": 184.80,
            "close": 186.75,
            "volume": 52483729
        },
        "aggregates": {
            "sentiment_7d": 0.65,
            "momentum_14d": 0.15,
            "vol_ratio_3d": 1.25
        }
    }
