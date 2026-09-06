"""
Signals API endpoints

Provides access to trading signals, alert management, and real-time market insights.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.signal import Signal
from app.models.alert import Alert
from app.services.signal_generator import SignalGenerator
from app.services.alert_engine import AlertEngine
from app.tasks.signal_generation import generate_signals_task, generate_alerts_task
from app.services.websocket_manager import event_broadcaster
from app.api.dependencies import verify_api_key, get_optional_user

router = APIRouter()


@router.get("/")
async def get_signals(
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    direction: Optional[str] = Query(None, description="Filter by direction (bullish/bearish/neutral)"),
    min_strength: Optional[float] = Query(None, ge=-1.0, le=1.0, description="Minimum signal strength"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence level"),
    active_only: bool = Query(True, description="Only return non-expired signals"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of signals"),
    db: Session = Depends(get_db)
):
    """Get trading signals with optional filtering"""
    
    query = db.query(Signal)
    
    # Apply filters
    if ticker:
        query = query.filter(Signal.ticker == ticker.upper())
    
    if signal_type:
        query = query.filter(Signal.signal_type == signal_type)
    
    if direction:
        query = query.filter(Signal.direction == direction)
    
    if min_strength is not None:
        query = query.filter(Signal.strength >= min_strength)
    
    if min_confidence is not None:
        query = query.filter(Signal.confidence >= min_confidence)
    
    if active_only:
        query = query.filter(Signal.expires_at > datetime.utcnow())
    
    # Order by generation time (newest first) and apply limit
    signals = query.order_by(Signal.generated_at.desc()).limit(limit).all()
    
    return {
        "signals": [signal.to_dict() for signal in signals],
        "count": len(signals),
        "filters": {
            "ticker": ticker,
            "signal_type": signal_type,
            "direction": direction,
            "min_strength": min_strength,
            "min_confidence": min_confidence,
            "active_only": active_only
        }
    }


# Alert endpoints - MUST be defined BEFORE parameterized routes to avoid conflicts
@router.get("/alerts")
async def get_alerts(
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledgment status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of alerts"),
    db: Session = Depends(get_db)
):
    """Get alerts with optional filtering"""
    
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    query = db.query(Alert).filter(Alert.triggered_at > cutoff_time)
    
    # Apply filters
    if ticker:
        query = query.filter(Alert.ticker == ticker.upper())
    
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    
    if severity:
        query = query.filter(Alert.severity == severity)
    
    if acknowledged is not None:
        if acknowledged:
            query = query.filter(Alert.acknowledged_at.isnot(None))
        else:
            query = query.filter(Alert.acknowledged_at.is_(None))
    
    alerts = query.order_by(Alert.triggered_at.desc()).limit(limit).all()
    
    return {
        "alerts": [alert.to_dict() for alert in alerts],
        "count": len(alerts),
        "filters": {
            "ticker": ticker,
            "alert_type": alert_type,
            "severity": severity,
            "hours": hours,
            "acknowledged": acknowledged
        }
    }


@router.get("/alerts/stats")
async def get_alert_stats(
    days: int = Query(7, ge=1, le=30, description="Days to analyze"),
    db: Session = Depends(get_db)
):
    """Get alert statistics for the specified period"""

    alert_engine = AlertEngine(db)
    stats = alert_engine.get_alert_stats(days)

    return stats


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a specific alert by ID"""

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return alert.to_dict()


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
):
    """Mark an alert as acknowledged"""
    import logging
    _logger = logging.getLogger(__name__)

    alert_engine = AlertEngine(db)
    success = alert_engine.acknowledge_alert(alert_id)

    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    who = user.email if user else "anonymous"
    _logger.info(f"Alert {alert_id} acknowledged by {who}")

    return {
        "message": "Alert acknowledged successfully",
        "alert_id": alert_id,
        "acknowledged_at": datetime.utcnow().isoformat(),
        "acknowledged_by": who,
    }


@router.post("/alerts/generate", dependencies=[Depends(verify_api_key)])
async def trigger_alert_generation(
    background_tasks: BackgroundTasks,
    hours: int = Query(1, ge=1, le=24, description="Process signals from last N hours"),
    db: Session = Depends(get_db)
):
    """Trigger alert generation from recent signals"""
    
    task = generate_alerts_task.delay(hours)
    
    return {
        "message": f"Alert generation triggered for signals from last {hours} hours",
        "task_id": task.id,
        "hours": hours
    }


