"""
Features API endpoints
Handles feature store data and calculation triggers
"""
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.ticker_features_daily import TickerFeaturesDaily
from app.models.stock import Stock
from app.features import FeatureAggregator
from app.tasks.feature_calculation import calculate_daily_features, calculate_features_for_ticker
from app.llm import enhance_analytics_with_llm_sync
from app.models.article import Article
from app.api.dependencies import verify_api_key, enforce_rate_limit
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _fetch_daily_features_dict(
    db: Session,
    ticker: str,
    target_date: Optional[str] = None,
    feature_version: str = "v1.0.0",
):
    """Internal helper to fetch daily features as a plain dict.

    Avoids calling the async route handler directly and bypasses FastAPI Query defaults.
    """
    # Resolve date
    if target_date:
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        date_obj = date.today()

    # Query features
    features_row = (
        db.query(TickerFeaturesDaily)
        .filter(
            TickerFeaturesDaily.ticker == ticker.upper(),
            TickerFeaturesDaily.date == date_obj,
            TickerFeaturesDaily.feature_version == feature_version,
        )
        .first()
    )
    if not features_row:
        raise HTTPException(
            status_code=404,
            detail=f"No features found for {ticker} on {date_obj} (version {feature_version})",
        )

    return features_row.to_dict()


@router.get("/daily/{ticker}")
async def get_daily_features(
    ticker: str,
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    feature_version: Optional[str] = Query("v1.0.0", description="Feature version"),
    db: Session = Depends(get_db)
):
    """
    Get daily features for a specific ticker
    """
    return _fetch_daily_features_dict(
        db=db,
        ticker=ticker,
        target_date=target_date,
        feature_version=feature_version or "v1.0.0",
    )


