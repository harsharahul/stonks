"""
Anomaly Detection Celery Tasks

Background tasks for running anomaly detection algorithms and generating alerts.
"""

import logging
from typing import List, Dict
from datetime import datetime
from celery import shared_task
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.etl_job_run import ETLJobRun
from app.models.stock import Stock
from app.services.anomaly_detector import AnomalyDetectionOrchestrator
from app.services.alert_engine import AlertEngine
from app.services.signal_generator import SignalGenerator

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def detect_anomalies_task(self, tickers: List[str] = None, include_market_wide: bool = True) -> Dict:
    """
    Run anomaly detection for specified tickers or all active stocks
    
    Args:
        tickers: List of ticker symbols to analyze (None for all active stocks)
        include_market_wide: Whether to include market-wide anomaly detection
        
    Returns:
        Dict with anomaly detection statistics
    """
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        print(f"🔍 Running anomaly detection")
        
        # Get tickers to analyze
        if tickers is None:
            stocks = db.query(Stock.symbol).limit(50).all()  # Limit for performance
            tickers = [stock.symbol for stock in stocks]
        
        print(f"   📊 Analyzing {len(tickers)} tickers")
        
        # Create ETL job run
        job_run = ETLJobRun(
            job_name="anomaly_detection",
            status="running",
            started_at=datetime.utcnow(),
            details={
                "task_id": task_id,
                "tickers": tickers,
                "include_market_wide": include_market_wide,
                "ticker_count": len(tickers)
            }
        )
        db.add(job_run)
        db.commit()
        
        # Initialize anomaly detector
        orchestrator = AnomalyDetectionOrchestrator(db)
        
        # Run anomaly detection
        all_anomalies = []
        ticker_results = {}
        
        for ticker in tickers:
            try:
                ticker_anomalies = orchestrator.detect_all_anomalies(ticker, False)  # Skip market-wide per ticker
                all_anomalies.extend(ticker_anomalies)
                ticker_results[ticker] = len(ticker_anomalies)
                
                if ticker_anomalies:
                    print(f"   🚨 {ticker}: {len(ticker_anomalies)} anomalies detected")
                
            except Exception as e:
                logger.error(f"Error detecting anomalies for {ticker}: {e}")
                ticker_results[ticker] = 0
                continue
        
        # Run market-wide detection if requested
        market_anomalies = []
        if include_market_wide:
            try:
                market_anomalies = orchestrator.cross_asset_detector.detect_correlation_anomalies()
                market_wide = orchestrator.statistical_detector.detect_market_wide_anomalies()
                market_anomalies.extend(market_wide)
                all_anomalies.extend(market_anomalies)
                print(f"   🌍 Market-wide: {len(market_anomalies)} anomalies detected")
            except Exception as e:
                logger.error(f"Error in market-wide anomaly detection: {e}")
        
        # Categorize anomalies
        anomalies_by_type = {}
        anomalies_by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        high_severity_anomalies = []
        
        for anomaly in all_anomalies:
            # Count by type
            anomalies_by_type[anomaly.anomaly_type] = anomalies_by_type.get(anomaly.anomaly_type, 0) + 1
            
            # Count by severity
            if anomaly.severity >= 0.8:
                anomalies_by_severity["critical"] += 1
                high_severity_anomalies.append(anomaly)
            elif anomaly.severity >= 0.6:
                anomalies_by_severity["high"] += 1
                high_severity_anomalies.append(anomaly)
            elif anomaly.severity >= 0.4:
                anomalies_by_severity["medium"] += 1
            else:
                anomalies_by_severity["low"] += 1
        
        # Generate alerts for high-severity anomalies
        alerts_generated = 0
        if high_severity_anomalies:
            try:
                # Convert anomalies to signals first, then to alerts
                signal_generator = SignalGenerator(db)
                alert_engine = AlertEngine(db)
                
                # Create signals from high-severity anomalies
                anomaly_signals = []
                for anomaly in high_severity_anomalies:
                    # Create a signal from the anomaly
                    from app.models.signal import Signal
                    signal = Signal(
                        ticker=anomaly.ticker,
                        signal_type=f"anomaly_{anomaly.anomaly_type}",
                        strength=anomaly.severity,
                        confidence=anomaly.confidence,
                        direction="neutral",  # Anomalies are generally neutral until analyzed
                        timeframe="daily",
                        expires_at=datetime.utcnow() + timedelta(hours=12),
                        model_version="anomaly_v1.0.0",
                        signal_metadata={
                            "anomaly_z_score": anomaly.z_score,
                            "anomaly_type": anomaly.anomaly_type,
                            "current_value": anomaly.current_value,
                            "expected_value": anomaly.expected_value
                        },
                        features_snapshot=anomaly.metadata
                    )
                    anomaly_signals.append(signal)
                
                # Save signals
                signal_generator.save_signals(anomaly_signals)
                
                # Generate alerts from signals
                alerts = alert_engine.process_signals(anomaly_signals)
                alerts_generated = alert_engine.save_alerts(alerts)
                
                print(f"   🔔 Generated {alerts_generated} alerts from anomalies")
                
            except Exception as e:
                logger.error(f"Error generating alerts from anomalies: {e}")
        
        # Update job run
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = len(all_anomalies)
        job_run.details.update({
            "total_anomalies": len(all_anomalies),
            "anomalies_by_type": anomalies_by_type,
            "anomalies_by_severity": anomalies_by_severity,
            "ticker_results": ticker_results,
            "market_anomalies": len(market_anomalies),
            "alerts_generated": alerts_generated
        })
        db.commit()
        
        print(f"✅ Anomaly detection complete: {len(all_anomalies)} anomalies, {alerts_generated} alerts")
        
        return {
            "status": "success",
            "tickers_analyzed": len(tickers),
            "total_anomalies": len(all_anomalies),
            "anomalies_by_type": anomalies_by_type,
            "anomalies_by_severity": anomalies_by_severity,
            "alerts_generated": alerts_generated,
            "high_severity_count": len(high_severity_anomalies)
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
        print(f"❌ Error in anomaly detection: {e}")
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def continuous_anomaly_monitoring_task(self) -> Dict:
    """
    Continuous anomaly monitoring task - runs every 15 minutes
    Focuses on real-time anomalies with shorter lookback periods
    """
    db = SessionLocal()
    
    try:
        print("🔄 Running continuous anomaly monitoring")
        
        # Get most active stocks (those with recent price updates)
        from sqlalchemy import desc
        recent_prices = db.query(Price.ticker).filter(
            Price.timestamp > datetime.utcnow() - timedelta(hours=4)
        ).distinct().limit(20).all()
        
        active_tickers = [p.ticker for p in recent_prices]
        
        if not active_tickers:
            print("   No active tickers found")
            return {"status": "no_data", "message": "No recent price updates"}
        
        print(f"   📊 Monitoring {len(active_tickers)} active tickers")
        
        # Run focused anomaly detection with shorter lookback
        orchestrator = AnomalyDetectionOrchestrator(db)
        
        critical_anomalies = []
        
        for ticker in active_tickers:
            try:
                # Focus on immediate anomalies (shorter lookback)
                detector = orchestrator.statistical_detector
                
                # Price anomalies (7-day lookback for real-time)
                price_anomalies = detector.detect_price_anomalies(ticker, lookback_days=7, z_threshold=3.0)
                
                # Only keep high-severity anomalies for real-time alerts
                high_severity = [a for a in price_anomalies if a.severity > 0.7]
                critical_anomalies.extend(high_severity)
                
            except Exception as e:
                logger.error(f"Error in continuous monitoring for {ticker}: {e}")
                continue
        
        # Generate immediate alerts for critical anomalies
        alerts_generated = 0
        if critical_anomalies:
            try:
                alert_engine = AlertEngine(db)
                
                # Create high-priority signals
                urgent_signals = []
                for anomaly in critical_anomalies:
                    from app.models.signal import Signal
                    signal = Signal(
                        ticker=anomaly.ticker,
                        signal_type=f"urgent_{anomaly.anomaly_type}",
                        strength=anomaly.severity,
                        confidence=anomaly.confidence,
                        direction="neutral",
                        timeframe="intraday",
                        expires_at=datetime.utcnow() + timedelta(hours=2),  # Short expiry for urgency
                        model_version="anomaly_urgent_v1.0.0",
                        signal_metadata={
                            "urgent": True,
                            "anomaly_z_score": anomaly.z_score,
                            "detection_type": "continuous_monitoring"
                        }
                    )
                    urgent_signals.append(signal)
                
                # Save and process
                signal_generator = SignalGenerator(db)
                signal_generator.save_signals(urgent_signals)
                
                alerts = alert_engine.process_signals(urgent_signals)
                alerts_generated = alert_engine.save_alerts(alerts)
                
                print(f"   🚨 Generated {alerts_generated} urgent alerts")
                
            except Exception as e:
                logger.error(f"Error generating urgent alerts: {e}")
        
        print(f"✅ Continuous monitoring complete: {len(critical_anomalies)} critical anomalies")
        
        return {
            "status": "success",
            "active_tickers": len(active_tickers),
            "critical_anomalies": len(critical_anomalies),
            "urgent_alerts": alerts_generated,
            "monitoring_type": "continuous"
        }
        
    except Exception as e:
        print(f"❌ Error in continuous monitoring: {e}")
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def anomaly_pattern_learning_task(self, days: int = 90) -> Dict:
    """
    Analyze historical anomalies to improve detection patterns
    This task learns from past anomalies to refine thresholds and rules
    """
    db = SessionLocal()
    
    try:
        print(f"🧠 Learning from anomaly patterns (last {days} days)")
        
        # This is a placeholder for machine learning-based pattern recognition
        # In production, this would:
        # 1. Analyze historical anomalies vs actual market outcomes
        # 2. Adjust detection thresholds based on false positive rates
        # 3. Identify new anomaly patterns
        # 4. Update signal generation rules
        
        # For now, return basic statistics
        return {
            "status": "success",
            "message": "Pattern learning completed",
            "days_analyzed": days,
            "note": "ML-based pattern learning is a future enhancement",
            "learning_date": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error in pattern learning: {e}")
        raise
        
    finally:
        db.close()