@router.post("/alerts/generate/sync", dependencies=[Depends(verify_api_key)])
async def generate_and_broadcast_alerts_sync(
    hours: int = Query(1, ge=1, le=24, description="Process signals from last N hours"),
    db: Session = Depends(get_db)
):
    """Synchronously generate alerts from recent signals and broadcast them to WebSocket clients.

    This runs inside the API process so broadcasts reach connected clients immediately.
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_signals = db.query(Signal).filter(
            Signal.generated_at > cutoff_time
        ).all()

        alert_engine = AlertEngine(db)
        alerts = alert_engine.process_signals(recent_signals)
        saved = alert_engine.save_alerts(alerts)

        # Broadcast alerts to global channel
        for alert in alerts:
            await event_broadcaster.broadcast_alert(alert.to_dict())

        return {
            "status": "success",
            "signals_processed": len(recent_signals),
            "alerts_generated": saved,
            "broadcasted": saved
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate alerts: {str(e)}")


@router.get("/sources/track-record")
async def get_source_track_records(db: Session = Depends(get_db)):
    """Verified track record per signal source (win rate over 5-day horizon).

    Aggregated from `signal_outcomes`: every directional signal scored
    against its realized forward return. This is how users judge which
    sources are worth following.
    """
    from app.tasks.signal_outcomes import HORIZON_DAYS, source_track_records

    records = source_track_records(db)
    return {
        "horizon_days": HORIZON_DAYS,
        "sources": records,
        "total_scored": sum(r["scored"] for r in records.values()),
    }


@router.get("/types")
async def get_signal_types(
    db: Session = Depends(get_db)
):
    """Get available signal types and their descriptions"""

    from app.services.signal_generator import SignalGenerator
    generator = SignalGenerator(db)

    signal_types = {}
    for rule in generator.rules:
        signal_types[rule.signal_type] = {
            "description": rule.description,
            "timeframe": rule.timeframe,
            "expires_hours": rule.expires_hours,
            "min_confidence": rule.min_confidence
        }

    return {
        "signal_types": signal_types,
        "count": len(signal_types)
    }


@router.get("/market/overview")
async def get_market_overview(
    limit: int = Query(20, ge=5, le=50, description="Number of top signals to include"),
    db: Session = Depends(get_db)
):
    """Get market overview with top signals and recent alerts"""

    # Get top active signals
    generator = SignalGenerator(db)
    all_active_signals = generator.get_active_signals(limit=limit*2)  # Get more to filter

    # Group by ticker and get strongest signal per ticker
    ticker_signals = {}
    for signal in all_active_signals:
        if signal.ticker not in ticker_signals:
            ticker_signals[signal.ticker] = signal
        elif abs(signal.strength) > abs(ticker_signals[signal.ticker].strength):
            ticker_signals[signal.ticker] = signal

    # Sort by strength and take top N
    top_signals = sorted(
        ticker_signals.values(),
        key=lambda s: abs(s.strength),
        reverse=True
    )[:limit]

    # Get recent alerts
    alert_engine = AlertEngine(db)
    recent_alerts = alert_engine.get_recent_alerts(hours=4, limit=10)

    # Get alert stats
    alert_stats = alert_engine.get_alert_stats(days=1)

    return {
        "market_overview": {
            "top_signals": [signal.to_dict() for signal in top_signals],
            "recent_alerts": [alert.to_dict() for alert in recent_alerts],
            "alert_stats": alert_stats,
            "generated_at": datetime.utcnow().isoformat()
        }
    }


@router.get("/ticker/{ticker}")
async def get_ticker_signals(
    ticker: str,
    active_only: bool = Query(True, description="Only return non-expired signals"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of signals"),
    db: Session = Depends(get_db)
):
    """Get all signals for a specific ticker"""

    generator = SignalGenerator(db)

    if active_only:
        signals = generator.get_active_signals(ticker, limit)
    else:
        query = db.query(Signal).filter(Signal.ticker == ticker.upper())
        signals = query.order_by(Signal.generated_at.desc()).limit(limit).all()

    # Get signal summary
    summary = generator.get_signal_summary(ticker)

    return {
        "ticker": ticker.upper(),
        "summary": summary,
        "signals": [signal.to_dict() for signal in signals]
    }


@router.get("/ticker/{ticker}/summary")
async def get_ticker_signal_summary(
    ticker: str,
    db: Session = Depends(get_db)
):
    """Get signal summary for a specific ticker"""

    generator = SignalGenerator(db)
    summary = generator.get_signal_summary(ticker)

    return summary


@router.post("/generate/{ticker}", dependencies=[Depends(verify_api_key)])
async def trigger_signal_generation(
    ticker: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger signal generation for a specific ticker"""

    task = generate_signals_task.delay([ticker.upper()])

    return {
        "message": f"Signal generation triggered for {ticker.upper()}",
        "task_id": task.id,
        "ticker": ticker.upper()
    }


@router.post("/generate/bulk", dependencies=[Depends(verify_api_key)])
async def trigger_bulk_signal_generation(
    background_tasks: BackgroundTasks,
    tickers: Optional[str] = Query(None, description="Comma-separated list of tickers"),
    limit: int = Query(50, ge=1, le=200, description="Max tickers to process if no specific list"),
    db: Session = Depends(get_db)
):
    """Trigger bulk signal generation"""

    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
    else:
        # Get top active stocks
        from app.models.stock import Stock
        stocks = db.query(Stock.symbol).limit(limit).all()
        ticker_list = [stock.symbol for stock in stocks]

    task = generate_signals_task.delay(ticker_list)

    return {
        "message": f"Bulk signal generation triggered for {len(ticker_list)} tickers",
        "task_id": task.id,
        "tickers": ticker_list[:10],  # Show first 10
        "total_tickers": len(ticker_list)
    }


@router.get("/{signal_id}")
async def get_signal(
    signal_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a specific signal by ID"""

    signal = db.query(Signal).filter(Signal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    return signal.to_dict()