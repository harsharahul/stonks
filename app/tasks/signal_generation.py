"""
Signal Generation Celery Tasks

Background tasks for generating trading signals and alerts from analytics features.
"""

import logging
from typing import List, Dict
from datetime import datetime, timedelta
from celery import shared_task
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.etl_job_run import ETLJobRun
from app.models.signal import Signal
from app.models.alert import Alert
from app.services.signal_generator import SignalGenerator
from app.services.alert_engine import AlertEngine
from app.services.websocket_manager import event_broadcaster
import asyncio

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_signals_task(self, tickers: List[str]) -> Dict:
    """
    Generate signals for a list of tickers
    
    Args:
        tickers: List of ticker symbols to process
        
    Returns:
        Dict with generation statistics
    """
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        print(f"🚨 Generating signals for {len(tickers)} tickers")
        
        # Create ETL job run
        job_run = ETLJobRun(
            job_name="signal_generation",
            status="running",
            started_at=datetime.utcnow(),
            details={
                "task_id": task_id,
                "tickers": tickers,
                "ticker_count": len(tickers)
            }
        )
        db.add(job_run)
        db.commit()
        
        # Initialize signal generator
        generator = SignalGenerator(db)
        
        # Generate signals for each ticker
        all_signals = []
        ticker_results = {}
        
        for ticker in tickers:
            try:
                signals = generator.generate_signals_for_ticker(ticker)
                all_signals.extend(signals)
                ticker_results[ticker] = len(signals)
                print(f"   📊 {ticker}: {len(signals)} signals generated")
                
            except Exception as e:
                logger.error(f"Error generating signals for {ticker}: {e}")
                ticker_results[ticker] = 0
                continue
        
        # Save all signals
        signals_saved = generator.save_signals(all_signals)
        
        # Update job run
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = signals_saved
        job_run.details.update({
            "signals_generated": signals_saved,
            "ticker_results": ticker_results,
            "tickers_processed": len([t for t in ticker_results.values() if t >= 0])
        })
        db.commit()
        
        print(f"✅ Signal generation complete: {signals_saved} signals saved")
        
        return {
            "status": "success",
            "tickers_processed": len(tickers),
            "signals_generated": signals_saved,
            "ticker_results": ticker_results
        }
        
    except Exception as e:
        if 'job_run' in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({
                "error": str(e),
                "error_type": type(e).__name__
            })
            db.commit()
        print(f"❌ Error in signal generation: {e}")
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def generate_alerts_task(self, hours_back: int = 1) -> Dict:
    """
    Generate alerts from recent signals
    
    Args:
        hours_back: Process signals from last N hours
        
    Returns:
        Dict with alert generation statistics
    """
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        print(f"🔔 Generating alerts from signals (last {hours_back} hours)")
        
        # Create ETL job run
        job_run = ETLJobRun(
            job_name="alert_generation",
            status="running",
            started_at=datetime.utcnow(),
            details={
                "task_id": task_id,
                "hours_back": hours_back
            }
        )
        db.add(job_run)
        db.commit()
        
        # Get recent signals
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        recent_signals = db.query(Signal).filter(
            Signal.generated_at > cutoff_time
        ).all()
        
        print(f"   📊 Processing {len(recent_signals)} recent signals")
        
        # Initialize alert engine
        alert_engine = AlertEngine(db)
        
        # Generate alerts from signals
        alerts = alert_engine.process_signals(recent_signals)
        
        # Save alerts
        alerts_saved = alert_engine.save_alerts(alerts)
        
        # Group alerts by type for reporting
        alerts_by_type = {}
        alerts_by_severity = {}
        
        for alert in alerts:
            alerts_by_type[alert.alert_type] = alerts_by_type.get(alert.alert_type, 0) + 1
            alerts_by_severity[alert.severity] = alerts_by_severity.get(alert.severity, 0) + 1
        
        # Broadcast alerts to websocket clients
        try:
            for alert in alerts:
                asyncio.run(event_broadcaster.broadcast_alert(alert.to_dict()))
        except Exception as be:
            logger.error(f"Broadcast error: {be}")

        # Update job run
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = alerts_saved
        job_run.details.update({
            "signals_processed": len(recent_signals),
            "alerts_generated": alerts_saved,
            "alerts_by_type": alerts_by_type,
            "alerts_by_severity": alerts_by_severity
        })
        db.commit()
        
        print(f"✅ Alert generation complete: {alerts_saved} alerts created")
        print(f"   By type: {alerts_by_type}")
        print(f"   By severity: {alerts_by_severity}")
        
        return {
            "status": "success",
            "signals_processed": len(recent_signals),
            "alerts_generated": alerts_saved,
            "alerts_by_type": alerts_by_type,
            "alerts_by_severity": alerts_by_severity
        }
        
    except Exception as e:
        if 'job_run' in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({
                "error": str(e),
                "error_type": type(e).__name__
            })
            db.commit()
        print(f"❌ Error in alert generation: {e}")
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def daily_signal_generation_task(self) -> Dict:
    """
    Daily task to generate signals for all active stocks
    Runs as part of the daily analytics pipeline
    """
    db = SessionLocal()
    
    try:
        print("🔄 Starting daily signal generation for all active stocks")
        
        # Get all active stocks
        from app.models.stock import Stock
        stocks = db.query(Stock.symbol).all()
        ticker_list = [stock.symbol for stock in stocks]
        
        print(f"   📊 Processing {len(ticker_list)} active stocks")
        
        # Generate signals for all tickers
        result = generate_signals_task.apply(args=[ticker_list])
        
        # Generate alerts from new signals
        alert_result = generate_alerts_task.apply(args=[2])  # Process last 2 hours of signals
        
        return {
            "status": "success",
            "daily_signal_generation": True,
            "total_stocks": len(ticker_list),
            "signal_result": result.get(),
            "alert_result": alert_result.get()
        }
        
    except Exception as e:
        print(f"❌ Error in daily signal generation: {e}")
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def cleanup_expired_signals_task(self, days_old: int = 7) -> Dict:
    """
    Clean up old and expired signals to manage database size
    
    Args:
        days_old: Remove signals older than N days
        
    Returns:
        Dict with cleanup statistics
    """
    db = SessionLocal()
    
    try:
        print(f"🧹 Cleaning up signals older than {days_old} days")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Count signals to be deleted
        signals_to_delete = db.query(Signal).filter(
            Signal.generated_at < cutoff_date
        ).count()
        
        # Delete old signals
        deleted_count = db.query(Signal).filter(
            Signal.generated_at < cutoff_date
        ).delete()
        
        # Also clean up old alerts (keep for longer - 30 days)
        alert_cutoff = datetime.utcnow() - timedelta(days=30)
        alerts_deleted = db.query(Alert).filter(
            Alert.triggered_at < alert_cutoff
        ).delete()
        
        db.commit()
        
        print(f"✅ Cleanup complete: {deleted_count} signals, {alerts_deleted} alerts removed")
        
        return {
            "status": "success",
            "signals_deleted": deleted_count,
            "alerts_deleted": alerts_deleted,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error in signal cleanup: {e}")
        db.rollback()
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def signal_performance_analysis_task(self, days: int = 30) -> Dict:
    """
    Analyze signal performance over time for model improvement
    
    Args:
        days: Number of days to analyze
        
    Returns:
        Dict with performance statistics
    """
    db = SessionLocal()
    
    try:
        print(f"📈 Analyzing signal performance over last {days} days")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get signals from the period
        signals = db.query(Signal).filter(
            Signal.generated_at > cutoff_date
        ).all()
        
        if not signals:
            return {"status": "no_data", "message": "No signals found in period"}
        
        # Analyze by signal type
        type_stats = {}
        direction_stats = {"bullish": 0, "bearish": 0, "neutral": 0}
        
        for signal in signals:
            # Count by type
            if signal.signal_type not in type_stats:
                type_stats[signal.signal_type] = {
                    "count": 0,
                    "avg_strength": 0,
                    "avg_confidence": 0,
                    "total_strength": 0,
                    "total_confidence": 0
                }
            
            stats = type_stats[signal.signal_type]
            stats["count"] += 1
            stats["total_strength"] += abs(signal.strength)
            stats["total_confidence"] += signal.confidence
            
            # Count by direction
            direction_stats[signal.direction] += 1
        
        # Calculate averages
        for signal_type, stats in type_stats.items():
            if stats["count"] > 0:
                stats["avg_strength"] = round(stats["total_strength"] / stats["count"], 3)
                stats["avg_confidence"] = round(stats["total_confidence"] / stats["count"], 3)
            del stats["total_strength"]
            del stats["total_confidence"]
        
        print(f"✅ Performance analysis complete: {len(signals)} signals analyzed")
        
        return {
            "status": "success",
            "period_days": days,
            "total_signals": len(signals),
            "signal_type_breakdown": type_stats,
            "direction_breakdown": direction_stats,
            "analysis_date": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error in performance analysis: {e}")
        raise
        
    finally:
        db.close()
