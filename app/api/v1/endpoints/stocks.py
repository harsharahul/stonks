"""
Stocks API endpoints
Handles stock information and details
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from math import ceil

from app.core.database import get_db
from app.models.stock import Stock
from app.models.price import Price
from app.models.stock_knowledge import StockKnowledge

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
    # Build query with filters
    query = db.query(Stock).filter(Stock.is_active == True)
    
    # Apply search filter
    if q:
        search_filter = or_(
            Stock.symbol.ilike(f"%{q}%"),
            Stock.company_name.ilike(f"%{q}%")
        )
        query = query.filter(search_filter)
    
    # Apply sector filter
    if sector:
        query = query.filter(Stock.sector.ilike(f"%{sector}%"))
    
    # Apply exchange filter
    if exchange:
        query = query.filter(Stock.exchange.ilike(f"%{exchange}%"))
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    stocks = query.offset(offset).limit(page_size).all()
    
    # Calculate total pages
    pages = ceil(total / page_size) if total > 0 else 1
    
    return {
        "items": [
            {
                "id": stock.id,
                "symbol": stock.symbol,
                "company_name": stock.company_name,
                "sector": stock.sector,
                "exchange": stock.exchange,
                "is_active": stock.is_active
            }
            for stock in stocks
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages
    }


@router.get("/{symbol}")
async def get_stock(
    symbol: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed stock information by symbol
    """
    # Query stock from database
    stock = db.query(Stock).filter(
        Stock.symbol == symbol.upper(),
        Stock.is_active == True
    ).first()
    
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    # Fetch latest price from database
    latest_price_row = db.query(Price).filter(
        Price.stock_id == stock.id
    ).order_by(Price.ts.desc()).first()

    latest_price = None
    if latest_price_row:
        ts = latest_price_row.ts or latest_price_row.timestamp
        latest_price = {
            "ts": ts.isoformat() if ts else None,
            "open": float(latest_price_row.open_price) if latest_price_row.open_price else None,
            "high": float(latest_price_row.high) if latest_price_row.high else None,
            "low": float(latest_price_row.low) if latest_price_row.low else None,
            "close": float(latest_price_row.close) if latest_price_row.close else float(latest_price_row.price),
            "volume": latest_price_row.volume or 0,
        }

    return {
        "id": stock.id,
        "symbol": stock.symbol,
        "company_name": stock.company_name,
        "sector": stock.sector,
        "exchange": stock.exchange,
        "is_active": stock.is_active,
        "latest_price": latest_price,
    }


@router.get("/{symbol}/knowledge")
async def get_stock_knowledge(
    symbol: str,
    db: Session = Depends(get_db)
):
    """
    Return the evolving analytical knowledge record for a stock ticker.

    Populated nightly by the update_stock_knowledge_task Celery task.
    Returns 404 if the stock doesn't exist or knowledge hasn't been generated yet.
    """
    stock = db.query(Stock).filter(
        Stock.symbol == symbol.upper(),
        Stock.is_active == True
    ).first()

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    knowledge = db.query(StockKnowledge).filter(
        StockKnowledge.ticker == symbol.upper()
    ).first()

    if not knowledge:
        raise HTTPException(
            status_code=404,
            detail="No knowledge record yet: run update_stock_knowledge_task to generate one"
        )

    return {
        "ticker": knowledge.ticker,
        "narrative": knowledge.narrative,
        "key_events": knowledge.key_events,
        "sentiment_trend": knowledge.sentiment_trend,
        "article_count_processed": knowledge.article_count_processed,
        "last_updated": knowledge.last_updated.isoformat() if knowledge.last_updated else None,
        "created_at": knowledge.created_at.isoformat() if knowledge.created_at else None,
    }
