"""
LangGraph-based Analytics Agent for Stonks
Enhances deterministic features with LLM-powered insights and synthesis
"""
from typing import Dict, List, Any, Optional, TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json
import logging
import os

logger = logging.getLogger(__name__)

# Initialize LLM based on ANALYTICS_LLM_PROVIDER config
def get_llm():
    """Get LLM instance based on configured provider"""
    provider = os.getenv("ANALYTICS_LLM_PROVIDER", "none")

    if provider == "none":
        return None

    try:
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key and api_key != "your_openai_api_key_here":
                return ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0.1,
                    max_tokens=1000
                )
            print("OpenAI provider configured but no valid API key found")
            return None

        if provider == "ollama":
            ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
            print(f"Using Ollama model: {ollama_model} at {ollama_host}")
            return OllamaLLM(model=ollama_model, host=ollama_host)

        print(f"Unknown LLM provider: {provider}")
        return None

    except Exception as e:
        print(f"LLM initialization error: {e}")
        return None

# Ollama LLM wrapper for LangChain compatibility
class OllamaLLM:
    """Wrapper for Ollama to make it compatible with LangChain"""
    
    def __init__(self, model: str = "qwen3:14b", temperature: float = 0.1, host: str = None):
        self.model = model
        self.temperature = temperature
        self.client = None
        try:
            import ollama
            if host:
                self.client = ollama.Client(host=host)
            else:
                self.client = ollama.Client()
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

# Define our state structure as TypedDict for LangGraph
class AnalyticsState(TypedDict):
    ticker: str
    features: Dict
    articles: List[Dict]
    insights: Dict
    recommendations: Dict
    risk_assessment: Dict
    synthesis: Dict
    errors: List[str]

# Node 1: Feature Analysis
def analyze_features(state: AnalyticsState) -> Dict:
    """Analyze deterministic features and identify patterns"""
    try:
        features = state['features']

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

        insights = state.get('insights', {})
        insights['patterns'] = patterns
        insights['feature_quality'] = 'high' if article_count >= 5 else 'medium'

        return {'insights': insights}

    except Exception as e:
        errors = state.get('errors', [])
        errors.append(f"Feature analysis error: {str(e)}")
        return {'errors': errors}

# Node 2: Article Sentiment Synthesis
def synthesize_article_sentiment(state: AnalyticsState) -> Dict:
    """Synthesize article content and sentiment for deeper insights"""
    insights = state.get('insights', {})
    errors = state.get('errors', [])

    try:
        if not state['articles']:
            insights['article_analysis'] = "No recent articles available"
            return {'insights': insights}

        # Prepare article summary for LLM
        article_summary = []
        for article in state['articles'][:5]:  # Top 5 articles
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
            ticker=state['ticker'],
            articles="\n".join(article_summary)
        )

        llm_instance = get_llm()
        if llm_instance:
            response = llm_instance.invoke(messages)
            insights['article_analysis'] = response.content
        else:
            insights['article_analysis'] = "LLM not available - using fallback analysis"
            # Fallback analysis
            positive_count = sum(1 for a in state['articles'] if a.get('sentiment', 0) > 0.6)
            total_count = len(state['articles'])
            if total_count > 0:
                sentiment_trend = "positive" if positive_count > total_count/2 else "neutral" if positive_count == total_count/2 else "negative"
                insights['article_analysis'] = f"Fallback analysis: {positive_count}/{total_count} articles show positive sentiment. Overall trend: {sentiment_trend}"

        return {'insights': insights}

    except Exception as e:
        errors.append(f"Article synthesis error: {str(e)}")
        return {'errors': errors, 'insights': insights}

# Node 3: Risk Assessment
def assess_risk(state: AnalyticsState) -> Dict:
    """Assess risk based on features and market conditions"""
    errors = state.get('errors', [])

    try:
        features = state['features']

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

        risk_assessment = {
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'risk_level': 'high' if risk_score > 0.7 else 'medium' if risk_score > 0.4 else 'low'
        }

        return {'risk_assessment': risk_assessment}

    except Exception as e:
        errors.append(f"Risk assessment error: {str(e)}")
        return {'errors': errors}

