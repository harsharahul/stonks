"""
LangGraph-based Analytics Agent for Stonks
Enhances deterministic features with LLM-powered insights and synthesis
"""
from typing import Dict, List, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json
import os

# Initialize LLM with fallback to Ollama
def get_llm():
    """Get LLM instance with fallback to Ollama if OpenAI not available"""
    try:
        # Try OpenAI first
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key != "your_openai_api_key_here":
            return ChatOpenAI(
                model="gpt-4o-mini",  # Cost-effective for production
                temperature=0.1,  # Low temperature for consistent financial analysis
                max_tokens=1000
            )
        
        # Fallback to Ollama
        try:
            import ollama
            # Test if Ollama is running
            available_models = ollama.list()
            
            # Prefer smaller, faster models for financial analysis
            preferred_models = ["llama3.1:latest", "qwen3:30b", "gpt-oss:20b"]
            selected_model = None
            
            for model_name in preferred_models:
                if any(model['name'] == model_name for model in available_models['models']):
                    selected_model = model_name
                    break
            
            if selected_model:
                print(f"Using Ollama model: {selected_model}")
                return OllamaLLM(model=selected_model)
            else:
                # Use first available model
                first_model = available_models['models'][0]['name']
                print(f"Using available Ollama model: {first_model}")
                return OllamaLLM(model=first_model)
                
        except Exception as e:
            print(f"Ollama fallback failed: {e}")
            return None
            
    except Exception as e:
        print(f"LLM initialization error: {e}")
        return None

# Ollama LLM wrapper for LangChain compatibility
class OllamaLLM:
    """Wrapper for Ollama to make it compatible with LangChain"""
    
    def __init__(self, model: str = "llama3.2:3b", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature
        self.client = None
        try:
            import ollama
            self.client = ollama
        except ImportError:
            raise ImportError("Ollama package not available")
    
    def invoke(self, messages):
        """Invoke Ollama with messages"""
        try:
            # Convert LangChain messages to Ollama format
            prompt = self._format_messages_for_ollama(messages)
            
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": self.temperature,
                    "num_predict": 1000
                }
            )
            
            # Return LangChain-compatible response
            return OllamaResponse(response['response'])
            
        except Exception as e:
            print(f"Ollama invocation error: {e}")
            raise
    
    def _format_messages_for_ollama(self, messages):
        """Format LangChain messages for Ollama"""
        formatted = []
        for message in messages:
            if hasattr(message, 'content'):
                if hasattr(message, 'type') and message.type == 'human':
                    formatted.append(f"User: {message.content}")
                elif hasattr(message, 'type') and message.type == 'ai':
                    formatted.append(f"Assistant: {message.content}")
                else:
                    formatted.append(message.content)
            else:
                formatted.append(str(message))
        
        return "\n".join(formatted) + "\n\nAssistant:"

# Ollama response wrapper
class OllamaResponse:
    """Wrapper for Ollama response to make it compatible with LangChain"""
    
    def __init__(self, content: str):
        self.content = content
    
    @property
    def content(self):
        return self._content
    
    @content.setter
    def content(self, value):
        self._content = value

# Define our state structure
class AnalyticsState:
    def __init__(self, ticker: str, features: Dict, articles: List[Dict], **kwargs):
        self.ticker = ticker
        self.features = features
        self.articles = articles
        self.insights = {}
        self.recommendations = {}
        self.risk_assessment = {}
        self.synthesis = {}
        self.errors = []

# Node 1: Feature Analysis
def analyze_features(state: AnalyticsState) -> AnalyticsState:
    """Analyze deterministic features and identify patterns"""
    try:
        features = state.features
        
        # Extract key metrics
        sentiment_7d = features.get('sentiment', {}).get('mean_7d')
        ret_5d = features.get('returns', {}).get('ret_5d')
        article_count = features.get('context', {}).get('article_count_7d', 0)
        
        # Basic pattern recognition
        patterns = []
        if sentiment_7d and ret_5d:
            if sentiment_7d > 0.6 and ret_5d > 0.05:
                patterns.append("Strong positive sentiment aligns with strong returns")
            elif sentiment_7d < 0.4 and ret_5d < -0.05:
                patterns.append("Negative sentiment correlates with poor performance")
            elif abs(sentiment_7d - 0.5) < 0.1 and abs(ret_5d) < 0.02:
                patterns.append("Neutral sentiment with stable performance")
        
        if article_count < 3:
            patterns.append("Low article coverage - limited information for analysis")
        
        state.insights['patterns'] = patterns
        state.insights['feature_quality'] = 'high' if article_count >= 5 else 'medium'
        
    except Exception as e:
        state.errors.append(f"Feature analysis error: {str(e)}")
    
    return state

