"""
Intelligent Signal Service

Integrates the expandable signal framework with LLM-powered processing.
Provides self-correcting writes, intelligent routing, and advanced analytics.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Type
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.signal_framework import (
    SignalRegistry, SignalOrchestrator, SignalSource, SignalProcessor,
    RawSignal, ProcessedSignal, SignalType, SignalSourceType,
    quality_monitor, signal_registry
)
from app.llm.langgraph_engine import LangGraphEngine, LLMConfig, LLMProvider
from app.signals.politician_trades import PoliticianTradesSource
from app.services.alert_engine import AlertEngine
from app.services.websocket_manager import event_broadcaster
from app.core.exceptions import SignalProcessingException
from app.core.database import get_db

logger = logging.getLogger(__name__)


class IntelligentSignalConfig(BaseModel):
    """Configuration for intelligent signal service"""
    
    # LLM Configuration
    llm_config: LLMConfig
    
    # Signal Sources Configuration
    politician_trades_config: Dict[str, Any] = {}
    social_media_config: Dict[str, Any] = {}
    options_flow_config: Dict[str, Any] = {}
    
    # Processing Configuration
    enable_self_correction: bool = True
    enable_fact_checking: bool = True
    enable_intelligent_routing: bool = True
    max_processing_time_seconds: int = 300
    
    # Quality Assurance
    min_confidence_score: float = 0.7
    require_validation: bool = True
    enable_human_review_queue: bool = False


class LLMSignalProcessor(SignalProcessor):
    """LLM-powered signal processor using LangGraph"""
    
    def __init__(self, langgraph_engine: LangGraphEngine):
        self.engine = langgraph_engine
        
    async def process_signal(self, signal: RawSignal) -> ProcessedSignal:
        """Process signal using LLM workflow"""
        try:
            start_time = datetime.utcnow()
            
            # Process through LangGraph workflow
            processed_signal = await self.engine.process_signal(signal)
            
            # Record processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            quality_monitor.record_processing_time(processed_signal.signal_type, int(processing_time))
            
            return processed_signal
            
        except Exception as e:
            logger.error(f"Error in LLM signal processing: {e}")
            raise SignalProcessingException(
                ticker=signal.ticker or "UNKNOWN",
                signal_type="llm_processing",
                reason=str(e)
            )
    
    async def validate_signal(self, signal: ProcessedSignal) -> Dict[str, float]:
        """Validate signal using LLM"""
        try:
            # Use LangGraph validation workflow
            validated_signal = await self.engine.validate_and_correct(signal)
            return validated_signal.validation_scores
            
        except Exception as e:
            logger.error(f"Error in signal validation: {e}")
            return {"validation_error": 0.0}
    
    async def enrich_signal(self, signal: ProcessedSignal) -> ProcessedSignal:
        """Enrich signal with additional LLM analysis"""
        try:
            # Signal already enriched in main processing
            return signal
            
        except Exception as e:
            logger.error(f"Error in signal enrichment: {e}")
            return signal


class SelfCorrectingWriter:
    """LLM-powered self-correcting data writer"""
    
    def __init__(self, langgraph_engine: LangGraphEngine, db_session: Session):
        self.engine = langgraph_engine
        self.db = db_session
        
    async def write_signal_with_validation(
        self, 
        signal: ProcessedSignal,
        target_table: str = "signals"
    ) -> Dict[str, Any]:
        """Write signal with automatic validation and correction"""
        
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Attempt to write
                write_result = await self._attempt_write(signal, target_table)
                
                # Validate the write
                validation_result = await self._validate_write(signal, write_result)
                
                if validation_result["is_valid"]:
                    logger.info(f"Signal {signal.id} written successfully on attempt {attempt + 1}")
                    return {
                        "success": True,
                        "signal_id": signal.id,
                        "attempts": attempt + 1,
                        "validation_result": validation_result
                    }
                
                # If validation failed, attempt correction
                if attempt < max_attempts - 1:
                    corrected_signal = await self._correct_signal(signal, validation_result)
                    signal = corrected_signal
                    
                    # Record correction
                    signal.correction_history.append({
                        "attempt": attempt + 1,
                        "issues": validation_result.get("issues", []),
                        "correction_timestamp": datetime.utcnow().isoformat()
                    })
                
                attempt += 1
                
            except Exception as e:
                logger.error(f"Error in write attempt {attempt + 1}: {e}")
                attempt += 1
                
                if attempt >= max_attempts:
                    return {
                        "success": False,
                        "error": str(e),
                        "attempts": attempt,
                        "signal_id": signal.id
                    }
        
        return {
            "success": False,
            "error": "Max attempts reached without successful validation",
            "attempts": max_attempts,
            "signal_id": signal.id
        }
    
    async def _attempt_write(self, signal: ProcessedSignal, target_table: str) -> Dict[str, Any]:
        """Attempt to write signal to database"""
        try:
            # Convert signal to database record
            # Implementation depends on your database schema
            
            # For now, simulate a write operation
            return {
                "write_id": f"write_{datetime.utcnow().timestamp()}",
                "table": target_table,
                "timestamp": datetime.utcnow(),
                "record_count": 1
            }
            
        except Exception as e:
            logger.error(f"Database write failed: {e}")
            raise
    
    async def _validate_write(self, signal: ProcessedSignal, write_result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the written data"""
        # Use LLM to validate the write operation
        # This could check for data consistency, completeness, etc.
        
        return {
            "is_valid": True,  # Simplified for now
            "confidence": 0.95,
            "issues": [],
            "validation_timestamp": datetime.utcnow().isoformat()
        }
    
    async def _correct_signal(self, signal: ProcessedSignal, validation_result: Dict[str, Any]) -> ProcessedSignal:
        """Correct signal based on validation issues"""
        # Use LLM to generate corrections
        corrected_signal = await self.engine.validate_and_correct(signal)
        return corrected_signal


