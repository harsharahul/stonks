"""
Feed API endpoints
Handles mixed feed of articles and signals
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.tasks.data_ingestion import fetch_google_news_by_ticker
from app.tasks.sec_edgar_ingestion import fetch_sec_edgar_rss, map_cik_to_tickers
from app.tasks.earnings_calendar import fetch_nasdaq_earnings_calendar, fetch_yahoo_earnings_calendar
from app.tasks.post_ingest_hooks import process_new_articles, update_source_reliability
from app.api.dependencies import verify_api_key

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


@router.post("/ingest/google-news", dependencies=[Depends(verify_api_key)])
async def ingest_google_news(
    background_tasks: BackgroundTasks,
    ticker: str = Query(..., min_length=1, description="Ticker symbol"),
    days: int = Query(7, ge=1, le=30, description="Days window for news"),
    db: Session = Depends(get_db)
):
    """On-demand ingestion: pull Google News RSS for a ticker and persist articles."""
    task = fetch_google_news_by_ticker.delay(ticker.upper(), days)
    return {
        "message": f"Google News ingestion triggered for {ticker.upper()}",
        "task_id": task.id,
        "ticker": ticker.upper(),
        "days": days
    }


@router.post("/ingest/sec-edgar", dependencies=[Depends(verify_api_key)])
async def ingest_sec_edgar(
    background_tasks: BackgroundTasks,
    filing_types: Optional[List[str]] = Query(None, description="Filing types (8-K, 10-K, 10-Q)"),
    days_back: int = Query(1, ge=1, le=30, description="Days to look back"),
    db: Session = Depends(get_db)
):
    """Trigger SEC EDGAR RSS feed ingestion for material filings."""
    task = fetch_sec_edgar_rss.delay(filing_types, days_back)
    return {
        "message": "SEC EDGAR ingestion triggered",
        "task_id": task.id,
        "filing_types": filing_types or ["8-K", "10-K", "10-Q"],
        "days_back": days_back
    }


@router.post("/ingest/earnings-calendar", dependencies=[Depends(verify_api_key)])
async def ingest_earnings_calendar(
    background_tasks: BackgroundTasks,
    days_ahead: int = Query(7, ge=1, le=30, description="Days to look ahead"),
    days_back: int = Query(3, ge=0, le=7, description="Days to look back"),
    db: Session = Depends(get_db)
):
    """Trigger earnings calendar ingestion."""
    task = fetch_nasdaq_earnings_calendar.delay(days_ahead, days_back)
    return {
        "message": "Earnings calendar ingestion triggered",
        "task_id": task.id,
        "days_ahead": days_ahead,
        "days_back": days_back
    }


@router.post("/ingest/earnings-ticker", dependencies=[Depends(verify_api_key)])
async def ingest_earnings_for_ticker(
    background_tasks: BackgroundTasks,
    ticker: str = Query(..., description="Stock ticker symbol"),
    db: Session = Depends(get_db)
):
    """Fetch earnings date for a specific ticker from Yahoo Finance."""
    task = fetch_yahoo_earnings_calendar.delay(ticker.upper())
    return {
        "message": f"Earnings date fetch triggered for {ticker.upper()}",
        "task_id": task.id,
        "ticker": ticker.upper()
    }


@router.post("/process/articles", dependencies=[Depends(verify_api_key)])
async def process_articles(
    background_tasks: BackgroundTasks,
    hours_back: int = Query(1, ge=1, le=24, description="Process articles from last N hours"),
    batch_size: int = Query(100, ge=10, le=500, description="Batch size"),
    db: Session = Depends(get_db)
):
    """Process recently ingested articles for sentiment and ticker extraction."""
    task = process_new_articles.delay(hours_back, batch_size)
    return {
        "message": "Article processing triggered",
        "task_id": task.id,
        "hours_back": hours_back,
        "batch_size": batch_size
    }


@router.post("/process/cik-mapping", dependencies=[Depends(verify_api_key)])
async def map_cik_tickers(
    background_tasks: BackgroundTasks,
    limit: int = Query(100, ge=10, le=1000, description="Max articles to process"),
    db: Session = Depends(get_db)
):
    """Map CIK numbers to stock tickers for SEC filings."""
    task = map_cik_to_tickers.delay(limit)
    return {
        "message": "CIK to ticker mapping triggered",
        "task_id": task.id,
        "limit": limit
    }


@router.post("/maintenance/update-reliability", dependencies=[Depends(verify_api_key)])
async def update_reliability(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Update data source reliability scores based on article quality."""
    task = update_source_reliability.delay()
    return {
        "message": "Source reliability update triggered",
        "task_id": task.id
    }
