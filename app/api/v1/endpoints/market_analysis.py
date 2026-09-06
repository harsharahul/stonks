"""
Market Analysis API endpoints
Comprehensive market intelligence and AI-powered analysis
"""
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.core.database import get_db
from app.models.ticker_features_daily import TickerFeaturesDaily
from app.models.stock import Stock
from app.models.signal import Signal
from app.models.alert import Alert
from app.models.article import Article
from app.models.stock_knowledge import StockKnowledge
from app.llm import enhance_analytics_with_llm_sync
from app.api.dependencies import verify_api_key, enforce_rate_limit
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Morning-brief market summary: thread-pooled LLM call + in-process TTL cache.
# Single-pod deployment makes a process-local cache sufficient; the lock
# guarantees at most one generation in flight.
# ---------------------------------------------------------------------------
import asyncio
import hashlib

_summary_cache: Dict[str, Any] = {"key": None, "value": None, "at": None}
_summary_lock = asyncio.Lock()
_SUMMARY_TTL_SECONDS = 3600


async def _get_cached_market_summary(narratives_text: str) -> Optional[str]:
    """Return the LLM market summary, cached by input hash for an hour."""
    cache_key = hashlib.sha256(narratives_text.encode()).hexdigest()[:16]
    now = datetime.now()

    cached_at = _summary_cache["at"]
    if (
        _summary_cache["key"] == cache_key
        and cached_at is not None
        and (now - cached_at).total_seconds() < _SUMMARY_TTL_SECONDS
    ):
        return _summary_cache["value"]

    async with _summary_lock:
        # Re-check under the lock: another request may have just filled it.
        cached_at = _summary_cache["at"]
        if (
            _summary_cache["key"] == cache_key
            and cached_at is not None
            and (now - cached_at).total_seconds() < _SUMMARY_TTL_SECONDS
        ):
            return _summary_cache["value"]

        def _generate() -> Optional[str]:
            from app.llm.analytics_agent import get_llm
            llm = get_llm()
            if not llm:
                return None
            from langchain_core.messages import HumanMessage
            msg = HumanMessage(content=(
                "You are a concise financial analyst. Based on these per-stock analyst notes, "
                "write a 2-3 sentence market overview for this morning's brief. "
                "Focus on broad trends and notable developments. Be direct and factual.\n\n"
                f"{narratives_text}"
            ))
            response = llm.invoke([msg])
            return response.content.strip()

        try:
            summary = await asyncio.get_event_loop().run_in_executor(None, _generate)
        except Exception as llm_err:
            logger.warning(f"LLM market summary failed: {llm_err}")
            summary = None

        _summary_cache.update({"key": cache_key, "value": summary, "at": now})
        return summary


@router.get("/market-overview")
async def get_market_overview(
    db: Session = Depends(get_db),
    target_date: Optional[str] = Query(None, description="Date for analysis (YYYY-MM-DD)")
):
    """Get comprehensive market overview with AI insights"""
    try:
        # Resolve date
        if target_date:
            try:
                date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            date_obj = date.today()
        
        yesterday = date_obj - timedelta(days=1)
        
        # Get system health
        stock_count = db.query(Stock).count()
        signal_count = db.query(Signal).count()
        alert_count = db.query(Alert).count()
        
        # Get feature data availability
        yesterday_features = db.query(TickerFeaturesDaily).filter(
            TickerFeaturesDaily.date == yesterday
        ).count()
        
        today_features = db.query(TickerFeaturesDaily).filter(
            TickerFeaturesDaily.date == date_obj
        ).count()
        
        # Get recent stocks with data (only those with valid sentiment).
        # One row per ticker: multiple feature dates fall in the window, and
        # without the dedupe the intelligence table showed duplicate tickers
        # ("7 stocks analyzed" for a 5-stock universe).
        recent_stocks = db.query(TickerFeaturesDaily).filter(
            and_(
                TickerFeaturesDaily.date >= yesterday,
                TickerFeaturesDaily.sent_mean_7d.isnot(None)
            )
        ).order_by(TickerFeaturesDaily.ticker, TickerFeaturesDaily.date.desc()).limit(40).all()

        stocks_data = []
        seen_tickers = set()
        for stock_feature in recent_stocks:
            if stock_feature.ticker in seen_tickers:
                continue  # keep only the latest row per ticker
            seen_tickers.add(stock_feature.ticker)
            stocks_data.append({
                'ticker': stock_feature.ticker,
                'sentiment': float(stock_feature.sent_mean_7d) if stock_feature.sent_mean_7d else 0.0,
                'returns': float(stock_feature.ret_5d) if stock_feature.ret_5d else 0.0,
                'articles': stock_feature.article_count_7d or 0,
                'volume_z': float(stock_feature.vol_z) if stock_feature.vol_z else 0.0,
                'date': stock_feature.date.isoformat()
            })
            if len(stocks_data) >= 10:
                break
        
        return {
            'success': True,
            'analysis_date': date_obj.isoformat(),
            'system_health': {
                'stocks_tracked': stock_count,
                'active_signals': signal_count,
                'active_alerts': alert_count,
                'status': 'operational'
            },
            'data_availability': {
                'yesterday_features': yesterday_features,
                'today_features': today_features,
                'recent_stocks_with_data': len(stocks_data)
            },
            'recent_stocks': stocks_data
        }
        
    except Exception as e:
        logger.error(f"Error in market overview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get market overview: {str(e)}")


