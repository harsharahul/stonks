"""
Expandable Signal Framework

Core framework for modular signal ingestion, processing, and management.
Supports diverse data sources with LLM-powered intelligent processing.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
from contextlib import asynccontextmanager

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SignalSourceType(str, Enum):
    """Types of signal sources"""
    MARKET_DATA = "market_data"
    SOCIAL_MEDIA = "social_media"
    NEWS_FEEDS = "news_feeds"
    REGULATORY = "regulatory"
    POLITICIAN_TRADES = "politician_trades"
    OPTIONS_FLOW = "options_flow"
    CRYPTO = "crypto"
    SENTIMENT = "sentiment"
    ECONOMIC = "economic"
    GEOPOLITICAL = "geopolitical"


class SignalType(str, Enum):
    """Types of signals generated"""
    PRICE_MOVEMENT = "price_movement"
    VOLUME_SPIKE = "volume_spike"
    SENTIMENT_SHIFT = "sentiment_shift"
    INSIDER_ACTIVITY = "insider_activity"
    REGULATORY_CHANGE = "regulatory_change"
    SOCIAL_MOMENTUM = "social_momentum"
    OPTIONS_ACTIVITY = "options_activity"
    POLITICAL_TRADE = "political_trade"
    NEWS_CATALYST = "news_catalyst"
    ANOMALY_DETECTION = "anomaly_detection"


class ProcessingStatus(str, Enum):
    """Signal processing status"""
    RAW = "raw"
    PROCESSING = "processing"
    VALIDATED = "validated"
    ENRICHED = "enriched"
    COMPLETED = "completed"
    FAILED = "failed"
    CORRECTED = "corrected"


@dataclass
class SignalSourceMetadata:
    """Metadata about a signal source"""
    name: str
    description: str
    source_type: SignalSourceType
    supported_signal_types: List[SignalType]
    update_frequency: timedelta
    reliability_score: float
    data_quality_score: float
    cost_per_signal: Optional[float] = None
    rate_limits: Optional[Dict[str, int]] = None
    required_config: List[str] = field(default_factory=list)


class RawSignal(BaseModel):
    """Raw signal data before processing"""
    source_id: str
    source_type: SignalSourceType
    timestamp: datetime
    raw_data: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ticker: Optional[str] = None
    priority: int = 5  # 1-10, higher is more urgent

    # Optional trading-signal hints. When a plugin sets these, the Celery
    # dispatcher persists the signal into the `signals` table; raw signals
    # without direction/strength are treated as informational and skipped.
    signal_type_hint: Optional[str] = None  # e.g. "social_momentum"
    direction: Optional[str] = None         # bullish | bearish | neutral
    strength: Optional[float] = None        # -1.0 .. 1.0
    confidence: Optional[float] = None      # 0.0 .. 1.0
    timeframe: str = "daily"                # intraday | daily | weekly


class ProcessedSignal(BaseModel):
    """Processed signal with LLM analysis"""
    id: str
    source_id: str
    signal_type: SignalType
    ticker: Optional[str]
    timestamp: datetime
    confidence_score: float
    
    # Core signal data
    title: str
    description: str
    strength: float  # 0.0-1.0
    direction: str  # bullish, bearish, neutral
    
    # LLM analysis
    llm_analysis: Optional[Dict[str, Any]] = None
    key_insights: List[str] = Field(default_factory=list)
    market_implications: List[str] = Field(default_factory=list)
    risk_assessment: Optional[Dict[str, Any]] = None
    
    # Processing metadata
    processing_status: ProcessingStatus
    processing_chain: List[str] = Field(default_factory=list)
    validation_scores: Dict[str, float] = Field(default_factory=dict)
    correction_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Related signals
    correlation_signals: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SignalSource(ABC):
    """Abstract base class for all signal sources"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
        self._last_fetch = None
        self._error_count = 0
        self._consecutive_errors = 0
        
    @abstractmethod
    def get_metadata(self) -> SignalSourceMetadata:
        """Get source metadata and capabilities"""
        pass
    
    @abstractmethod
    async def configure(self) -> bool:
        """Configure the signal source"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if source is healthy and available"""
        pass
    
    @abstractmethod
    async def fetch_signals(self, since: Optional[datetime] = None) -> List[RawSignal]:
        """Fetch new signals since timestamp"""
        pass
    
    async def validate_config(self) -> List[str]:
        """Validate configuration and return any errors"""
        errors = []
        metadata = self.get_metadata()
        
        for required_field in metadata.required_config:
            if required_field not in self.config:
                errors.append(f"Missing required config field: {required_field}")
        
        return errors
    
    def should_fetch(self) -> bool:
        """Determine if it's time to fetch new signals"""
        if not self.enabled:
            return False
            
        if self._last_fetch is None:
            return True
            
        metadata = self.get_metadata()
        return datetime.utcnow() - self._last_fetch >= metadata.update_frequency
    
    def record_error(self, error: Exception) -> None:
        """Record an error for monitoring"""
        self._error_count += 1
        self._consecutive_errors += 1
        logger.error(f"Signal source {self.__class__.__name__} error: {error}")
    
    def record_success(self) -> None:
        """Record successful operation"""
        self._consecutive_errors = 0
        self._last_fetch = datetime.utcnow()


