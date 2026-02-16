"""
Price History API endpoints
Serves OHLCV price data for stock detail charts
"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.stock import Stock
from app.models.price import Price
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Period to timedelta mapping
PERIOD_MAP = {
    "1W": timedelta(days=7),
    "1M": timedelta(days=30),
    "3M": timedelta(days=90),
    "6M": timedelta(days=180),
    "1Y": timedelta(days=365),
    "ALL": None,
}

VALID_PERIODS = list(PERIOD_MAP.keys())


@router.get("/{ticker}/history")
async def get_price_history(
    ticker: str,
    period: str = Query("1M", description=f"Time period: {', '.join(VALID_PERIODS)}"),
    db: Session = Depends(get_db),
):
    """Get OHLCV price history for a specific ticker."""
    period_upper = period.upper()
    if period_upper not in PERIOD_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period '{period}'. Must be one of: {', '.join(VALID_PERIODS)}",
        )

    stock = db.query(Stock).filter(
        Stock.symbol == ticker.upper(),
        Stock.is_active == True,
    ).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

    query = db.query(Price).filter(Price.stock_id == stock.id)

    delta = PERIOD_MAP[period_upper]
    if delta is not None:
        cutoff = datetime.utcnow() - delta
        query = query.filter(Price.ts >= cutoff)

    prices = query.order_by(Price.ts.asc()).all()

    if not prices:
        return {
            "ticker": ticker.upper(),
            "period": period_upper,
            "count": 0,
            "latest": None,
            "summary": None,
            "prices": [],
        }

    price_list = [
        {
            "date": p.ts.strftime("%Y-%m-%d") if p.ts else p.timestamp.strftime("%Y-%m-%d"),
            "open": float(p.open_price) if p.open_price else 0,
            "high": float(p.high) if p.high else 0,
            "low": float(p.low) if p.low else 0,
            "close": float(p.close) if p.close else float(p.price),
            "volume": p.volume or 0,
        }
        for p in prices
    ]

    latest = prices[-1]
    previous = prices[-2] if len(prices) >= 2 else latest
    current_price = float(latest.close) if latest.close else float(latest.price)
    prev_close = float(previous.close) if previous.close else float(previous.price)
    change = current_price - prev_close
    change_pct = change / prev_close if prev_close != 0 else 0

    period_high = max(float(p.high) if p.high else float(p.price) for p in prices)
    period_low = min(float(p.low) if p.low else float(p.price) for p in prices)
    avg_volume = sum((p.volume or 0) for p in prices) / len(prices)

    latest_ts = latest.ts or latest.timestamp
    return {
        "ticker": ticker.upper(),
        "period": period_upper,
        "count": len(price_list),
        "latest": {
            "date": latest_ts.strftime("%Y-%m-%d"),
            "open": float(latest.open_price) if latest.open_price else 0,
            "high": float(latest.high) if latest.high else 0,
            "low": float(latest.low) if latest.low else 0,
            "close": current_price,
            "volume": latest.volume or 0,
            "adjusted_close": float(latest.adjusted_close) if latest.adjusted_close else None,
        },
        "summary": {
            "current_price": current_price,
            "previous_close": prev_close,
            "change": round(change, 4),
            "change_percent": round(change_pct, 6),
            "period_high": period_high,
            "period_low": period_low,
            "avg_volume": round(avg_volume),
        },
        "prices": price_list,
    }