# Node 2: Article Sentiment Synthesis
def synthesize_article_sentiment(state: AnalyticsState) -> AnalyticsState:
    """Synthesize article content and sentiment for deeper insights"""
    try:
        if not state.articles:
            state.insights['article_analysis'] = "No recent articles available"
            return state
        
        # Prepare article summary for LLM
        article_summary = []
        for article in state.articles[:5]:  # Top 5 articles
            title = article.get('title', 'No title')
            sentiment = article.get('sentiment')
            sentiment_label = "positive" if sentiment and sentiment > 0.6 else "negative" if sentiment and sentiment < 0.4 else "neutral"
            article_summary.append(f"Title: {title} | Sentiment: {sentiment_label}")
        
        # LLM analysis prompt
        prompt = ChatPromptTemplate.from_template("""
        Analyze these recent articles about {ticker} stock:
        
        {articles}
        
        Provide:
        1. Key themes or topics mentioned
        2. Overall sentiment trend
        3. Any notable events or news
        4. Potential market impact
        
        Be concise and financial-focused.
        """)
        
        messages = prompt.format_messages(
            ticker=state.ticker,
            articles="\n".join(article_summary)
        )
        
        llm_instance = get_llm()
        if llm_instance:
            response = llm_instance.invoke(messages)
            state.insights['article_analysis'] = response.content
        else:
            state.insights['article_analysis'] = "LLM not available - using fallback analysis"
            # Fallback analysis
            positive_count = sum(1 for a in state.articles if a.get('sentiment', 0) > 0.6)
            total_count = len(state.articles)
            if total_count > 0:
                sentiment_trend = "positive" if positive_count > total_count/2 else "neutral" if positive_count == total_count/2 else "negative"
                state.insights['article_analysis'] = f"Fallback analysis: {positive_count}/{total_count} articles show positive sentiment. Overall trend: {sentiment_trend}"
        
    except Exception as e:
        state.errors.append(f"Article synthesis error: {str(e)}")
    
    return state

# Node 3: Risk Assessment
def assess_risk(state: AnalyticsState) -> AnalyticsState:
    """Assess risk based on features and market conditions"""
    try:
        features = state.features
        
        # Extract risk indicators
        vol_z = features.get('context', {}).get('vol_z')
        sent_shock = features.get('sentiment', {}).get('sent_shock')
        ret_5d = features.get('returns', {}).get('ret_5d')
        article_count = features.get('context', {}).get('article_count_7d', 0)
        
        risk_factors = []
        risk_score = 0
        
        # Volume volatility risk
        if vol_z and abs(vol_z) > 2:
            risk_factors.append(f"High volume volatility (Z-score: {vol_z:.2f})")
            risk_score += 0.3
        
        # Sentiment shock risk
        if sent_shock and abs(sent_shock) > 1:
            risk_factors.append(f"Significant sentiment shock ({sent_shock:.2f})")
            risk_score += 0.25
        
        # Information uncertainty risk
        if article_count < 3:
            risk_factors.append("Low information coverage increases uncertainty")
            risk_score += 0.2
        
        # Performance risk
        if ret_5d and ret_5d < -0.1:
            risk_factors.append("Significant negative performance trend")
            risk_score += 0.25
        
        risk_score = min(risk_score, 1.0)
        
        state.risk_assessment = {
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'risk_level': 'high' if risk_score > 0.7 else 'medium' if risk_score > 0.4 else 'low'
        }
        
    except Exception as e:
        state.errors.append(f"Risk assessment error: {str(e)}")
    
    return state