class SignalProcessor(ABC):
    """Abstract base class for signal processors"""
    
    @abstractmethod
    async def process_signal(self, signal: RawSignal) -> ProcessedSignal:
        """Process a raw signal into processed signal"""
        pass
    
    @abstractmethod
    async def validate_signal(self, signal: ProcessedSignal) -> Dict[str, float]:
        """Validate processed signal and return validation scores"""
        pass
    
    @abstractmethod
    async def enrich_signal(self, signal: ProcessedSignal) -> ProcessedSignal:
        """Enrich signal with additional analysis"""
        pass


class SignalRegistry:
    """Registry for managing signal sources and processors"""
    
    def __init__(self):
        self._sources: Dict[str, Type[SignalSource]] = {}
        self._processors: Dict[SignalType, Type[SignalProcessor]] = {}
        self._active_sources: Dict[str, SignalSource] = {}
        
    def register_source(self, source_id: str, source_class: Type[SignalSource]) -> None:
        """Register a signal source class"""
        self._sources[source_id] = source_class
        logger.info(f"Registered signal source: {source_id}")
    
    def register_processor(self, signal_type: SignalType, processor_class: Type[SignalProcessor]) -> None:
        """Register a signal processor for a signal type"""
        self._processors[signal_type] = processor_class
        logger.info(f"Registered signal processor for: {signal_type}")
    
    def create_source(self, source_id: str, config: Dict[str, Any]) -> SignalSource:
        """Create and configure a signal source instance"""
        if source_id not in self._sources:
            raise ValueError(f"Unknown signal source: {source_id}")
        
        source_class = self._sources[source_id]
        source = source_class(config)
        
        # Validate configuration
        errors = asyncio.run(source.validate_config())
        if errors:
            raise ValueError(f"Configuration errors for {source_id}: {errors}")
        
        self._active_sources[source_id] = source
        return source
    
    def get_source(self, source_id: str) -> Optional[SignalSource]:
        """Get active source instance"""
        return self._active_sources.get(source_id)
    
    def list_available_sources(self) -> List[str]:
        """List all registered source types"""
        return list(self._sources.keys())
    
    def list_active_sources(self) -> List[str]:
        """List all active source instances"""
        return list(self._active_sources.keys())
    
    def get_processor(self, signal_type: SignalType) -> Optional[Type[SignalProcessor]]:
        """Get processor class for signal type"""
        return self._processors.get(signal_type)