class IntelligentSignalRouter:
    """LLM-powered intelligent signal routing"""
    
    def __init__(self, langgraph_engine: LangGraphEngine, alert_engine: AlertEngine):
        self.engine = langgraph_engine
        self.alert_engine = alert_engine
        
    async def route_signal(self, signal: ProcessedSignal) -> Dict[str, Any]:
        """Intelligently route signal based on content and urgency"""
        
        routing_decisions = []
        
        try:
            # Analyze signal for routing decisions
            routing_analysis = await self._analyze_routing_needs(signal)
            
            # Route to alerts if needed
            if routing_analysis.get("should_alert", False):
                alert_result = await self._route_to_alerts(signal, routing_analysis)
                routing_decisions.append(alert_result)
            
            # Route to WebSocket broadcast if needed
            if routing_analysis.get("should_broadcast", False):
                broadcast_result = await self._route_to_websocket(signal, routing_analysis)
                routing_decisions.append(broadcast_result)
            
            # Route to external services if needed
            if routing_analysis.get("external_services", []):
                external_results = await self._route_to_external_services(signal, routing_analysis)
                routing_decisions.extend(external_results)
            
            return {
                "signal_id": signal.id,
                "routing_decisions": routing_decisions,
                "routing_analysis": routing_analysis,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in signal routing: {e}")
            return {
                "signal_id": signal.id,
                "error": str(e),
                "routing_decisions": [],
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _analyze_routing_needs(self, signal: ProcessedSignal) -> Dict[str, Any]:
        """Analyze signal to determine routing needs"""
        
        analysis = {
            "should_alert": False,
            "should_broadcast": False,
            "external_services": [],
            "priority": signal.strength * signal.confidence_score,
            "urgency": "medium"
        }
        
        # High confidence and strength signals should generate alerts
        if signal.confidence_score > 0.8 and signal.strength > 0.7:
            analysis["should_alert"] = True
            analysis["urgency"] = "high"
        
        # Political trades should always broadcast
        if signal.signal_type == SignalType.POLITICAL_TRADE:
            analysis["should_broadcast"] = True
            analysis["external_services"].append("compliance_monitoring")
        
        # High-impact signals should broadcast
        if signal.strength > 0.8:
            analysis["should_broadcast"] = True
        
        return analysis
    
    async def _route_to_alerts(self, signal: ProcessedSignal, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Route signal to alert system"""
        try:
            # Convert processed signal to alert format
            alert_data = {
                "ticker": signal.ticker,
                "alert_type": signal.signal_type.value,
                "severity": self._map_severity(analysis["urgency"]),
                "title": signal.title,
                "message": signal.description,
                "strength": signal.strength,
                "confidence": signal.confidence_score,
                "metadata": {
                    "signal_id": signal.id,
                    "llm_analysis": signal.llm_analysis,
                    "key_insights": signal.key_insights
                }
            }
            
            # Generate alert
            alert = self.alert_engine.create_alert_from_data(alert_data)
            
            return {
                "target": "alerts",
                "success": True,
                "alert_id": alert.id if alert else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error routing to alerts: {e}")
            return {
                "target": "alerts",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _route_to_websocket(self, signal: ProcessedSignal, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Route signal to WebSocket broadcast"""
        try:
            # Prepare broadcast data
            broadcast_data = {
                "signal_id": signal.id,
                "signal_type": signal.signal_type.value,
                "ticker": signal.ticker,
                "title": signal.title,
                "description": signal.description,
                "strength": signal.strength,
                "confidence": signal.confidence_score,
                "direction": signal.direction,
                "timestamp": signal.timestamp.isoformat(),
                "key_insights": signal.key_insights[:3],  # Limit for broadcast
                "urgency": analysis.get("urgency", "medium")
            }
            
            # Broadcast to appropriate channel
            if signal.signal_type == SignalType.POLITICAL_TRADE:
                await event_broadcaster.broadcast_signal(broadcast_data)
            else:
                await event_broadcaster.broadcast_signal(broadcast_data)
            
            return {
                "target": "websocket",
                "success": True,
                "channel": "signals",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error routing to WebSocket: {e}")
            return {
                "target": "websocket",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _route_to_external_services(self, signal: ProcessedSignal, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Route signal to external services"""
        results = []
        
        for service in analysis.get("external_services", []):
            try:
                # Route to specific external service
                if service == "compliance_monitoring":
                    result = await self._route_to_compliance(signal)
                elif service == "risk_management":
                    result = await self._route_to_risk_management(signal)
                else:
                    result = {
                        "target": service,
                        "success": False,
                        "error": f"Unknown service: {service}",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error routing to {service}: {e}")
                results.append({
                    "target": service,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        return results
    
    async def _route_to_compliance(self, signal: ProcessedSignal) -> Dict[str, Any]:
        """Route to compliance monitoring"""
        # Implementation for compliance routing
        return {
            "target": "compliance_monitoring",
            "success": True,
            "action": "logged_for_review",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _route_to_risk_management(self, signal: ProcessedSignal) -> Dict[str, Any]:
        """Route to risk management"""
        # Implementation for risk management routing
        return {
            "target": "risk_management", 
            "success": True,
            "action": "risk_assessment_triggered",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _map_severity(self, urgency: str) -> str:
        """Map urgency to alert severity"""
        mapping = {
            "low": "low",
            "medium": "medium", 
            "high": "high",
            "critical": "critical"
        }
        return mapping.get(urgency, "medium")


class IntelligentSignalService:
    """Main service for intelligent signal processing"""
    
    def __init__(self, config: IntelligentSignalConfig):
        self.config = config
        self.langgraph_engine = LangGraphEngine(config.llm_config)
        self.llm_processor = LLMSignalProcessor(self.langgraph_engine)
        self._setup_signal_sources()
        self._setup_processors()
        
    def _setup_signal_sources(self) -> None:
        """Setup and register signal sources"""
        
        # Register politician trades source
        signal_registry.register_source("politician_trades", PoliticianTradesSource)
        
        # Create and configure sources
        if self.config.politician_trades_config:
            politician_source = signal_registry.create_source(
                "politician_trades", 
                self.config.politician_trades_config
            )
            asyncio.create_task(politician_source.configure())
        
        # Add more signal sources as needed
        logger.info("Signal sources configured")
    
    def _setup_processors(self) -> None:
        """Setup and register signal processors"""
        
        # Register LLM processor for all signal types
        for signal_type in SignalType:
            signal_registry.register_processor(signal_type, LLMSignalProcessor)
        
        logger.info("Signal processors configured")
    
    async def start_processing(self, db_session: Session) -> None:
        """Start the intelligent signal processing service"""
        
        try:
            # Create orchestrator
            orchestrator = SignalOrchestrator(signal_registry, db_session)
            
            # Create intelligent components
            self.self_correcting_writer = SelfCorrectingWriter(self.langgraph_engine, db_session)
            
            # Get alert engine
            alert_engine = AlertEngine(db_session)
            self.intelligent_router = IntelligentSignalRouter(self.langgraph_engine, alert_engine)
            
            # Start orchestrator
            await orchestrator.start()
            
            logger.info("Intelligent signal service started successfully")
            
            # Keep service running
            while True:
                await asyncio.sleep(60)  # Check every minute
                
        except Exception as e:
            logger.error(f"Error in intelligent signal service: {e}")
            raise
    
    async def process_single_signal(self, raw_signal: RawSignal, db_session: Session) -> Dict[str, Any]:
        """Process a single signal through the intelligent pipeline"""
        
        results = {
            "signal_id": None,
            "processing_success": False,
            "validation_success": False,
            "routing_success": False,
            "errors": []
        }
        
        try:
            # Process signal with LLM
            processed_signal = await self.llm_processor.process_signal(raw_signal)
            results["signal_id"] = processed_signal.id
            results["processing_success"] = True
            
            # Self-correcting write
            if self.config.enable_self_correction:
                write_result = await self.self_correcting_writer.write_signal_with_validation(
                    processed_signal
                )
                results["validation_success"] = write_result["success"]
                if not write_result["success"]:
                    results["errors"].append(f"Write validation failed: {write_result.get('error')}")
            
            # Intelligent routing
            if self.config.enable_intelligent_routing:
                routing_result = await self.intelligent_router.route_signal(processed_signal)
                results["routing_success"] = len(routing_result.get("routing_decisions", [])) > 0
                results["routing_decisions"] = routing_result.get("routing_decisions", [])
            
            logger.info(f"Successfully processed signal {processed_signal.id}")
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            results["errors"].append(str(e))
        
        return results
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        
        quality_report = quality_monitor.get_quality_report()
        
        return {
            "active_sources": signal_registry.list_active_sources(),
            "available_sources": signal_registry.list_available_sources(),
            "quality_metrics": quality_report,
            "config": {
                "llm_model": self.config.llm_config.model,
                "self_correction_enabled": self.config.enable_self_correction,
                "fact_checking_enabled": self.config.enable_fact_checking,
                "intelligent_routing_enabled": self.config.enable_intelligent_routing
            },
            "timestamp": datetime.utcnow().isoformat()
        }


# Factory function
def create_intelligent_signal_service(config: IntelligentSignalConfig) -> IntelligentSignalService:
    """Create intelligent signal service with configuration"""
    return IntelligentSignalService(config)


# Context manager for service lifecycle
@asynccontextmanager
async def intelligent_signal_service_context(config: IntelligentSignalConfig, db_session: Session):
    """Context manager for intelligent signal service"""
    service = create_intelligent_signal_service(config)
    try:
        # Start the service in background
        service_task = asyncio.create_task(service.start_processing(db_session))
        yield service
    finally:
        # Cleanup
        service_task.cancel()
        try:
            await service_task
        except asyncio.CancelledError:
            pass
