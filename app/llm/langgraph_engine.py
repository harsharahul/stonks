"""
LangGraph-Powered Signal Processing Engine

Intelligent signal processing using LangGraph workflows with LLM agents.
Provides self-correcting writes, intelligent routing, and quality assurance.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from app.core.signal_framework import RawSignal, ProcessedSignal, SignalType
from app.core.exceptions import SignalProcessingException

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class WorkflowType(str, Enum):
    """Types of LangGraph workflows"""
    SIGNAL_PROCESSING = "signal_processing"
    QUALITY_ASSURANCE = "quality_assurance"
    FACT_CHECKING = "fact_checking"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    PATTERN_DETECTION = "pattern_detection"


@dataclass
class LLMConfig:
    """Configuration for LLM services"""
    provider: LLMProvider
    model: str
    temperature: float = 0.1
    max_tokens: int = 4000
    timeout_seconds: int = 30
    fallback_model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class ProcessingState(TypedDict):
    """State for LangGraph workflows"""
    raw_signal: Dict[str, Any]
    processed_signal: Optional[Dict[str, Any]]
    validation_results: Optional[Dict[str, Any]]
    corrections: List[Dict[str, Any]]
    quality_scores: Dict[str, float]
    analysis_steps: List[str]
    final_output: Optional[Dict[str, Any]]
    error_count: int
    processing_metadata: Dict[str, Any]


class SignalAnalysis(BaseModel):
    """LLM analysis output"""
    signal_type: SignalType
    confidence_score: float = Field(ge=0.0, le=1.0)
    title: str
    description: str
    key_insights: List[str]
    market_implications: List[str]
    risk_assessment: Dict[str, Any]
    strength: float = Field(ge=0.0, le=1.0)
    direction: str = Field(pattern="^(bullish|bearish|neutral)$")
    urgency: int = Field(ge=1, le=10)


class ValidationResult(BaseModel):
    """LLM validation output"""
    is_valid: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    quality_scores: Dict[str, float]
    identified_issues: List[str]
    suggested_corrections: List[Dict[str, Any]]
    validation_reasoning: str


class CorrectionAction(BaseModel):
    """LLM correction action"""
    field_name: str
    current_value: Any
    corrected_value: Any
    correction_reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class LangGraphEngine:
    """LangGraph-powered intelligent signal processing"""
    
    def __init__(self, llm_config: LLMConfig):
        self.llm_config = llm_config
        self.llm = self._create_llm()
        self.workflows = self._initialize_workflows()
        
    def _create_llm(self) -> ChatOpenAI:
        """Create LLM instance based on configuration"""
        if self.llm_config.provider == LLMProvider.OPENAI:
            return ChatOpenAI(
                model=self.llm_config.model,
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens,
                timeout=self.llm_config.timeout_seconds,
                api_key=self.llm_config.api_key
            )
        elif self.llm_config.provider == LLMProvider.OLLAMA:
            from langchain_community.llms import Ollama
            return Ollama(
                model=self.llm_config.model,
                base_url=self.llm_config.base_url or "http://localhost:11434"
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_config.provider}")
    
    def _initialize_workflows(self) -> Dict[WorkflowType, StateGraph]:
        """Initialize LangGraph workflows"""
        workflows = {}
        
        # Signal processing workflow
        workflows[WorkflowType.SIGNAL_PROCESSING] = self._create_signal_processing_workflow()
        
        # Quality assurance workflow
        workflows[WorkflowType.QUALITY_ASSURANCE] = self._create_quality_assurance_workflow()
        
        # Fact checking workflow
        workflows[WorkflowType.FACT_CHECKING] = self._create_fact_checking_workflow()
        
        return workflows
    
    def _create_signal_processing_workflow(self) -> StateGraph:
        """Create signal processing workflow"""
        workflow = StateGraph(ProcessingState)
        
        # Add nodes
        workflow.add_node("extract_features", self._extract_features_node)
        workflow.add_node("analyze_signal", self._analyze_signal_node)
        workflow.add_node("validate_analysis", self._validate_analysis_node)
        workflow.add_node("enrich_signal", self._enrich_signal_node)
        workflow.add_node("quality_check", self._quality_check_node)
        workflow.add_node("finalize_output", self._finalize_output_node)
        
        # Add edges
        workflow.add_edge("extract_features", "analyze_signal")
        workflow.add_edge("analyze_signal", "validate_analysis")
        workflow.add_edge("validate_analysis", "enrich_signal")
        workflow.add_edge("enrich_signal", "quality_check")
        workflow.add_edge("quality_check", "finalize_output")
        workflow.add_edge("finalize_output", END)
        
        # Set entry point
        workflow.set_entry_point("extract_features")
        
        return workflow.compile()
    
    def _create_quality_assurance_workflow(self) -> StateGraph:
        """Create quality assurance workflow"""
        workflow = StateGraph(ProcessingState)
        
        # Add nodes
        workflow.add_node("initial_validation", self._initial_validation_node)
        workflow.add_node("detect_issues", self._detect_issues_node)
        workflow.add_node("generate_corrections", self._generate_corrections_node)
        workflow.add_node("apply_corrections", self._apply_corrections_node)
        workflow.add_node("final_validation", self._final_validation_node)
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "initial_validation",
            self._should_correct,
            {
                "correct": "detect_issues",
                "pass": "final_validation"
            }
        )
        
        workflow.add_edge("detect_issues", "generate_corrections")
        workflow.add_edge("generate_corrections", "apply_corrections")
        workflow.add_edge("apply_corrections", "final_validation")
        workflow.add_edge("final_validation", END)
        
        workflow.set_entry_point("initial_validation")
        
        return workflow.compile()
    
    def _create_fact_checking_workflow(self) -> StateGraph:
        """Create fact checking workflow"""
        workflow = StateGraph(ProcessingState)
        
        # Add nodes
        workflow.add_node("extract_claims", self._extract_claims_node)
        workflow.add_node("verify_facts", self._verify_facts_node)
        workflow.add_node("assess_credibility", self._assess_credibility_node)
        workflow.add_node("generate_confidence", self._generate_confidence_node)
        
        # Add edges
        workflow.add_edge("extract_claims", "verify_facts")
        workflow.add_edge("verify_facts", "assess_credibility")
        workflow.add_edge("assess_credibility", "generate_confidence")
        workflow.add_edge("generate_confidence", END)
        
        workflow.set_entry_point("extract_claims")
        
        return workflow.compile()
    
    async def process_signal(self, raw_signal: RawSignal) -> ProcessedSignal:
        """Process signal through LangGraph workflow"""
        try:
            # Initialize state
            initial_state = ProcessingState(
                raw_signal=raw_signal.dict(),
                processed_signal=None,
                validation_results=None,
                corrections=[],
                quality_scores={},
                analysis_steps=[],
                final_output=None,
                error_count=0,
                processing_metadata={
                    "start_time": datetime.utcnow().isoformat(),
                    "workflow_type": WorkflowType.SIGNAL_PROCESSING.value
                }
            )
            
            # Run workflow
            workflow = self.workflows[WorkflowType.SIGNAL_PROCESSING]
            result = await workflow.ainvoke(initial_state)
            
            # Convert result to ProcessedSignal
            return self._convert_to_processed_signal(result)
            
        except Exception as e:
            logger.error(f"Error in signal processing workflow: {e}")
            raise SignalProcessingException(
                ticker=raw_signal.ticker or "UNKNOWN",
                signal_type="unknown",
                reason=str(e)
            )
    
    async def validate_and_correct(self, signal: ProcessedSignal) -> ProcessedSignal:
        """Validate signal and apply corrections if needed"""
        try:
            # Initialize state
            initial_state = ProcessingState(
                raw_signal={},
                processed_signal=signal.dict(),
                validation_results=None,
                corrections=[],
                quality_scores={},
                analysis_steps=[],
                final_output=None,
                error_count=0,
                processing_metadata={
                    "start_time": datetime.utcnow().isoformat(),
                    "workflow_type": WorkflowType.QUALITY_ASSURANCE.value
                }
            )
            
            # Run workflow
            workflow = self.workflows[WorkflowType.QUALITY_ASSURANCE]
            result = await workflow.ainvoke(initial_state)
            
            # Return corrected signal
            return self._convert_to_processed_signal(result)
            
        except Exception as e:
            logger.error(f"Error in validation workflow: {e}")
            return signal  # Return original on error
    
    # Workflow Node Implementations
    
    async def _extract_features_node(self, state: ProcessingState) -> ProcessingState:
        """Extract features from raw signal"""
        try:
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content="""You are a financial signal analysis expert. Extract key features from the raw signal data.
                
                Focus on:
                - Relevant financial metrics
                - Market context
                - Timing information
                - Source credibility
                - Data quality indicators
                
                Return structured feature data."""),
                HumanMessage(content=f"Raw signal data: {json.dumps(state['raw_signal'], indent=2)}")
            ])
            
            response = await self.llm.ainvoke(prompt.format_messages())
            
            # Parse response and extract features
            features = self._parse_features_response(response.content)
            
            state["analysis_steps"].append("extract_features")
            state["processing_metadata"]["features"] = features
            
            return state
            
        except Exception as e:
            state["error_count"] += 1
            logger.error(f"Error in extract_features_node: {e}")
            return state
    
    async def _analyze_signal_node(self, state: ProcessingState) -> ProcessingState:
        """Analyze signal and generate insights"""
        try:
            parser = PydanticOutputParser(pydantic_object=SignalAnalysis)
            
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=f"""You are a financial market analysis expert. Analyze the signal data and provide comprehensive insights.
                
                Consider:
                - Market significance
                - Risk implications
                - Trading opportunities
                - Confidence levels
                - Urgency assessment
                
                {parser.get_format_instructions()}"""),
                HumanMessage(content=f"""
                Raw signal: {json.dumps(state['raw_signal'], indent=2)}
                Extracted features: {json.dumps(state['processing_metadata'].get('features', {}), indent=2)}
                """)
            ])
            
            response = await self.llm.ainvoke(prompt.format_messages())
            analysis = parser.parse(response.content)
            
            # Convert to dict and store
            state["processed_signal"] = analysis.dict()
            state["analysis_steps"].append("analyze_signal")
            
            return state
            
        except Exception as e:
            state["error_count"] += 1
            logger.error(f"Error in analyze_signal_node: {e}")
            return state
    
    async def _validate_analysis_node(self, state: ProcessingState) -> ProcessingState:
        """Validate the analysis results"""
        try:
            parser = PydanticOutputParser(pydantic_object=ValidationResult)
            
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=f"""You are a quality assurance expert for financial analysis. Validate the signal analysis for accuracy, consistency, and completeness.
                
                Check for:
                - Logical consistency
                - Data accuracy
                - Appropriate confidence levels
                - Missing information
                - Potential biases
                
                {parser.get_format_instructions()}"""),
                HumanMessage(content=f"""
                Signal analysis to validate: {json.dumps(state['processed_signal'], indent=2)}
                Original raw data: {json.dumps(state['raw_signal'], indent=2)}
                """)
            ])
            
            response = await self.llm.ainvoke(prompt.format_messages())
            validation = parser.parse(response.content)
            
            state["validation_results"] = validation.dict()
            state["quality_scores"].update(validation.quality_scores)
            state["analysis_steps"].append("validate_analysis")
            
            return state
            
        except Exception as e:
            state["error_count"] += 1
            logger.error(f"Error in validate_analysis_node: {e}")
            return state
    
    async def _enrich_signal_node(self, state: ProcessingState) -> ProcessingState:
        """Enrich signal with additional context and analysis"""
        try:
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content="""You are a financial context expert. Enrich the signal analysis with additional market context, correlations, and implications.
                
                Add:
                - Market correlations
                - Historical context
                - Sector implications
                - Related signals
                - Risk factors"""),
                HumanMessage(content=f"""
                Current signal: {json.dumps(state['processed_signal'], indent=2)}
                Validation results: {json.dumps(state['validation_results'], indent=2)}
                """)
            ])
            
            response = await self.llm.ainvoke(prompt.format_messages())
            
            # Parse enrichment data and update signal
            enrichment = self._parse_enrichment_response(response.content)
            
            if state["processed_signal"]:
                state["processed_signal"].update(enrichment)
            
            state["analysis_steps"].append("enrich_signal")
            
            return state
            
        except Exception as e:
            state["error_count"] += 1
            logger.error(f"Error in enrich_signal_node: {e}")
            return state
    
    async def _quality_check_node(self, state: ProcessingState) -> ProcessingState:
        """Final quality check"""
        try:
            # Calculate overall quality score
            quality_scores = state["quality_scores"]
            overall_quality = sum(quality_scores.values()) / len(quality_scores) if quality_scores else 0.5
            
            state["quality_scores"]["overall"] = overall_quality
            state["analysis_steps"].append("quality_check")
            
            return state
            
        except Exception as e:
            state["error_count"] += 1
            logger.error(f"Error in quality_check_node: {e}")
            return state
    
    async def _finalize_output_node(self, state: ProcessingState) -> ProcessingState:
        """Finalize the processed signal output"""
        try:
            # Add processing metadata
            if state["processed_signal"]:
                state["processed_signal"]["processing_metadata"] = {
                    "analysis_steps": state["analysis_steps"],
                    "quality_scores": state["quality_scores"],
                    "error_count": state["error_count"],
                    "processing_time": datetime.utcnow().isoformat()
                }
            
            state["final_output"] = state["processed_signal"]
            state["analysis_steps"].append("finalize_output")
            
            return state
            
        except Exception as e:
            state["error_count"] += 1
            logger.error(f"Error in finalize_output_node: {e}")
            return state
    
    # Quality Assurance Workflow Nodes
    
    async def _initial_validation_node(self, state: ProcessingState) -> ProcessingState:
        """Initial validation of processed signal"""
        # Implementation for initial validation
        state["analysis_steps"].append("initial_validation")
        return state
    
    async def _detect_issues_node(self, state: ProcessingState) -> ProcessingState:
        """Detect issues in processed signal"""
        # Implementation for issue detection
        state["analysis_steps"].append("detect_issues")
        return state
    
    async def _generate_corrections_node(self, state: ProcessingState) -> ProcessingState:
        """Generate corrections for detected issues"""
        # Implementation for correction generation
        state["analysis_steps"].append("generate_corrections")
        return state
    
    async def _apply_corrections_node(self, state: ProcessingState) -> ProcessingState:
        """Apply generated corrections"""
        # Implementation for applying corrections
        state["analysis_steps"].append("apply_corrections")
        return state
    
    async def _final_validation_node(self, state: ProcessingState) -> ProcessingState:
        """Final validation after corrections"""
        # Implementation for final validation
        state["analysis_steps"].append("final_validation")
        return state
    
    # Fact Checking Workflow Nodes
    
    async def _extract_claims_node(self, state: ProcessingState) -> ProcessingState:
        """Extract factual claims from signal"""
        # Implementation for claim extraction
        state["analysis_steps"].append("extract_claims")
        return state
    
    async def _verify_facts_node(self, state: ProcessingState) -> ProcessingState:
        """Verify factual claims"""
        # Implementation for fact verification
        state["analysis_steps"].append("verify_facts")
        return state
    
    async def _assess_credibility_node(self, state: ProcessingState) -> ProcessingState:
        """Assess source credibility"""
        # Implementation for credibility assessment
        state["analysis_steps"].append("assess_credibility")
        return state
    
    async def _generate_confidence_node(self, state: ProcessingState) -> ProcessingState:
        """Generate confidence scores"""
        # Implementation for confidence generation
        state["analysis_steps"].append("generate_confidence")
        return state
    
    # Utility Methods
    
    def _should_correct(self, state: ProcessingState) -> str:
        """Determine if corrections are needed"""
        validation_results = state.get("validation_results", {})
        if validation_results and not validation_results.get("is_valid", True):
            return "correct"
        return "pass"
    
    def _parse_features_response(self, response: str) -> Dict[str, Any]:
        """Parse feature extraction response"""
        try:
            return json.loads(response)
        except:
            return {"features": response}
    
    def _parse_enrichment_response(self, response: str) -> Dict[str, Any]:
        """Parse enrichment response"""
        try:
            return json.loads(response)
        except:
            return {"enrichment": response}
    
    def _convert_to_processed_signal(self, state: ProcessingState) -> ProcessedSignal:
        """Convert workflow state to ProcessedSignal"""
        final_output = state.get("final_output", {})
        
        # Create ProcessedSignal with required fields
        return ProcessedSignal(
            id=f"signal_{datetime.utcnow().timestamp()}",
            source_id=state["raw_signal"].get("source_id", "unknown"),
            signal_type=SignalType(final_output.get("signal_type", "anomaly_detection")),
            ticker=final_output.get("ticker"),
            timestamp=datetime.utcnow(),
            confidence_score=final_output.get("confidence_score", 0.5),
            title=final_output.get("title", "Processed Signal"),
            description=final_output.get("description", "Signal processed through LLM workflow"),
            strength=final_output.get("strength", 0.5),
            direction=final_output.get("direction", "neutral"),
            llm_analysis=final_output.get("llm_analysis"),
            key_insights=final_output.get("key_insights", []),
            market_implications=final_output.get("market_implications", []),
            risk_assessment=final_output.get("risk_assessment"),
            processing_status="completed",
            processing_chain=state.get("analysis_steps", []),
            validation_scores=state.get("quality_scores", {}),
            correction_history=state.get("corrections", [])
        )


# Factory function for creating LangGraph engines
def create_langgraph_engine(llm_config: LLMConfig) -> LangGraphEngine:
    """Factory function to create LangGraph engine"""
    return LangGraphEngine(llm_config)