class SignalOrchestrator:
    """Orchestrates signal ingestion, processing, and routing"""
    
    def __init__(self, registry: SignalRegistry, db_session: Session):
        self.registry = registry
        self.db = db_session
        self._running = False
        self._tasks = []
        
    async def start(self) -> None:
        """Start the signal orchestration process"""
        self._running = True
        logger.info("Starting signal orchestrator")
        
        # Start monitoring tasks for each active source
        for source_id in self.registry.list_active_sources():
            task = asyncio.create_task(self._monitor_source(source_id))
            self._tasks.append(task)
    
    async def stop(self) -> None:
        """Stop the signal orchestration process"""
        self._running = False
        logger.info("Stopping signal orchestrator")
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
    
    async def _monitor_source(self, source_id: str) -> None:
        """Monitor a single signal source"""
        source = self.registry.get_source(source_id)
        if not source:
            logger.error(f"Source not found: {source_id}")
            return
        
        while self._running:
            try:
                if source.should_fetch():
                    await self._fetch_and_process(source_id)
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                source.record_error(e)
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _fetch_and_process(self, source_id: str) -> None:
        """Fetch and process signals from a source"""
        source = self.registry.get_source(source_id)
        if not source:
            return
        
        try:
            # Health check
            if not await source.health_check():
                logger.warning(f"Health check failed for source: {source_id}")
                return
            
            # Fetch new signals
            raw_signals = await source.fetch_signals()
            logger.info(f"Fetched {len(raw_signals)} signals from {source_id}")
            
            # Process each signal
            for raw_signal in raw_signals:
                await self._process_single_signal(raw_signal)
            
            source.record_success()
            
        except Exception as e:
            source.record_error(e)
            logger.error(f"Error processing signals from {source_id}: {e}")
    
    async def _process_single_signal(self, raw_signal: RawSignal) -> None:
        """Process a single raw signal"""
        try:
            # Determine signal type (could be LLM-powered)
            signal_type = await self._classify_signal(raw_signal)
            
            # Get appropriate processor
            processor_class = self.registry.get_processor(signal_type)
            if not processor_class:
                logger.warning(f"No processor found for signal type: {signal_type}")
                return
            
            processor = processor_class()
            
            # Process the signal
            processed_signal = await processor.process_signal(raw_signal)
            
            # Validate the signal
            validation_scores = await processor.validate_signal(processed_signal)
            processed_signal.validation_scores = validation_scores
            
            # Enrich the signal
            enriched_signal = await processor.enrich_signal(processed_signal)
            enriched_signal.processing_status = ProcessingStatus.COMPLETED
            
            # Store the signal (implement based on your storage strategy)
            await self._store_signal(enriched_signal)
            
            # Route for further processing (alerts, notifications, etc.)
            await self._route_signal(enriched_signal)
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
    
    async def _classify_signal(self, raw_signal: RawSignal) -> SignalType:
        """Classify the raw signal to determine processing type"""
        # This could be LLM-powered classification
        # For now, use simple rules or source-based classification
        
        if raw_signal.source_type == SignalSourceType.POLITICIAN_TRADES:
            return SignalType.POLITICAL_TRADE
        elif raw_signal.source_type == SignalSourceType.SOCIAL_MEDIA:
            return SignalType.SOCIAL_MOMENTUM
        elif raw_signal.source_type == SignalSourceType.OPTIONS_FLOW:
            return SignalType.OPTIONS_ACTIVITY
        # Add more classification logic
        
        return SignalType.ANOMALY_DETECTION  # Default
    
    async def _store_signal(self, signal: ProcessedSignal) -> None:
        """Store processed signal in database"""
        # Implement signal storage logic
        pass
    
    async def _route_signal(self, signal: ProcessedSignal) -> None:
        """Route signal for alerts, notifications, etc."""
        # Implement routing logic based on signal properties
        pass


# Global registry instance
signal_registry = SignalRegistry()


def register_signal_source(source_id: str, *, default_enabled: bool = True):
    """Class decorator: register a SignalSource plugin under ``source_id``.

    ``default_enabled`` seeds the admin toggle for deployments that have
    never seen this source (mock/experimental sources should pass False).
    Contributors: decorate your SignalSource subclass with this, see
    CONTRIBUTING-SIGNALS.md for the full plugin contract.
    """
    def _wrap(cls):
        cls.source_id = source_id
        cls.default_enabled = default_enabled
        signal_registry.register_source(source_id, cls)
        return cls
    return _wrap


@asynccontextmanager
async def signal_orchestrator_context(db_session: Session):
    """Context manager for signal orchestrator"""
    orchestrator = SignalOrchestrator(signal_registry, db_session)
    try:
        await orchestrator.start()
        yield orchestrator
    finally:
        await orchestrator.stop()


# Utility functions for signal management
def register_default_sources():
    """Import the plugins package so @register_signal_source decorators run."""
    import app.signals  # noqa: F401  (importing registers every bundled plugin)


def initialize_signal_framework():
    """Initialize the signal framework"""
    logger.info("Initializing signal framework")
    register_default_sources()
    logger.info("Signal framework initialized")


# Quality monitoring
class SignalQualityMonitor:
    """Monitor signal quality and performance"""
    
    def __init__(self):
        self.quality_metrics = {}
        self.performance_metrics = {}
    
    def record_signal_quality(self, source_id: str, quality_score: float) -> None:
        """Record quality score for a signal source"""
        if source_id not in self.quality_metrics:
            self.quality_metrics[source_id] = []
        
        self.quality_metrics[source_id].append({
            'timestamp': datetime.utcnow(),
            'quality_score': quality_score
        })
    
    def record_processing_time(self, signal_type: SignalType, processing_time_ms: int) -> None:
        """Record processing time for signal type"""
        if signal_type not in self.performance_metrics:
            self.performance_metrics[signal_type] = []
        
        self.performance_metrics[signal_type].append({
            'timestamp': datetime.utcnow(),
            'processing_time_ms': processing_time_ms
        })
    
    def get_quality_report(self) -> Dict[str, Any]:
        """Generate quality report"""
        return {
            'quality_metrics': self.quality_metrics,
            'performance_metrics': self.performance_metrics,
            'generated_at': datetime.utcnow()
        }


# Global quality monitor
quality_monitor = SignalQualityMonitor()