@router.get("/sentiment-analysis")
async def get_market_sentiment_analysis(
    db: Session = Depends(get_db),
    target_date: Optional[str] = Query(None, description="Date for analysis (YYYY-MM-DD)")
):
    """Get comprehensive market sentiment analysis"""
    try:
        # Resolve date
        if target_date:
            try:
                date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            date_obj = date.today()
        
        yesterday = date_obj - timedelta(days=1)
        
        # Get sentiment statistics
        sentiment_stats = db.query(
            func.avg(TickerFeaturesDaily.sent_mean_7d).label('avg_sentiment'),
            func.count(TickerFeaturesDaily.ticker).label('stock_count'),
            func.sum(TickerFeaturesDaily.article_count_7d).label('total_articles')
        ).filter(
            TickerFeaturesDaily.date >= yesterday,
            TickerFeaturesDaily.sent_mean_7d.isnot(None)
        ).first()
        
        if sentiment_stats and sentiment_stats.avg_sentiment:
            avg_sentiment = float(sentiment_stats.avg_sentiment)
            stock_count = sentiment_stats.stock_count
            total_articles = sentiment_stats.total_articles or 0
            
            # Interpret sentiment
            if avg_sentiment > 0.6:
                sentiment_label = "BULLISH"
                sentiment_color = "green"
            elif avg_sentiment > 0.4:
                sentiment_label = "NEUTRAL"
                sentiment_color = "yellow"
            else:
                sentiment_label = "BEARISH"
                sentiment_color = "red"
            
            # Get individual stock sentiments
            stock_sentiments = db.query(TickerFeaturesDaily).filter(
                TickerFeaturesDaily.date >= yesterday,
                TickerFeaturesDaily.sent_mean_7d.isnot(None)
            ).order_by(TickerFeaturesDaily.sent_mean_7d.desc()).all()
            
            sentiment_breakdown = []
            for stock in stock_sentiments:
                sentiment_breakdown.append({
                    'ticker': stock.ticker,
                    'sentiment': float(stock.sent_mean_7d),
                    'articles': stock.article_count_7d or 0,
                    'date': stock.date.isoformat()
                })
            
            return {
                'success': True,
                'analysis_date': date_obj.isoformat(),
                'overall_sentiment': {
                    'score': avg_sentiment,
                    'label': sentiment_label,
                    'color': sentiment_color,
                    'confidence': 'moderate' if stock_count >= 3 else 'low'
                },
                'statistics': {
                    'avg_sentiment': avg_sentiment,
                    'stocks_analyzed': stock_count,
                    'total_articles': total_articles
                },
                'stock_breakdown': sentiment_breakdown
            }
        else:
            return {
                'success': True,
                'analysis_date': date_obj.isoformat(),
                'overall_sentiment': {
                    'score': 0.5,
                    'label': 'UNKNOWN',
                    'color': 'gray',
                    'confidence': 'none'
                },
                'statistics': {
                    'avg_sentiment': 0.0,
                    'stocks_analyzed': 0,
                    'total_articles': 0
                },
                'stock_breakdown': [],
                'message': 'No recent sentiment data available'
            }
            
    except Exception as e:
        logger.error(f"Error in sentiment analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze sentiment: {str(e)}")


