"""
Feed API endpoints
Handles mixed feed of articles and signals
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.worker import worker
from app.features.retail_sentiment import RetailSentimentFeatures
from app.api.dependencies import verify_api_key
from app.models.etl_job_run import ETLJobRun
from app.models.article import Article

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
    task = worker.send_task('app.tasks.data_ingestion.fetch_google_news_by_ticker', args=[ticker.upper(), days])
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
    task = worker.send_task('app.tasks.sec_edgar_ingestion.fetch_sec_edgar_rss', args=[filing_types, days_back])
    return {
        "message": "SEC EDGAR ingestion triggered",
        "task_id": task.id,
        "filing_types": filing_types or ["8-K", "10-K", "10-Q"],
        "days_back": days_back
    }


@router.post("/ingest/sec-edgar-enhanced", dependencies=[Depends(verify_api_key)])
async def ingest_sec_edgar_enhanced(
    background_tasks: BackgroundTasks,
    filing_types: str = Query("8-K,10-K,10-Q", description="Comma-separated filing types to fetch"),
    days_back: int = Query(7, ge=1, le=30, description="Days to look back"),
    tickers: Optional[str] = Query(None, description="Comma-separated tickers to fetch"),
    db: Session = Depends(get_db)
):
    """Enhanced SEC EDGAR ingestion using sec-parser library"""
    try:
        # Parse comma-separated strings into lists
        filing_types_list = [ft.strip() for ft in filing_types.split(",")]
        tickers_list = [t.strip() for t in tickers.split(",")] if tickers else None
        
        task = worker.send_task('app.tasks.sec_edgar_enhanced.fetch_sec_edgar_enhanced', args=[days_back, filing_types_list, tickers_list])
        return {
            "message": "Enhanced SEC EDGAR ingestion triggered",
            "task_id": task.id,
            "days_back": days_back,
            "filing_types": filing_types_list,
            "tickers": tickers_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger enhanced SEC EDGAR ingestion: {str(e)}")


@router.post("/ingest/earnings-calendar", dependencies=[Depends(verify_api_key)])
async def ingest_earnings_calendar(
    background_tasks: BackgroundTasks,
    days_ahead: int = Query(7, ge=1, le=30, description="Days to look ahead"),
    days_back: int = Query(3, ge=0, le=7, description="Days to look back"),
    db: Session = Depends(get_db)
):
    """Trigger earnings calendar ingestion."""
    task = worker.send_task('app.tasks.earnings_calendar.fetch_nasdaq_earnings_calendar', args=[days_ahead, days_back])
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
    task = worker.send_task('app.tasks.earnings_calendar.fetch_yahoo_earnings_calendar', args=[ticker.upper()])
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
    task = worker.send_task('app.tasks.post_ingest_hooks.process_new_articles', args=[hours_back, batch_size])
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
    task = worker.send_task('app.tasks.sec_edgar_ingestion.map_cik_to_tickers', args=[limit])
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
    task = worker.send_task('app.tasks.post_ingest_hooks.update_source_reliability', args=[])
    return {
        "message": "Source reliability update triggered",
        "task_id": task.id
    }


@router.post("/ingest/wsb-hot", dependencies=[Depends(verify_api_key)])
async def ingest_wsb_hot_posts(
    background_tasks: BackgroundTasks,
    limit: int = Query(50, ge=10, le=100, description="Number of hot posts to fetch"),
    time_filter: str = Query("day", description="Time filter: hour, day, week, month"),
    db: Session = Depends(get_db)
):
    """Fetch hot posts from r/wallstreetbets for retail sentiment analysis."""
    task = worker.send_task('app.tasks.reddit_wsb_ingestion.fetch_wsb_hot_posts', args=[limit, time_filter])
    return {
        "message": f"WSB hot posts ingestion triggered (limit: {limit}, filter: {time_filter})",
        "task_id": task.id,
        "limit": limit,
        "time_filter": time_filter
    }


@router.post("/ingest/wsb-enhanced", dependencies=[Depends(verify_api_key)])
async def ingest_wsb_enhanced(
    background_tasks: BackgroundTasks,
    limit: int = Query(50, ge=10, le=100, description="Number of posts to fetch"),
    sort: str = Query("hot", description="Sort method (hot, new, top, rising)"),
    db: Session = Depends(get_db)
):
    """Enhanced WSB ingestion using improved Reddit parser."""
    try:
        task = worker.send_task('app.tasks.reddit_wsb_enhanced.fetch_wsb_enhanced', args=[limit, sort])
        return {
            "message": "Enhanced WSB ingestion triggered",
            "task_id": task.id,
            "limit": limit,
            "sort": sort
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger enhanced WSB ingestion: {str(e)}")


@router.post("/ingest/wsb-daily", dependencies=[Depends(verify_api_key)])
async def ingest_wsb_daily_thread(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Fetch WSB daily discussion thread for general market sentiment."""
    task = worker.send_task('app.tasks.reddit_wsb_ingestion.fetch_wsb_daily_thread', args=[])
    return {
        "message": "WSB daily thread ingestion triggered",
        "task_id": task.id
    }


