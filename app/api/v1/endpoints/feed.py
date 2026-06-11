"""
Feed API endpoints
Handles mixed feed of articles and signals
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, String

from app.core.database import get_db
from app.worker import worker
from app.features.retail_sentiment import RetailSentimentFeatures
from app.api.dependencies import verify_api_key, require_admin
from app.core.config import settings
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
    from app.models.signal import Signal

    items = []

    # Build article query
    article_query = db.query(Article).order_by(Article.created_at.desc())

    if symbols:
        ticker_list = [s.strip().upper() for s in symbols.split(",")]
        article_query = article_query.filter(Article.tickers.overlap(ticker_list))

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            article_query = article_query.filter(Article.created_at >= since_dt)
        except ValueError:
            pass

    if until:
        try:
            until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
            article_query = article_query.filter(Article.created_at <= until_dt)
        except ValueError:
            pass

    # Get total count for pagination
    total_articles = article_query.count()

    # Fetch articles for this page
    offset = (page - 1) * page_size
    articles = article_query.offset(offset).limit(page_size).all()

    for article in articles:
        pub_at = article.published_at or article.created_at
        items.append({
            "type": "article",
            "id": str(article.id),
            "title": article.title or "Untitled",
            "url": article.url,
            "published_at": pub_at.isoformat() if pub_at else None,
            "tickers": article.tickers or [],
            "sentiment": float(article.sentiment) if article.sentiment else None,
        })

    # On page 1, also include a few recent signals
    if page == 1:
        signal_query = db.query(Signal).order_by(Signal.generated_at.desc()).limit(5)
        if symbols:
            ticker_list = [s.strip().upper() for s in symbols.split(",")]
            signal_query = signal_query.filter(Signal.ticker.in_(ticker_list))

        signals = signal_query.all()
        for sig in signals:
            items.append({
                "type": "signal",
                "id": str(sig.id),
                "symbol": sig.ticker,
                "signal_type": sig.signal_type,
                "value": float(sig.strength),
                "computed_at": sig.generated_at.isoformat() if sig.generated_at else None,
            })

    return {
        "items": items,
        "total": total_articles,
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


@router.get("/debug/articles")
async def debug_articles(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100, description="Number of articles to return")
):
    """Debug endpoint to check articles in database (development only)"""
    if settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=404, detail="Not found")
    try:
        articles = db.query(Article).order_by(Article.created_at.desc()).limit(limit).all()
        
        debug_data = []
        for article in articles:
            debug_data.append({
                "id": str(article.id),
                "title": article.title,
                "url": article.url,
                "source_id": article.source_id,
                "article_metadata": article.article_metadata,
                "created_at": article.created_at.isoformat() if article.created_at else None,
                "tickers": article.tickers
            })
        
        return {
            "total_articles": len(debug_data),
            "articles": debug_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get debug articles: {str(e)}")


@router.get("/ingest/status", dependencies=[Depends(require_admin)])
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
            ETLJobRun.job_name.like("%wsb%")
        ).order_by(ETLJobRun.started_at.desc()).first()
        
        if wsb_job:
            wsb_status = "operational" if wsb_job.status in ["completed", "success"] else "degraded"
            # Use simpler JSONB query for compatibility
            wsb_articles = db.query(Article).filter(
                Article.article_metadata.cast(String).like('%"source": "reddit_wsb_enhanced"%')
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
            ETLJobRun.job_name.like("%sec%edgar%")
        ).order_by(ETLJobRun.started_at.desc()).first()
        
        if sec_job:
            sec_status = "operational" if sec_job.status in ["completed", "success"] else "degraded"
            sec_articles = db.query(Article).filter(
                Article.article_metadata.cast(String).like('%"source": "sec_edgar_enhanced"%')
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
            earnings_status = "operational" if earnings_job.status in ["completed", "success"] else "degraded"
            earnings_articles = db.query(Article).filter(
                Article.article_metadata.cast(String).like('%"event_type": "earnings"%')
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
            ETLJobRun.job_name.like("%rss%")
        ).order_by(ETLJobRun.started_at.desc()).first()
        
        if news_job:
            # Check for both "completed" and "success" statuses
            news_status = "operational" if news_job.status in ["completed", "success"] else "degraded"
            news_articles = db.query(Article).filter(
                Article.article_metadata.cast(String).like('%"source": "google_news"%')
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
