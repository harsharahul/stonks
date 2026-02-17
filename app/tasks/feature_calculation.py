"""
Celery tasks for daily feature calculation and aggregation
"""

from datetime import date, datetime, timedelta
from typing import Optional, List
from celery import shared_task

from app.core.database import SessionLocal
from app.features import FeatureAggregator
from app.models.stock import Stock
from app.models.etl_job_run import ETLJobRun
from app.tasks.etl_helpers import get_or_create_etl_job


def _calculate_daily_features_impl(db, target_date_obj, tickers: List[str]) -> dict:
    """
    Core feature-calculation logic. Used by both the Celery task and
    backfill_features to avoid .apply_async().get() deadlock.
    """
    print(f"🔧 Calculating features for {target_date_obj} ({len(tickers)} tickers)")

    aggregator = FeatureAggregator(db)
    results = aggregator.calculate_and_store_daily_features(
        target_date=target_date_obj,
        tickers=tickers
    )
    db.commit()

    return {
        "status": "success",
        "target_date": target_date_obj.isoformat(),
        "processed_count": len(results),
        "total_count": len(tickers),
        "processed_tickers": list(results.keys()),
        "feature_version": aggregator.feature_version,
    }


@shared_task(bind=True)
def calculate_daily_features(
    self,
    target_date: Optional[str] = None,
    tickers: Optional[List[str]] = None
):
    """
    Calculate and store daily features for all active tickers
    
    Args:
        target_date: Date to calculate features for (YYYY-MM-DD format, defaults to today)
        tickers: Specific tickers to process (defaults to all active)
        
    Returns:
        Dictionary with task results
    """
    
    db = SessionLocal()
    task_id = self.request.id

    try:
        # Parse target date
        if target_date:
            target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        else:
            target_date_obj = date.today()

        # Get or reuse admin-created ETLJobRun
        job_run = get_or_create_etl_job(db, task_id, "feature_calculation", {
            "task_id": task_id,
            "target_date": target_date_obj.isoformat(),
            "tickers_filter": tickers,
        })

        # Get tickers to process
        if tickers is None:
            active_stocks = db.query(Stock).filter(Stock.is_active == True).all()
            tickers = [stock.symbol for stock in active_stocks]

        # Use shared helper
        result = _calculate_daily_features_impl(db, target_date_obj, tickers)

        # Update job run with success
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = result["processed_count"]
        job_run.details.update({
            "processed_tickers": result["processed_tickers"],
            "feature_version": result["feature_version"],
            "success_count": result["processed_count"],
            "error_count": len(tickers) - result["processed_count"]
        })
        db.commit()

        result["job_run_id"] = str(job_run.id)
        result["success_rate"] = result["processed_count"] / len(tickers) if tickers else 0
        return result

    except Exception as e:
        if 'job_run' in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({
                "error": str(e),
                "error_type": type(e).__name__
            })
            db.commit()

        print(f"❌ Error in daily feature calculation: {e}")
        raise

    finally:
        db.close()


@shared_task(bind=True)
def calculate_features_for_ticker(
    self,
    ticker: str,
    target_date: Optional[str] = None
):
    """
    Calculate features for a single ticker (used for backfilling or individual updates)
    
    Args:
        ticker: Stock ticker symbol
        target_date: Date to calculate features for (YYYY-MM-DD format, defaults to today)
        
    Returns:
        Dictionary with feature calculation results
    """
    
    db = SessionLocal()
    
    try:
        # Parse target date
        if target_date:
            target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        else:
            target_date_obj = date.today()
        
        print(f"🔧 Calculating features for {ticker} on {target_date_obj}")
        
        # Initialize feature aggregator
        aggregator = FeatureAggregator(db)
        
        # Calculate features
        features = aggregator.calculate_features_for_ticker(ticker, target_date_obj)
        
        # Store features
        record = aggregator.store_features(features)
        db.commit()
        
        # Convert to dict for serialization
        feature_dict = record.to_dict()
        
        return {
            "status": "success",
            "ticker": ticker,
            "target_date": target_date_obj.isoformat(),
            "features": feature_dict
        }
        
    except Exception as e:
        print(f"❌ Error calculating features for {ticker}: {e}")
        db.rollback()
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def backfill_features(
    self,
    start_date: str,
    end_date: str,
    tickers: Optional[List[str]] = None
):
    """
    Backfill features for a date range
    
    Args:
        start_date: Start date (YYYY-MM-DD format)
        end_date: End date (YYYY-MM-DD format)
        tickers: Specific tickers to process (defaults to all active)
        
    Returns:
        Dictionary with backfill results
    """
    
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        print(f"🔄 Starting feature backfill from {start_date_obj} to {end_date_obj}")
        
        # Create ETL job run record
        job_run = ETLJobRun(
            job_name="backfill_features",
            started_at=datetime.utcnow(),
            status="running",
            details={
                "task_id": task_id,
                "start_date": start_date_obj.isoformat(),
                "end_date": end_date_obj.isoformat(),
                "tickers_filter": tickers
            }
        )
        db.add(job_run)
        db.commit()
        
        # Get tickers to process
        if tickers is None:
            active_stocks = db.query(Stock).filter(Stock.is_active == True).all()
            tickers = [stock.symbol for stock in active_stocks]
        
        # Process each date
        current_date = start_date_obj
        total_processed = 0
        total_errors = 0
        
        while current_date <= end_date_obj:
            try:
                # Skip weekends (simple approach)
                if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                    print(f"📅 Processing {current_date}")
                    
                    # Direct call to avoid .apply_async().get() deadlock
                    result = _calculate_daily_features_impl(
                        db, current_date, tickers
                    )
                    
                    total_processed += result.get("processed_count", 0)
                    total_errors += (result.get("total_count", 0) - result.get("processed_count", 0))
                
            except Exception as e:
                print(f"❌ Error processing {current_date}: {e}")
                total_errors += len(tickers)
            
            current_date += timedelta(days=1)
        
        # Update job run with success
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = total_processed
        job_run.details.update({
            "total_processed": total_processed,
            "total_errors": total_errors,
            "date_range_days": (end_date_obj - start_date_obj).days + 1
        })
        
        db.commit()
        
        return {
            "status": "success",
            "start_date": start_date_obj.isoformat(),
            "end_date": end_date_obj.isoformat(),
            "total_processed": total_processed,
            "total_errors": total_errors,
            "tickers": tickers,
            "job_run_id": str(job_run.id)
        }
        
    except Exception as e:
        # Update job run with error
        if 'job_run' in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({
                "error": str(e),
                "error_type": type(e).__name__
            })
            db.commit()
        
        print(f"❌ Error in feature backfill: {e}")
        raise
        
    finally:
        db.close()