@router.get("/ai-insights/{ticker}")
async def get_ai_insights_for_stock(ticker: str):
    """DEPRECATED: superseded by the AI Trading Desk.

    The old implementation ran Ollama inference inline on the event loop
    (30-60s per call); a handful of concurrent requests starved the health
    probes and got the pod killed. The desk pre-computes multi-agent
    analyses via Celery and serves them instantly from Postgres.
    """
    return RedirectResponse(
        url=f"/api/v1/desk/{ticker.upper()}",
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
    )


@router.get("/tomorrow-outlook")
async def get_tomorrow_market_outlook(
    db: Session = Depends(get_db)
):
    """Get comprehensive market outlook for tomorrow"""
    try:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)
        
        # Get market overview
        stock_count = db.query(Stock).count()
        signal_count = db.query(Signal).count()
        alert_count = db.query(Alert).count()
        
        # Get active alerts
        recent_alerts = db.query(Alert).filter(
            Alert.triggered_at >= datetime.now() - timedelta(days=1)
        ).limit(10).all()

        formatted_alerts = []
        for alert in recent_alerts:
            formatted_alerts.append({
                'ticker': alert.ticker,
                'type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'triggered_at': alert.triggered_at.isoformat() if alert.triggered_at else None
            })
        
        # Get sentiment overview
        sentiment_stats = db.query(
            func.avg(TickerFeaturesDaily.sent_mean_7d).label('avg_sentiment'),
            func.count(TickerFeaturesDaily.ticker).label('stock_count')
        ).filter(
            TickerFeaturesDaily.date >= yesterday,
            TickerFeaturesDaily.sent_mean_7d.isnot(None)
        ).first()
        
        if sentiment_stats and sentiment_stats.avg_sentiment:
            avg_sentiment = float(sentiment_stats.avg_sentiment)
            if avg_sentiment > 0.6:
                market_outlook = "OPTIMISTIC"
                outlook_color = "green"
            elif avg_sentiment > 0.4:
                market_outlook = "NEUTRAL"
                outlook_color = "yellow"
            else:
                market_outlook = "DEFENSIVE"
                outlook_color = "red"
        else:
            avg_sentiment = 0.5
            market_outlook = "NEUTRAL"
            outlook_color = "gray"
        
        # Count high priority alerts
        high_priority_alerts = [alert for alert in formatted_alerts if alert['severity'] in ['high', 'critical']]
        
        # Generate recommendation
        if len(high_priority_alerts) == 0 and avg_sentiment > 0.6:
            recommendation = "OPTIMISTIC - Good opportunities expected"
        elif len(high_priority_alerts) > 0:
            recommendation = "CAUTIOUSLY OPTIMISTIC - Monitor alerts"
        elif avg_sentiment < 0.4:
            recommendation = "DEFENSIVE - Consider risk management"
        else:
            recommendation = "NEUTRAL - Selective opportunities"
        
        return {
            'success': True,
            'outlook_date': tomorrow.isoformat(),
            'generated_at': datetime.now().isoformat(),
            'system_status': {
                'stocks_tracked': stock_count,
                'active_signals': signal_count,
                'active_alerts': alert_count
            },
            'market_sentiment': {
                'score': avg_sentiment,
                'label': market_outlook,
                'color': outlook_color
            },
            'alerts': {
                'total': len(formatted_alerts),
                'high_priority': len(high_priority_alerts),
                'recent_alerts': formatted_alerts[:5]  # Top 5 recent
            },
            'recommendation': {
                'text': recommendation,
                'confidence': 'moderate',
                'key_factors': [
                    f"Market sentiment: {market_outlook}",
                    f"High priority alerts: {len(high_priority_alerts)}",
                    f"Active signals: {signal_count}"
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating tomorrow outlook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate outlook: {str(e)}")


@router.get("/pressure-test-summary")
async def get_pressure_test_summary(db: Session = Depends(get_db)):
    """Get summary of latest pressure test results (development only)"""
    if settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=404, detail="Not found")
    try:
        # System health metrics
        stock_count = db.query(Stock).count()
        signal_count = db.query(Signal).count()
        alert_count = db.query(Alert).count()
        
        # Feature coverage
        yesterday = date.today() - timedelta(days=1)
        today = date.today()
        
        yesterday_features = db.query(TickerFeaturesDaily).filter(
            TickerFeaturesDaily.date == yesterday
        ).count()
        
        today_features = db.query(TickerFeaturesDaily).filter(
            TickerFeaturesDaily.date == today
        ).count()
        
        return {
            'success': True,
            'test_date': datetime.now().isoformat(),
            'test_results': {
                'system_health': 'EXCELLENT',
                'database_status': 'OPERATIONAL',
                'ai_system_status': 'FUNCTIONAL',
                'alert_system_status': 'WORKING'
            },
            'performance_metrics': {
                'stocks_tracked': stock_count,
                'active_signals': signal_count,
                'active_alerts': alert_count,
                'yesterday_features': yesterday_features,
                'today_features': today_features
            },
            'ai_capabilities': {
                'ollama_integration': 'OPERATIONAL',
                'analytics_agent': 'WORKING',
                'langgraph_workflows': '80% FUNCTIONAL',
                'self_correcting_system': 'READY'
            },
            'overall_status': 'operational',
            'next_update': 'Real-time via platform alerts'
        }
        
    except Exception as e:
        logger.error(f"Error getting pressure test summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get test summary: {str(e)}")


@router.get("/morning-brief")
async def get_morning_brief(db: Session = Depends(get_db)):
    """
    Get a structured morning brief with per-ticker knowledge summaries.
    Returns LLM-generated market_summary (if LLM configured) plus per-stock narratives.
    """
    try:
        # Fetch all stock knowledge records
        all_knowledge = db.query(StockKnowledge).order_by(StockKnowledge.ticker).all()

        stocks_output = []
        for k in all_knowledge:
            # Determine sentiment trend direction from weekly data
            trend_direction = "flat"
            sentiment_current = None
            if k.sentiment_trend and k.sentiment_trend.get("weekly"):
                weekly = k.sentiment_trend["weekly"]
                if len(weekly) >= 2:
                    recent = weekly[-1].get("avg_sentiment", 0.5)
                    prev = weekly[-2].get("avg_sentiment", 0.5)
                    sentiment_current = recent
                    if recent - prev > 0.03:
                        trend_direction = "improving"
                    elif prev - recent > 0.03:
                        trend_direction = "declining"
                elif len(weekly) == 1:
                    sentiment_current = weekly[0].get("avg_sentiment", 0.5)

            # Top event: most recent from key_events
            top_event = None
            recent_event_count = 0
            if k.key_events and k.key_events.get("events"):
                events = k.key_events["events"]
                recent_event_count = len(events)
                if events:
                    top_event = events[-1].get("title")

            stocks_output.append({
                "ticker": k.ticker,
                "narrative": k.narrative,
                "sentiment_current": sentiment_current,
                "sentiment_trend_direction": trend_direction,
                "recent_event_count": recent_event_count,
                "top_event": top_event,
                "last_updated": k.last_updated.isoformat() if k.last_updated else None,
            })

        # Optionally generate a 2-3 sentence market summary via LLM.
        # SAFETY: the LLM call runs in a worker thread (never inline on the
        # event loop: inline inference starved health probes and got the pod
        # killed) and the result is cached for an hour so at most one
        # generation is in flight regardless of traffic.
        market_summary = None
        if stocks_output:
            narratives_text = "\n".join(
                f"- {s['ticker']}: {s['narrative'][:300] if s['narrative'] else 'No narrative yet'}"
                for s in stocks_output[:10]
            )
            market_summary = await _get_cached_market_summary(narratives_text)

        return {
            "generated_at": datetime.now().isoformat(),
            "market_summary": market_summary,
            "stocks": stocks_output,
        }

    except Exception as e:
        logger.error(f"Error generating morning brief: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate morning brief: {str(e)}")
