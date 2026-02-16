"""
Anomaly Detection API endpoints

Provides real-time anomaly detection for price, volume, sentiment, and market patterns.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.anomaly_detector import (
    AnomalyDetectionOrchestrator,
    StatisticalAnomalyDetector,
    CrossAssetAnomalyDetector,
    TimeSeriesAnomalyDetector
)

router = APIRouter()


@router.get("/")
async def detect_anomalies(
    ticker: Optional[str] = Query(None, description="Specific ticker to analyze"),
    include_market_wide: bool = Query(True, description="Include market-wide anomaly detection"),
    min_severity: float = Query(0.3, ge=0.0, le=1.0, description="Minimum severity threshold"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of anomalies to return"),
    db: Session = Depends(get_db)
):
    """
    Detect anomalies across all algorithms
    """
    try:
        orchestrator = AnomalyDetectionOrchestrator(db)
        anomalies = orchestrator.detect_all_anomalies(ticker, include_market_wide)
        
        # Filter by minimum severity
        filtered_anomalies = [
            a for a in anomalies 
            if a.severity >= min_severity
        ][:limit]
        
        # Convert to dict format
        anomaly_dicts = []
        for anomaly in filtered_anomalies:
            anomaly_dicts.append({
                "ticker": anomaly.ticker,
                "anomaly_type": anomaly.anomaly_type,
                "severity": round(anomaly.severity, 3),
                "z_score": round(anomaly.z_score, 2),
                "current_value": round(anomaly.current_value, 4),
                "expected_value": round(anomaly.expected_value, 4),
                "threshold": anomaly.threshold,
                "confidence": round(anomaly.confidence, 3),
                "detected_at": anomaly.detected_at.isoformat(),
                "metadata": anomaly.metadata
            })
        
        return {
            "anomalies": anomaly_dicts,
            "total_detected": len(anomalies),
            "filtered_count": len(filtered_anomalies),
            "filters": {
                "ticker": ticker,
                "include_market_wide": include_market_wide,
                "min_severity": min_severity
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{ticker}")
async def detect_ticker_anomalies(
    ticker: str,
    lookback_days: int = Query(30, ge=7, le=90, description="Days of historical data to analyze"),
    z_threshold: float = Query(2.5, ge=1.0, le=5.0, description="Z-score threshold for anomalies"),
    db: Session = Depends(get_db)
):
    """
    Detect anomalies for a specific ticker
    """
    try:
        detector = StatisticalAnomalyDetector(db)
        
        # Run all detection types
        price_anomalies = detector.detect_price_anomalies(ticker, lookback_days, z_threshold)
        sentiment_anomalies = detector.detect_sentiment_anomalies(ticker, lookback_days, z_threshold)
        
        # Feature anomalies for key metrics
        feature_anomalies = []
        key_features = ['momentum_14d', 'wsb_sentiment_7d', 'retail_buzz_score', 'vol_z']
        
        for feature in key_features:
            feature_result = detector.detect_feature_anomalies(ticker, feature, lookback_days, z_threshold)
            feature_anomalies.extend(feature_result)
        
        # Time series anomalies
        ts_detector = TimeSeriesAnomalyDetector(db)
        pattern_anomalies = ts_detector.detect_pattern_breaks(ticker, lookback_days)
        volatility_anomalies = ts_detector.detect_volatility_anomalies(ticker, lookback_days)
        
        # Combine all anomalies
        all_anomalies = (
            price_anomalies + sentiment_anomalies + feature_anomalies + 
            pattern_anomalies + volatility_anomalies
        )
        
        # Sort by severity
        all_anomalies.sort(key=lambda x: x.severity, reverse=True)
        
        # Convert to response format
        anomaly_dicts = []
        for anomaly in all_anomalies:
            anomaly_dicts.append({
                "anomaly_type": anomaly.anomaly_type,
                "severity": round(anomaly.severity, 3),
                "z_score": round(anomaly.z_score, 2),
                "current_value": round(anomaly.current_value, 4),
                "expected_value": round(anomaly.expected_value, 4),
                "confidence": round(anomaly.confidence, 3),
                "detected_at": anomaly.detected_at.isoformat(),
                "metadata": anomaly.metadata
            })
        
        return {
            "ticker": ticker.upper(),
            "anomalies": anomaly_dicts,
            "total_detected": len(all_anomalies),
            "parameters": {
                "lookback_days": lookback_days,
                "z_threshold": z_threshold
            },
            "analysis_types": [
                "price_volume", "sentiment", "features", "patterns", "volatility"
            ],
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market")
async def detect_market_anomalies(
    lookback_days: int = Query(30, ge=7, le=90, description="Days of historical data"),
    correlation_threshold: float = Query(0.8, ge=0.5, le=1.0, description="Correlation change threshold"),
    db: Session = Depends(get_db)
):
    """
    Detect market-wide anomalies and correlation breakdowns
    """
    try:
        cross_asset_detector = CrossAssetAnomalyDetector(db)
        statistical_detector = StatisticalAnomalyDetector(db)
        
        # Detect correlation anomalies
        correlation_anomalies = cross_asset_detector.detect_correlation_anomalies(
            lookback_days=lookback_days,
            correlation_threshold=correlation_threshold
        )
        
        # Detect market-wide sentiment anomalies
        market_anomalies = cross_asset_detector.detect_market_wide_anomalies(lookback_days)
        
        # Combine results
        all_anomalies = correlation_anomalies + market_anomalies
        all_anomalies.sort(key=lambda x: x.severity, reverse=True)
        
        # Convert to response format
        anomaly_dicts = []
        for anomaly in all_anomalies:
            anomaly_dicts.append({
                "ticker": anomaly.ticker,
                "anomaly_type": anomaly.anomaly_type,
                "severity": round(anomaly.severity, 3),
                "z_score": round(anomaly.z_score, 2),
                "current_value": round(anomaly.current_value, 4),
                "expected_value": round(anomaly.expected_value, 4),
                "confidence": round(anomaly.confidence, 3),
                "detected_at": anomaly.detected_at.isoformat(),
                "metadata": anomaly.metadata
            })
        
        return {
            "market_anomalies": anomaly_dicts,
            "total_detected": len(all_anomalies),
            "parameters": {
                "lookback_days": lookback_days,
                "correlation_threshold": correlation_threshold
            },
            "analysis_types": ["correlation_breakdown", "market_sentiment"],
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price/{ticker}")
async def detect_price_anomalies(
    ticker: str,
    lookback_days: int = Query(30, ge=7, le=90, description="Days of historical data"),
    z_threshold: float = Query(2.5, ge=1.0, le=5.0, description="Z-score threshold"),
    db: Session = Depends(get_db)
):
    """
    Detect price and volume anomalies for a specific ticker
    """
    try:
        detector = StatisticalAnomalyDetector(db)
        anomalies = detector.detect_price_anomalies(ticker, lookback_days, z_threshold)
        
        return {
            "ticker": ticker.upper(),
            "price_anomalies": [
                {
                    "anomaly_type": a.anomaly_type,
                    "severity": round(a.severity, 3),
                    "z_score": round(a.z_score, 2),
                    "current_value": round(a.current_value, 4),
                    "expected_value": round(a.expected_value, 4),
                    "confidence": round(a.confidence, 3),
                    "metadata": a.metadata
                }
                for a in anomalies
            ],
            "parameters": {
                "lookback_days": lookback_days,
                "z_threshold": z_threshold
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment/{ticker}")
async def detect_sentiment_anomalies(
    ticker: str,
    lookback_days: int = Query(30, ge=7, le=90, description="Days of historical data"),
    z_threshold: float = Query(2.0, ge=1.0, le=5.0, description="Z-score threshold"),
    db: Session = Depends(get_db)
):
    """
    Detect sentiment anomalies for a specific ticker
    """
    try:
        detector = StatisticalAnomalyDetector(db)
        anomalies = detector.detect_sentiment_anomalies(ticker, lookback_days, z_threshold)
        
        return {
            "ticker": ticker.upper(),
            "sentiment_anomalies": [
                {
                    "anomaly_type": a.anomaly_type,
                    "severity": round(a.severity, 3),
                    "z_score": round(a.z_score, 2),
                    "current_value": round(a.current_value, 3),
                    "expected_value": round(a.expected_value, 3),
                    "confidence": round(a.confidence, 3),
                    "metadata": a.metadata
                }
                for a in anomalies
            ],
            "parameters": {
                "lookback_days": lookback_days,
                "z_threshold": z_threshold
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns/{ticker}")
async def detect_pattern_anomalies(
    ticker: str,
    lookback_days: int = Query(60, ge=20, le=120, description="Days of historical data for pattern analysis"),
    db: Session = Depends(get_db)
):
    """
    Detect time series pattern anomalies (trend breaks, volatility spikes)
    """
    try:
        detector = TimeSeriesAnomalyDetector(db)
        
        pattern_anomalies = detector.detect_pattern_breaks(ticker, lookback_days)
        volatility_anomalies = detector.detect_volatility_anomalies(ticker, lookback_days)
        
        all_anomalies = pattern_anomalies + volatility_anomalies
        
        return {
            "ticker": ticker.upper(),
            "pattern_anomalies": [
                {
                    "anomaly_type": a.anomaly_type,
                    "severity": round(a.severity, 3),
                    "z_score": round(a.z_score, 2),
                    "current_value": round(a.current_value, 4),
                    "expected_value": round(a.expected_value, 4),
                    "confidence": round(a.confidence, 3),
                    "metadata": a.metadata
                }
                for a in all_anomalies
            ],
            "parameters": {
                "lookback_days": lookback_days
            },
            "analysis_types": ["trend_reversal", "volatility_spike"],
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_anomaly_summary(
    hours: int = Query(24, ge=1, le=168, description="Hours to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get summary of recent anomaly detection results
    """
    try:
        orchestrator = AnomalyDetectionOrchestrator(db)
        summary = orchestrator.get_anomaly_summary(hours)
        
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