# Node 4: Generate Recommendations
def generate_recommendations(state: AnalyticsState) -> AnalyticsState:
    """Generate actionable recommendations based on analysis"""
    try:
        # Prepare context for LLM
        context = {
            'ticker': state.ticker,
            'patterns': state.insights.get('patterns', []),
            'article_analysis': state.insights.get('article_analysis', ''),
            'risk_assessment': state.risk_assessment,
            'features': state.features
        }
        
        prompt = ChatPromptTemplate.from_template("""
        Based on this stock analysis for {ticker}, provide 2-3 actionable recommendations:
        
        Context:
        - Patterns: {patterns}
        - Article Analysis: {article_analysis}
        - Risk Level: {risk_assessment[risk_level]}
        - Key Metrics: 5d Return: {features[returns][ret_5d]:.2%}, Sentiment: {features[sentiment][mean_7d]:.2f}
        
        Provide:
        1. Short-term action (next 1-3 days)
        2. Medium-term strategy (next 1-2 weeks)
        3. Risk management advice
        
        Be specific, actionable, and financial-focused.
        """)
        
        messages = prompt.format_messages(**context)
        llm_instance = get_llm()
        
        if llm_instance:
            response = llm_instance.invoke(messages)
            state.recommendations = {
                'llm_insights': response.content,
                'confidence': 'high' if len(state.errors) == 0 else 'medium'
            }
        else:
            # Fallback recommendations based on deterministic features
            features = state.features
            ret_5d = features.get('returns', {}).get('ret_5d', 0)
            sent_7d = features.get('sentiment', {}).get('mean_7d', 0.5)
            
            if ret_5d > 0.05 and sent_7d > 0.6:
                recommendation = "Strong positive momentum with positive sentiment. Consider holding or adding to position."
            elif ret_5d < -0.05 and sent_7d < 0.4:
                recommendation = "Negative performance with poor sentiment. Monitor closely and consider risk management."
            else:
                recommendation = "Mixed signals. Monitor for clearer trend development before making significant changes."
            
            state.recommendations = {
                'llm_insights': f"Fallback recommendation: {recommendation}",
                'confidence': 'medium'  # Lower confidence for fallback
            }
        
    except Exception as e:
        state.errors.append(f"Recommendation generation error: {str(e)}")
    
    return state

# Node 5: Final Synthesis
def final_synthesis(state: AnalyticsState) -> AnalyticsState:
    """Create final synthesis combining all insights"""
    try:
        synthesis = {
            'ticker': state.ticker,
            'timestamp': state.features.get('metadata', {}).get('created_at'),
            'summary': {
                'key_insights': state.insights.get('patterns', []),
                'risk_level': state.risk_assessment.get('risk_level', 'unknown'),
                'recommendation_confidence': state.recommendations.get('confidence', 'unknown')
            },
            'analysis': {
                'feature_quality': state.insights.get('feature_quality', 'unknown'),
                'article_coverage': state.features.get('context', {}).get('article_count_7d', 0),
                'sentiment_trend': state.features.get('sentiment', {}).get('mean_7d'),
                'performance_trend': state.features.get('returns', {}).get('ret_5d')
            },
            'llm_enhancements': {
                'article_synthesis': state.insights.get('article_analysis', ''),
                'recommendations': state.recommendations.get('llm_insights', ''),
                'risk_factors': state.risk_assessment.get('risk_factors', [])
            }
        }
        
        state.synthesis = synthesis
        
    except Exception as e:
        state.errors.append(f"Final synthesis error: {str(e)}")
    
    return state

# Create the LangGraph workflow
def create_analytics_workflow():
    """Create the LangGraph workflow for analytics enhancement"""
    
    # Create the graph
    workflow = StateGraph(AnalyticsState)
    
    # Add nodes
    workflow.add_node("analyze_features", analyze_features)
    workflow.add_node("synthesize_articles", synthesize_article_sentiment)
    workflow.add_node("assess_risk", assess_risk)
    workflow.add_node("generate_recommendations", generate_recommendations)
    workflow.add_node("final_synthesis", final_synthesis)
    
    # Define the flow
    workflow.set_entry_point("analyze_features")
    workflow.add_edge("analyze_features", "synthesize_articles")
    workflow.add_edge("synthesize_articles", "assess_risk")
    workflow.add_edge("assess_risk", "generate_recommendations")
    workflow.add_edge("generate_recommendations", "final_synthesis")
    workflow.add_edge("final_synthesis", END)
    
    return workflow.compile()

# Main function to run the workflow
async def enhance_analytics_with_llm(
    ticker: str, 
    features: Dict, 
    articles: List[Dict]
) -> Dict[str, Any]:
    """
    Run the LangGraph workflow to enhance analytics with LLM insights
    
    Args:
        ticker: Stock ticker symbol
        features: Deterministic features from our pipeline
        articles: Recent articles about the ticker
    
    Returns:
        Enhanced analytics with LLM insights
    """
    try:
        # Create workflow
        workflow = create_analytics_workflow()
        
        # Initialize state
        initial_state = AnalyticsState(
            ticker=ticker,
            features=features,
            articles=articles
        )
        
        # Run workflow
        result = await workflow.ainvoke(initial_state)
        
        return {
            'success': True,
            'enhanced_analytics': result.synthesis,
            'errors': result.errors
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'enhanced_analytics': None
        }

# Synchronous wrapper for compatibility
def enhance_analytics_with_llm_sync(
    ticker: str, 
    features: Dict, 
    articles: List[Dict]
) -> Dict[str, Any]:
    """Synchronous wrapper for the LLM enhancement"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        enhance_analytics_with_llm(ticker, features, articles)
    )