@router.get("/daily/{ticker}/history")
async def get_feature_history(
    ticker: str,
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    feature_version: Optional[str] = Query("v1.0.0", description="Feature version"),
    db: Session = Depends(get_db)
):
    """
    Get feature history for a ticker over specified days
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    features = db.query(TickerFeaturesDaily).filter(
        TickerFeaturesDaily.ticker == ticker.upper(),
        TickerFeaturesDaily.date >= start_date,
        TickerFeaturesDaily.date <= end_date,
        TickerFeaturesDaily.feature_version == feature_version
    ).order_by(TickerFeaturesDaily.date.desc()).all()
    
    return {
        "ticker": ticker.upper(),
        "feature_version": feature_version,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "count": len(features),
        "features": [f.to_dict() for f in features]
    }


@router.get("/summary")
async def get_features_summary(
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    feature_version: Optional[str] = Query("v1.0.0", description="Feature version"),
    limit: int = Query(20, ge=1, le=100, description="Number of tickers to return"),
    db: Session = Depends(get_db)
):
    """
    Get feature summary for multiple tickers on a specific date
    """
    # Parse date
    if target_date:
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        date_obj = date.today()
    
    # Query features for all tickers on the date
    features = db.query(TickerFeaturesDaily).filter(
        TickerFeaturesDaily.date == date_obj,
        TickerFeaturesDaily.feature_version == feature_version
    ).order_by(TickerFeaturesDaily.ticker).limit(limit).all()
    
    return {
        "date": date_obj.isoformat(),
        "feature_version": feature_version,
        "count": len(features),
        "features": [
            {
                "ticker": f.ticker,
                "sent_mean_7d": float(f.sent_mean_7d) if f.sent_mean_7d else None,
                "ret_5d": float(f.ret_5d) if f.ret_5d else None,
                "vol_z": float(f.vol_z) if f.vol_z else None,
                "novelty_mean_3d": float(f.novelty_mean_3d) if f.novelty_mean_3d else None,
                "conflict_score": float(f.conflict_score) if f.conflict_score else None,
                "article_count_7d": f.article_count_7d
            }
            for f in features
        ]
    }


@router.post("/calculate/by-ticker/{ticker}", dependencies=[Depends(verify_api_key), Depends(enforce_rate_limit)])
async def trigger_feature_calculation(
    ticker: str,
    background_tasks: BackgroundTasks,
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db)
):
    """
    Trigger feature calculation for a specific ticker
    """
    # Validate ticker exists
    stock = db.query(Stock).filter(Stock.symbol == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")
    
    # Parse date
    if target_date:
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Trigger background task
    task = calculate_features_for_ticker.delay(ticker.upper(), target_date)
    
    return {
        "message": f"Feature calculation triggered for {ticker.upper()}",
        "task_id": task.id,
        "target_date": target_date or date.today().isoformat()
    }


@router.post("/calculate/sync/{ticker}", dependencies=[Depends(verify_api_key)])
async def calculate_features_sync(
    ticker: str,
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db)
):
    """
    Calculate features synchronously for immediate results
    """
    try:
        # Validate ticker exists
        stock = db.query(Stock).filter(Stock.symbol == ticker.upper()).first()
        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")
        
        # Parse date
        if target_date:
            try:
                target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            target_date_obj = date.today()
        
        # Calculate features directly
        from app.features.aggregator import FeatureAggregator
        aggregator = FeatureAggregator(db)
        features = aggregator.calculate_features_for_ticker(ticker.upper(), target_date_obj)
        
        # Store features
        record = aggregator.store_features(features)
        db.commit()
        
        return {
            "message": f"Features calculated successfully for {ticker}",
            "ticker": ticker.upper(),
            "target_date": target_date_obj.isoformat(),
            "features": record.to_dict(),
            "mode": "synchronous"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Feature calculation failed: {str(e)}")


@router.post("/calculate/daily", dependencies=[Depends(verify_api_key), Depends(enforce_rate_limit)])
async def trigger_daily_calculation(
    background_tasks: BackgroundTasks,
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    tickers: Optional[str] = Query(None, description="Comma-separated list of tickers"),
    db: Session = Depends(get_db)
):
    """
    Trigger daily feature calculation for all tickers or specified tickers
    """
    # Parse date
    if target_date:
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Parse tickers
    ticker_list = None
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        
        # Validate tickers exist
        existing_tickers = db.query(Stock.symbol).filter(
            Stock.symbol.in_(ticker_list),
            Stock.is_active == True
        ).all()
        existing_symbols = [t[0] for t in existing_tickers]
        
        invalid_tickers = set(ticker_list) - set(existing_symbols)
        if invalid_tickers:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid tickers: {list(invalid_tickers)}"
            )
    
    # Trigger background task
    task = calculate_daily_features.delay(target_date, ticker_list)
    
    return {
        "message": "Daily feature calculation triggered",
        "task_id": task.id,
        "target_date": target_date or date.today().isoformat(),
        "tickers": ticker_list or "all active tickers"
    }


@router.get("/calculate/immediate/{ticker}", dependencies=[Depends(verify_api_key), Depends(enforce_rate_limit)])
async def calculate_features_immediate(
    ticker: str,
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db)
):
    """
    Calculate features immediately (synchronous) for testing/debugging
    """
    # Validate ticker exists
    stock = db.query(Stock).filter(Stock.symbol == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")
    
    # Parse date
    if target_date:
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        date_obj = date.today()
    
    try:
        # Calculate features immediately
        aggregator = FeatureAggregator(db)
        features = aggregator.calculate_features_for_ticker(ticker.upper(), date_obj)
        
        # Store features
        record = aggregator.store_features(features)
        db.commit()
        
        return {
            "message": f"Features calculated and stored for {ticker.upper()}",
            "ticker": ticker.upper(),
            "date": date_obj.isoformat(),
            "features": record.to_dict()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error calculating features: {str(e)}")


@router.get("/stats")
async def get_feature_stats(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get feature store statistics and coverage
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Get feature coverage
    feature_count = db.query(TickerFeaturesDaily).filter(
        TickerFeaturesDaily.date >= start_date,
        TickerFeaturesDaily.date <= end_date
    ).count()
    
    # Get unique tickers with features
    unique_tickers = db.query(TickerFeaturesDaily.ticker).filter(
        TickerFeaturesDaily.date >= start_date,
        TickerFeaturesDaily.date <= end_date
    ).distinct().count()
    
    # Get total active tickers
    total_active = db.query(Stock).filter(Stock.is_active == True).count()
    
    # Get latest feature date
    latest_features = db.query(TickerFeaturesDaily).order_by(
        TickerFeaturesDaily.date.desc()
    ).first()
    
    coverage_rate = (unique_tickers / total_active) if total_active > 0 else 0
    
    return {
        "date_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days
        },
        "coverage": {
            "total_feature_records": feature_count,
            "unique_tickers_with_features": unique_tickers,
            "total_active_tickers": total_active,
            "coverage_rate": coverage_rate
        },
        "latest": {
            "latest_feature_date": latest_features.date.isoformat() if latest_features else None,
            "latest_ticker": latest_features.ticker if latest_features else None
        }
    }


@router.get("/{ticker}/enhanced", response_model=Dict[str, Any])
def get_enhanced_features(
    ticker: str,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    Get enhanced features with LLM-powered insights for a specific ticker
    """
    try:
        # Get the latest available features for this ticker
        latest_features = db.query(TickerFeaturesDaily).filter(
            TickerFeaturesDaily.ticker == ticker.upper(),
            TickerFeaturesDaily.feature_version == "v1.0.0"
        ).order_by(TickerFeaturesDaily.date.desc()).first()
        
        if not latest_features:
            raise HTTPException(
                status_code=404,
                detail=f"No features found for {ticker}"
            )
        
        # Get base features for the latest available date
        features = _fetch_daily_features_dict(
            db=db,
            ticker=ticker,
            target_date=latest_features.date.strftime("%Y-%m-%d"),
            feature_version="v1.0.0",
        )
        
        # Fetch recent articles for context (best-effort)
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        try:
            rows = (
                db.query(Article)
                .filter(
                    Article.tickers.contains([ticker]),
                    Article.published_at >= cutoff_date,
                )
                .order_by(Article.published_at.desc())
                .limit(10)
                .all()
            )
        except Exception as e:
            logger.warning(f"Could not fetch articles for {ticker}: {e}")
            rows = []

        # Convert articles to minimal dicts expected by LLM layer
        articles = [
            {
                "title": r.title,
                "sentiment": float(r.sentiment) if r.sentiment is not None else None,
                "url": r.url,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "raw_content": r.raw_content,
            }
            for r in rows
        ]
        
        # Enhance with LLM
        enhanced_result = enhance_analytics_with_llm_sync(
            ticker=ticker,
            features=features,  # features is already a dict
            articles=articles
        )
        
        if not enhanced_result['success']:
            # Return base features if LLM enhancement fails
            return {
                "ticker": ticker,
                "base_features": features,  # features is already a dict
                "llm_enhancement": {
                    "status": "failed",
                    "error": enhanced_result.get('error', 'Unknown error')
                }
            }
        
        return {
            "ticker": ticker,
            "base_features": features,  # features is already a dict
            "llm_enhancement": enhanced_result['enhanced_analytics']
        }
        
    except Exception as e:
        logger.error(f"Error getting enhanced features for {ticker}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/test/llm")
def test_llm_integration():
    """
    Test endpoint for LLM integration
    """
    try:
        # Test with mock data
        mock_features = {
            "ticker": "TEST",
            "sentiment": {"mean_7d": 0.6},
            "returns": {"ret_5d": 0.05},
            "context": {"article_count_7d": 5}
        }
        
        mock_articles = [
            {"title": "Test Article", "sentiment": 0.7}
        ]
        
        # Test LLM enhancement
        result = enhance_analytics_with_llm_sync(
            ticker="TEST",
            features=mock_features,
            articles=mock_articles
        )
        
        return {
            "status": "success",
            "llm_available": result['success'],
            "enhanced_analytics": result.get('enhanced_analytics', {}),
            "errors": result.get('errors', [])
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "llm_available": False
        }

@router.get("/test/basic")
def test_basic():
    """
    Basic test endpoint
    """
    return {"message": "Basic endpoint working", "status": "ok"}

@router.get("/test/features")
def test_features_basic():
    """
    Test basic features without LLM
    """
    try:
        # Just return a simple response
        return {
            "message": "Features test working",
            "status": "ok",
            "test_data": {"ticker": "TEST", "value": 123}
        }
    except Exception as e:
        return {"error": str(e)}