# Node 4: Generate Recommendations
def generate_recommendations(state: AnalyticsState) -> Dict:
    """Generate actionable recommendations based on analysis"""
    errors = state.get('errors', [])

    try:
        # Prepare context for LLM
        insights = state.get('insights', {})
        risk_assessment = state.get('risk_assessment', {})
        features = state['features']

        raw_ret = features.get('returns', {}).get('ret_5d')
        raw_sent = features.get('sentiment', {}).get('mean_7d')

        context = {
            'ticker': state['ticker'],
            'patterns': insights.get('patterns', []),
            'article_analysis': insights.get('article_analysis', ''),
            'risk_level': risk_assessment.get('risk_level', 'unknown'),
            'ret_5d': raw_ret if raw_ret is not None else 0.0,
            'sent_mean_7d': raw_sent if raw_sent is not None else 0.5
        }

        prompt = ChatPromptTemplate.from_template("""
        Based on this stock analysis for {ticker}, provide 2-3 actionable recommendations:

        Context:
        - Patterns: {patterns}
        - Article Analysis: {article_analysis}
        - Risk Level: {risk_level}
        - Key Metrics: 5d Return: {ret_5d:.2%}, Sentiment: {sent_mean_7d:.2f}

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
            recommendations = {
                'llm_insights': response.content,
                'confidence': 'high' if len(errors) == 0 else 'medium',
                'llm_fallback': False,
            }
        else:
            # HONEST fallback: the LLM is unavailable, so this is rule-derived
            # text: say so loudly and machine-readably instead of passing it
            # off as analysis (audit finding #9).
            logger.warning("analytics_agent: LLM unavailable: serving rule-derived fallback recommendation")
            ret_5d = context['ret_5d']
            sent_7d = context['sent_mean_7d']

            if ret_5d > 0.05 and sent_7d > 0.6:
                recommendation = "Strong positive momentum with positive sentiment. Consider holding or adding to position."
            elif ret_5d < -0.05 and sent_7d < 0.4:
                recommendation = "Negative performance with poor sentiment. Monitor closely and consider risk management."
            else:
                recommendation = "Mixed signals. Monitor for clearer trend development before making significant changes."

            recommendations = {
                'llm_insights': f"[AI offline: rule-derived fallback] {recommendation}",
                'confidence': 'low',
                'llm_fallback': True,
            }

        return {'recommendations': recommendations}

    except Exception as e:
        errors.append(f"Recommendation generation error: {str(e)}")
        return {'errors': errors}

# Node 5: Final Synthesis
def final_synthesis(state: AnalyticsState) -> Dict:
    """Create final synthesis combining all insights"""
    errors = state.get('errors', [])

    try:
        insights = state.get('insights', {})
        risk_assessment = state.get('risk_assessment', {})
        recommendations = state.get('recommendations', {})
        features = state['features']

        synthesis = {
            'ticker': state['ticker'],
            'timestamp': features.get('metadata', {}).get('created_at'),
            'summary': {
                'key_insights': insights.get('patterns', []),
                'risk_level': risk_assessment.get('risk_level', 'unknown'),
                'recommendation_confidence': recommendations.get('confidence', 'unknown')
            },
            'analysis': {
                'feature_quality': insights.get('feature_quality', 'unknown'),
                'article_coverage': features.get('context', {}).get('article_count_7d', 0),
                'sentiment_trend': features.get('sentiment', {}).get('mean_7d'),
                'performance_trend': features.get('returns', {}).get('ret_5d')
            },
            'llm_enhancements': {
                'article_synthesis': insights.get('article_analysis', ''),
                'recommendations': recommendations.get('llm_insights', ''),
                'risk_factors': risk_assessment.get('risk_factors', [])
            }
        }

        return {'synthesis': synthesis}

    except Exception as e:
        errors.append(f"Final synthesis error: {str(e)}")
        return {'errors': errors}

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

        # Initialize state as dict
        initial_state: AnalyticsState = {
            'ticker': ticker,
            'features': features,
            'articles': articles,
            'insights': {},
            'recommendations': {},
            'risk_assessment': {},
            'synthesis': {},
            'errors': []
        }

        # Run workflow
        result = await workflow.ainvoke(initial_state)

        return {
            'success': True,
            'enhanced_analytics': result.get('synthesis'),
            'errors': result.get('errors', [])
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
    """Synchronous wrapper for the LLM enhancement - runs in thread pool"""
    import asyncio
    import concurrent.futures

    # Run async function in a new thread with its own event loop
    # This avoids "event loop already running" errors in FastAPI
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(
            asyncio.run,
            enhance_analytics_with_llm(ticker, features, articles)
        )
        return future.result()