@router.get("/wsb/trending")
async def get_wsb_trending_tickers(
    days: int = Query(7, ge=1, le=30, description="Days to look back"),
    limit: int = Query(20, ge=5, le=50, description="Max tickers to return"),
    db: Session = Depends(get_db)
):
    """Get tickers trending on WallStreetBets based on mentions and engagement."""
    try:
        trending = RetailSentimentFeatures.get_trending_tickers(db, days, limit)
        return {
            "trending_tickers": trending,
            "days": days,
            "total_found": len(trending),
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/rss-automated", dependencies=[Depends(verify_api_key)])
async def ingest_rss_automated(
    tickers: Optional[List[str]] = Query(None, description="Specific tickers to process (defaults to all active)")
):
    """
    Trigger automated RSS ingestion for all configured sources and tickers
    """
    try:
        task = worker.send_task('app.tasks.data_ingestion.ingest_rss_feeds_task', args=[tickers])
        
        return {
            "message": "Automated RSS ingestion triggered",
            "task_id": task.id,
            "tickers_requested": tickers,
            "mode": "automated"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger automated RSS ingestion: {e}")


@router.get("/ingest/status")
async def get_ingestion_status(
    db: Session = Depends(get_db)
):
    """
    Get real-time status of all data ingestion sources
    """
    try:
        # Get latest ETL job runs for each source
        sources_status = []
        
        # WSB Enhanced Source
        wsb_job = db.query(ETLJobRun).filter(
            ETLJobRun.job_name.like("%wsb%enhanced%")
        ).order_by(ETLJobRun.started_at.desc()).first()
        
        if wsb_job:
            wsb_status = "operational" if wsb_job.status == "completed" else "degraded"
            wsb_articles = db.query(Article).filter(
                func.jsonb_extract_path_text(Article.article_metadata, 'source') == 'reddit_wsb_enhanced'
            ).count()
            wsb_freshness = (datetime.utcnow() - wsb_job.started_at.replace(tzinfo=None)).total_seconds() / 60  # minutes ago
        else:
            wsb_status = "down"
            wsb_articles = 0
            wsb_freshness = None
            
        sources_status.append({
            "name": "WSB Enhanced",
            "status": wsb_status,
            "last_update": wsb_job.started_at.isoformat() if wsb_job else None,
            "article_count": wsb_articles,
            "freshness_minutes": round(wsb_freshness, 1) if wsb_freshness else None,
            "source_type": "reddit"
        })
        
        # SEC EDGAR Enhanced Source
        sec_job = db.query(ETLJobRun).filter(
            ETLJobRun.job_name.like("%sec%edgar%enhanced%")
        ).order_by(ETLJobRun.started_at.desc()).first()
        
        if sec_job:
            sec_status = "operational" if sec_job.status == "completed" else "degraded"
            sec_articles = db.query(Article).filter(
                func.jsonb_extract_path_text(Article.article_metadata, 'source') == 'sec_edgar_enhanced'
            ).count()
            sec_freshness = (datetime.utcnow() - sec_job.started_at.replace(tzinfo=None)).total_seconds() / 60
        else:
            sec_status = "down"
            sec_articles = 0
            sec_freshness = None
            
        sources_status.append({
            "name": "SEC EDGAR Enhanced",
            "status": sec_status,
            "last_update": sec_job.started_at.isoformat() if sec_job else None,
            "article_count": sec_articles,
            "freshness_minutes": round(sec_freshness, 1) if sec_freshness else None,
            "source_type": "sec_edgar"
        })
        
        # Earnings Calendar Source
        earnings_job = db.query(ETLJobRun).filter(
            ETLJobRun.job_name.like("%earnings%")
        ).order_by(ETLJobRun.started_at.desc()).first()
        
        if earnings_job:
            earnings_status = "operational" if earnings_job.status == "completed" else "degraded"
            earnings_articles = db.query(Article).filter(
                func.jsonb_extract_path_text(Article.article_metadata, 'source') == 'earnings_calendar'
            ).count()
            earnings_freshness = (datetime.utcnow() - earnings_job.started_at.replace(tzinfo=None)).total_seconds() / 60
        else:
            earnings_status = "down"
            earnings_articles = 0
            earnings_freshness = None
            
        sources_status.append({
            "name": "Earnings Calendar",
            "status": earnings_status,
            "last_update": earnings_job.started_at.isoformat() if earnings_job else None,
            "article_count": earnings_articles,
            "freshness_minutes": round(earnings_freshness, 1) if earnings_freshness else None,
            "source_type": "earnings"
        })
        
        # News RSS Source
        news_job = db.query(ETLJobRun).filter(
            ETLJobRun.job_name.like("%google%news%")
        ).order_by(ETLJobRun.started_at.desc()).first()
        
        if news_job:
            news_status = "operational" if news_job.status == "completed" else "degraded"
            news_articles = db.query(Article).filter(
                func.jsonb_extract_path_text(Article.article_metadata, 'source') == 'google_news'
            ).count()
            news_freshness = (datetime.utcnow() - news_job.started_at.replace(tzinfo=None)).total_seconds() / 60
        else:
            news_status = "down"
            news_articles = 0
            news_freshness = None
            
        sources_status.append({
            "name": "News RSS",
            "status": news_status,
            "last_update": news_job.started_at.isoformat() if news_job else None,
            "article_count": news_articles,
            "freshness_minutes": round(news_freshness, 1) if news_freshness else None,
            "source_type": "news"
        })
        
        # Calculate overall system health
        operational_sources = sum(1 for source in sources_status if source["status"] == "operational")
        total_sources = len(sources_status)
        system_health = "healthy" if operational_sources >= total_sources * 0.75 else "degraded"
        
        return {
            "system_health": system_health,
            "operational_sources": operational_sources,
            "total_sources": total_sources,
            "sources": sources_status,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ingestion status: {str(e)}")
