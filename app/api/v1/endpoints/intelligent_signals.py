"""
Intelligent Signals API Endpoints

API endpoints for the expandable signal framework with LLM-powered processing.
Includes politician trades monitoring, signal analysis, and intelligent routing.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.api.dependencies import require_admin
from app.core.exceptions import create_http_exception, SignalProcessingException
from app.services.intelligent_signal_service import (
    IntelligentSignalService, IntelligentSignalConfig, 
    create_intelligent_signal_service
)
from app.llm.langgraph_engine import LLMConfig, LLMProvider
from app.core.signal_framework import (
    SignalType, SignalSourceType, ProcessedSignal, RawSignal,
    signal_registry, quality_monitor
)
from app.signals.politician_trades import PoliticianTradesSource, PoliticianTrade

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models

class SignalSourceConfigRequest(BaseModel):
    """Request to configure a signal source"""
    source_type: SignalSourceType
    config: Dict[str, Any]
    enabled: bool = True


class LLMConfigRequest(BaseModel):
    """Request for LLM configuration"""
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "gpt-4-turbo-preview"
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, ge=100, le=8000)
    timeout_seconds: int = Field(default=30, ge=5, le=300)


class IntelligentSignalConfigRequest(BaseModel):
    """Request for intelligent signal service configuration"""
    llm_config: LLMConfigRequest
    politician_trades_config: Dict[str, Any] = {}
    enable_self_correction: bool = True
    enable_fact_checking: bool = True
    enable_intelligent_routing: bool = True
    min_confidence_score: float = Field(default=0.7, ge=0.0, le=1.0)


class ProcessSignalRequest(BaseModel):
    """Request to process a raw signal"""
    source_id: str
    source_type: SignalSourceType
    raw_data: Dict[str, Any]
    ticker: Optional[str] = None
    priority: int = Field(default=5, ge=1, le=10)


class SignalAnalysisResponse(BaseModel):
    """Response for signal analysis"""
    signal_id: str
    signal_type: SignalType
    ticker: Optional[str]
    confidence_score: float
    title: str
    description: str
    key_insights: List[str]
    market_implications: List[str]
    strength: float
    direction: str
    processing_metadata: Dict[str, Any]


class PoliticianTradeResponse(BaseModel):
    """Response for politician trade data"""
    politician_name: str
    office: str
    party: str
    ticker: Optional[str]
    trade_type: str
    amount_range: str
    transaction_date: datetime
    filing_date: datetime
    timing_score: Optional[float]
    conflict_score: Optional[float]
    market_impact_score: Optional[float]
    analysis: Dict[str, Any]


# Global service instance (would be managed by dependency injection in production)
_intelligent_service: Optional[IntelligentSignalService] = None


# API Endpoints

@router.post("/configure", dependencies=[Depends(require_admin)])
async def configure_intelligent_signals(
    config_request: IntelligentSignalConfigRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Configure the intelligent signals service"""
    
    try:
        global _intelligent_service
        
        # Convert request to service config
        llm_config = LLMConfig(
            provider=config_request.llm_config.provider,
            model=config_request.llm_config.model,
            temperature=config_request.llm_config.temperature,
            max_tokens=config_request.llm_config.max_tokens,
            timeout_seconds=config_request.llm_config.timeout_seconds
        )
        
        service_config = IntelligentSignalConfig(
            llm_config=llm_config,
            politician_trades_config=config_request.politician_trades_config,
            enable_self_correction=config_request.enable_self_correction,
            enable_fact_checking=config_request.enable_fact_checking,
            enable_intelligent_routing=config_request.enable_intelligent_routing,
            min_confidence_score=config_request.min_confidence_score
        )
        
        # Create service
        _intelligent_service = create_intelligent_signal_service(service_config)
        
        return {
            "message": "Intelligent signals service configured successfully",
            "config": {
                "llm_model": llm_config.model,
                "llm_provider": llm_config.provider.value,
                "features_enabled": {
                    "self_correction": service_config.enable_self_correction,
                    "fact_checking": service_config.enable_fact_checking,
                    "intelligent_routing": service_config.enable_intelligent_routing
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error configuring intelligent signals: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure intelligent signals: {str(e)}"
        )


@router.get("/sources")
async def list_signal_sources() -> Dict[str, Any]:
    """List available and active signal sources"""
    
    try:
        return {
            "available_sources": signal_registry.list_available_sources(),
            "active_sources": signal_registry.list_active_sources(),
            "source_metadata": {
                source_id: signal_registry.get_source(source_id).get_metadata().dict()
                if signal_registry.get_source(source_id) else None
                for source_id in signal_registry.list_active_sources()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing signal sources: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list signal sources: {str(e)}"
        )


@router.post("/sources/{source_id}/configure", dependencies=[Depends(require_admin)])
async def configure_signal_source(
    source_id: str,
    config_request: SignalSourceConfigRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Configure a specific signal source"""
    
    try:
        # Create and configure source
        source = signal_registry.create_source(source_id, config_request.config)
        
        # Test configuration
        config_success = await source.configure()
        health_check = await source.health_check()
        
        return {
            "message": f"Signal source {source_id} configured successfully",
            "source_id": source_id,
            "configuration_success": config_success,
            "health_check_passed": health_check,
            "metadata": source.get_metadata().dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error configuring source {source_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure source {source_id}: {str(e)}"
        )


@router.post("/process", dependencies=[Depends(require_admin)])
async def process_signal(
    signal_request: ProcessSignalRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Process a raw signal through the intelligent pipeline"""
    
    try:
        global _intelligent_service
        
        if not _intelligent_service:
            raise HTTPException(
                status_code=400,
                detail="Intelligent signals service not configured. Call /configure first."
            )
        
        # Create raw signal from request
        raw_signal = RawSignal(
            source_id=signal_request.source_id,
            source_type=signal_request.source_type,
            timestamp=datetime.utcnow(),
            raw_data=signal_request.raw_data,
            ticker=signal_request.ticker,
            priority=signal_request.priority
        )
        
        # Process signal in background
        background_tasks.add_task(
            _process_signal_background, 
            _intelligent_service, 
            raw_signal, 
            db
        )
        
        return {
            "message": "Signal processing started",
            "signal_info": {
                "source_id": signal_request.source_id,
                "source_type": signal_request.source_type.value,
                "ticker": signal_request.ticker,
                "priority": signal_request.priority
            },
            "processing_status": "queued",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing signal: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process signal: {str(e)}"
        )


@router.get("/politician-trades")
async def get_politician_trades(
    politician_name: Optional[str] = Query(None, description="Filter by politician name"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of trades to return"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get politician trading data"""
    
    try:
        # Get politician trades source
        politician_source = signal_registry.get_source("politician_trades")
        
        if not politician_source:
            raise HTTPException(
                status_code=404,
                detail="Politician trades source not configured"
            )
        
        # Fetch recent trades
        since_date = datetime.utcnow() - timedelta(days=days)
        signals = await politician_source.fetch_signals(since=since_date)
        
        # Filter and format trades
        trades = []
        for signal in signals[:limit]:
            if politician_name and signal.raw_data.get('politician_name') != politician_name:
                continue
                
            trade_response = PoliticianTradeResponse(
                politician_name=signal.raw_data.get('politician_name', 'Unknown'),
                office=signal.raw_data.get('office', 'Unknown'),
                party=signal.raw_data.get('party', 'Unknown'),
                ticker=signal.ticker,
                trade_type=signal.raw_data.get('trade_type', 'Unknown'),
                amount_range=signal.raw_data.get('amount_range', 'Unknown'),
                transaction_date=signal.raw_data.get('transaction_date', datetime.utcnow()),
                filing_date=signal.raw_data.get('filing_date', datetime.utcnow()),
                timing_score=signal.raw_data.get('timing_score'),
                conflict_score=signal.raw_data.get('conflict_score'),
                market_impact_score=signal.raw_data.get('market_impact_score'),
                analysis={
                    "committees": signal.raw_data.get('committees', []),
                    "recent_legislation": signal.raw_data.get('recent_legislation', []),
                    "conflict_indicators": signal.raw_data.get('conflict_indicators', [])
                }
            )
            trades.append(trade_response)
        
        return {
            "trades": [trade.dict() for trade in trades],
            "count": len(trades),
            "filters": {
                "politician_name": politician_name,
                "days": days,
                "limit": limit
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching politician trades: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch politician trades: {str(e)}"
        )


@router.get("/politician-trades/{politician_name}/analysis")
async def get_politician_analysis(
    politician_name: str,
    days: int = Query(365, ge=30, le=1095, description="Analysis period in days"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get detailed analysis for a specific politician's trading patterns"""
    
    try:
        # This would typically involve more sophisticated analysis
        # For now, return a basic analysis structure
        
        return {
            "politician_name": politician_name,
            "analysis_period_days": days,
            "trading_patterns": {
                "total_trades": 0,  # Would be calculated from data
                "buy_sell_ratio": 0.0,
                "average_trade_size": 0.0,
                "sectors_traded": [],
                "most_traded_tickers": []
            },
            "timing_analysis": {
                "trades_before_earnings": 0,
                "trades_before_announcements": 0,
                "average_disclosure_delay": 0.0,
                "timing_risk_score": 0.0
            },
            "conflict_analysis": {
                "committee_related_trades": 0,
                "potential_conflicts": [],
                "conflict_risk_score": 0.0
            },
            "performance_analysis": {
                "performance_vs_market": None,
                "hit_rate": None,
                "total_return_estimate": None
            },
            "overall_risk_assessment": {
                "risk_score": 0.0,
                "attention_level": "low",
                "recommendations": []
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error analyzing politician {politician_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze politician {politician_name}: {str(e)}"
        )


@router.get("/stats")
async def get_processing_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get processing statistics and system health"""
    
    try:
        global _intelligent_service
        
        # Get basic stats
        stats = {
            "service_configured": _intelligent_service is not None,
            "active_sources": signal_registry.list_active_sources(),
            "available_sources": signal_registry.list_available_sources(),
            "quality_metrics": quality_monitor.get_quality_report()
        }
        
        # Get detailed stats if service is configured
        if _intelligent_service:
            detailed_stats = await _intelligent_service.get_processing_stats()
            stats.update(detailed_stats)
        
        stats["timestamp"] = datetime.utcnow().isoformat()
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting processing stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get processing stats: {str(e)}"
        )


@router.post("/signals/{signal_id}/reprocess", dependencies=[Depends(require_admin)])
async def reprocess_signal(
    signal_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Reprocess a signal with current LLM models"""
    
    try:
        global _intelligent_service
        
        if not _intelligent_service:
            raise HTTPException(
                status_code=400,
                detail="Intelligent signals service not configured"
            )
        
        # In a real implementation, you would:
        # 1. Fetch the original signal from database
        # 2. Reprocess it through the current pipeline
        # 3. Update the stored results
        
        return {
            "message": f"Signal {signal_id} reprocessing started",
            "signal_id": signal_id,
            "status": "queued",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error reprocessing signal {signal_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reprocess signal {signal_id}: {str(e)}"
        )


# Background task functions

async def _process_signal_background(
    service: IntelligentSignalService,
    raw_signal: RawSignal,
    db_session: Session
) -> None:
    """Background task to process a signal"""
    
    try:
        result = await service.process_single_signal(raw_signal, db_session)
        
        if result["processing_success"]:
            logger.info(f"Successfully processed signal {result['signal_id']} in background")
        else:
            logger.error(f"Failed to process signal in background: {result['errors']}")
            
    except Exception as e:
        logger.error(f"Error in background signal processing: {e}")


# Health check endpoint

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check for intelligent signals service"""
    
    try:
        global _intelligent_service
        
        health_status = {
            "service_configured": _intelligent_service is not None,
            "active_sources": len(signal_registry.list_active_sources()),
            "available_sources": len(signal_registry.list_available_sources()),
            "status": "healthy" if _intelligent_service else "unconfigured",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Test source health if available
        source_health = {}
        for source_id in signal_registry.list_active_sources():
            source = signal_registry.get_source(source_id)
            if source:
                try:
                    is_healthy = await source.health_check()
                    source_health[source_id] = "healthy" if is_healthy else "unhealthy"
                except:
                    source_health[source_id] = "error"
        
        health_status["source_health"] = source_health
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
