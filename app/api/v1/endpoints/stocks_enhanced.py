"""
Enhanced Stocks API endpoints
Comprehensive stock management with AI discovery and user controls
"""
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from pydantic import BaseModel

from app.core.database import get_db
from app.models.stock import Stock
from app.models.ticker_features_daily import TickerFeaturesDaily
from app.models.signal import Signal
from app.models.alert import Alert
from app.api.dependencies import verify_api_key, enforce_rate_limit
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class StockCreateRequest(BaseModel):
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    priority_level: Optional[str] = "normal"  # low, normal, high
    added_by: Optional[str] = "user"  # user, ai_discovery, signal_detection


class StockUpdateRequest(BaseModel):
    name: Optional[str] = None
    sector: Optional[str] = None
    priority_level: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/comprehensive")
async def get_comprehensive_stocks(
    db: Session = Depends(get_db),
    limit: int = Query(50, description="Number of stocks to return"),
    include_inactive: bool = Query(False, description="Include inactive stocks"),
    priority_filter: Optional[str] = Query(None, description="Filter by priority level"),
    sector_filter: Optional[str] = Query(None, description="Filter by sector"),
    sort_by: str = Query("priority", description="Sort by: priority, activity, name, recent_signals")
):
    """Get comprehensive list of all tracked stocks with enhanced data"""
    try:
        # Base query
        query = db.query(Stock)
        
        # Apply filters
        if not include_inactive:
            query = query.filter(Stock.is_active == True)
            
        if priority_filter:
            query = query.filter(Stock.priority_level == priority_filter)
            
        if sector_filter:
            query = query.filter(Stock.sector == sector_filter)
        
        # Get stocks
        stocks = query.limit(limit).all()
        
        # Enhance with additional data
        enhanced_stocks = []
        for stock in stocks:
            # Get latest features
            latest_features = db.query(TickerFeaturesDaily).filter(
                TickerFeaturesDaily.ticker == stock.symbol
            ).order_by(desc(TickerFeaturesDaily.date)).first()
            
            # Get recent signals count
            recent_signals = db.query(Signal).filter(
                and_(
                    Signal.ticker == stock.symbol,
                    Signal.generated_at >= datetime.utcnow() - timedelta(days=7)
                )
            ).count()
            
            # Get recent alerts count  
            recent_alerts = db.query(Alert).filter(
                and_(
                    Alert.ticker == stock.symbol,
                    Alert.triggered_at >= datetime.utcnow() - timedelta(days=7)
                )
            ).count()
            
            enhanced_stock = {
                'symbol': stock.symbol,
                'name': stock.company_name,
                'sector': stock.sector,
                'priority_level': getattr(stock, 'priority_level', 'normal'),
                'is_active': stock.is_active,
                'added_by': getattr(stock, 'added_by', 'unknown'),
                'created_at': stock.created_at.isoformat() if hasattr(stock, 'created_at') else None,
                'last_updated': stock.updated_at.isoformat() if hasattr(stock, 'updated_at') else None,
                
                # Enhanced analytics
                'recent_activity': {
                    'signals_7d': recent_signals,
                    'alerts_7d': recent_alerts,
                    'has_recent_features': latest_features is not None,
                    'last_feature_date': latest_features.date.isoformat() if latest_features else None
                },
                
                # Latest features if available
                'latest_features': {
                    'sentiment': float(latest_features.sent_mean_7d) if latest_features and latest_features.sent_mean_7d else None,
                    'returns_5d': float(latest_features.ret_5d) if latest_features and latest_features.ret_5d else None,
                    'article_count': latest_features.article_count_7d if latest_features else 0,
                    'volume_z': float(latest_features.vol_z) if latest_features and latest_features.vol_z else None,
                    'date': latest_features.date.isoformat() if latest_features else None
                } if latest_features else None
            }
            
            enhanced_stocks.append(enhanced_stock)
        
        # Sort results
        if sort_by == "priority":
            priority_order = {"high": 0, "normal": 1, "low": 2}
            enhanced_stocks.sort(key=lambda x: priority_order.get(x['priority_level'], 1))
        elif sort_by == "activity":
            enhanced_stocks.sort(key=lambda x: x['recent_activity']['signals_7d'] + x['recent_activity']['alerts_7d'], reverse=True)
        elif sort_by == "name":
            enhanced_stocks.sort(key=lambda x: x['symbol'])
        elif sort_by == "recent_signals":
            enhanced_stocks.sort(key=lambda x: x['recent_activity']['signals_7d'], reverse=True)
        
        return {
            'success': True,
            'total': len(enhanced_stocks),
            'stocks': enhanced_stocks,
            'filters_applied': {
                'include_inactive': include_inactive,
                'priority_filter': priority_filter,
                'sector_filter': sector_filter,
                'sort_by': sort_by
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting comprehensive stocks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stocks: {str(e)}")


@router.post("/add")
async def add_stock_to_tracking(
    stock_request: StockCreateRequest,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Add a new stock to tracking system"""
    try:
        # Check if stock already exists
        existing_stock = db.query(Stock).filter(Stock.symbol == stock_request.symbol.upper()).first()
        
        if existing_stock:
            if existing_stock.is_active:
                return {
                    'success': False,
                    'message': f'Stock {stock_request.symbol} is already being tracked',
                    'stock': {
                        'symbol': existing_stock.symbol,
                        'name': existing_stock.company_name,
                        'is_active': existing_stock.is_active
                    }
                }
            else:
                # Reactivate existing stock
                existing_stock.is_active = True
                existing_stock.priority_level = stock_request.priority_level
                if hasattr(existing_stock, 'updated_at'):
                    existing_stock.updated_at = datetime.utcnow()
                db.commit()
                
                return {
                    'success': True,
                    'message': f'Stock {stock_request.symbol} reactivated',
                    'stock': {
                        'symbol': existing_stock.symbol,
                        'name': existing_stock.company_name,
                        'is_active': existing_stock.is_active,
                        'priority_level': getattr(existing_stock, 'priority_level', 'normal')
                    }
                }
        
        # Create new stock
        new_stock = Stock(
            symbol=stock_request.symbol.upper(),
            company_name=stock_request.name or stock_request.symbol.upper(),
            sector=stock_request.sector,
            is_active=True
        )
        
        # Add enhanced fields if columns exist
        if hasattr(Stock, 'priority_level'):
            new_stock.priority_level = stock_request.priority_level
        if hasattr(Stock, 'added_by'):
            new_stock.added_by = stock_request.added_by
        
        db.add(new_stock)
        db.commit()
        db.refresh(new_stock)
        
        # Trigger background feature calculation if available
        if background_tasks:
            background_tasks.add_task(trigger_feature_calculation, stock_request.symbol.upper())
        
        return {
            'success': True,
            'message': f'Stock {stock_request.symbol} added to tracking',
            'stock': {
                'symbol': new_stock.symbol,
                'name': new_stock.company_name,
                'sector': new_stock.sector,
                'is_active': new_stock.is_active,
                'priority_level': getattr(new_stock, 'priority_level', 'normal'),
                'added_by': getattr(new_stock, 'added_by', 'user')
            }
        }
        
    except Exception as e:
        logger.error(f"Error adding stock {stock_request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add stock: {str(e)}")


@router.delete("/remove/{symbol}")
async def remove_stock_from_tracking(
    symbol: str,
    db: Session = Depends(get_db)
):
    """Remove a stock from tracking system (only user-added stocks)"""
    try:
        stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
        
        if not stock:
            return {
                'success': False,
                'message': f'Stock {symbol} not found'
            }
        
        # Only allow removal of user-added stocks
        if stock.added_by != 'user':
            return {
                'success': False,
                'message': f'Cannot remove system-tracked stock {symbol}. Only user-added stocks can be removed.'
            }
        
        # Soft delete by setting as inactive
        stock.is_active = False
        db.commit()
        
        return {
            'success': True,
            'message': f'Stock {symbol} removed from tracking',
            'stock': {
                'symbol': stock.symbol,
                'name': stock.company_name,
                'sector': stock.sector,
                'is_active': stock.is_active,
                'priority_level': getattr(stock, 'priority_level', 'normal'),
                'added_by': stock.added_by
            }
        }
        
    except Exception as e:
        logger.error(f"Error removing stock {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove stock: {str(e)}")


@router.put("/{symbol}")
async def update_stock(
    symbol: str,
    stock_update: StockUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update stock tracking settings"""
    try:
        stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
        
        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
        
        # Update fields
        if stock_update.name is not None:
            stock.company_name = stock_update.name
        if stock_update.sector is not None:
            stock.sector = stock_update.sector
        if stock_update.is_active is not None:
            stock.is_active = stock_update.is_active
        if stock_update.priority_level is not None and hasattr(stock, 'priority_level'):
            stock.priority_level = stock_update.priority_level
            
        if hasattr(stock, 'updated_at'):
            stock.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            'success': True,
            'message': f'Stock {symbol} updated successfully',
            'stock': {
                'symbol': stock.symbol,
                'name': stock.name,
                'sector': stock.sector,
                'is_active': stock.is_active,
                'priority_level': getattr(stock, 'priority_level', 'normal')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating stock {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update stock: {str(e)}")


@router.get("/ai-discovered")
async def get_ai_discovered_stocks(
    db: Session = Depends(get_db),
    days: int = Query(7, description="Days to look back for AI discoveries"),
    limit: int = Query(20, description="Number of stocks to return")
):
    """Get stocks discovered by AI systems"""
    try:
        # Get stocks that have been active in signals/alerts recently but might not be formally tracked
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Find stocks with recent signals
        signal_stocks = db.query(Signal.ticker, func.count(Signal.id).label('signal_count')).filter(
            Signal.generated_at >= cutoff_date
        ).group_by(Signal.ticker).having(func.count(Signal.id) >= 2).all()
        
        # Find stocks with recent alerts
        alert_stocks = db.query(Alert.ticker, func.count(Alert.id).label('alert_count')).filter(
            Alert.triggered_at >= cutoff_date
        ).group_by(Alert.ticker).having(func.count(Alert.id) >= 1).all()
        
        # Combine and analyze
        discovered_stocks = []
        all_discovered_tickers = set([s.ticker for s in signal_stocks] + [a.ticker for a in alert_stocks])
        
        for ticker in all_discovered_tickers:
            # Check if already formally tracked
            existing_stock = db.query(Stock).filter(Stock.symbol == ticker).first()
            
            signal_count = next((s.signal_count for s in signal_stocks if s.ticker == ticker), 0)
            alert_count = next((a.alert_count for a in alert_stocks if a.ticker == ticker), 0)
            
            # Get recent signal types
            recent_signals = db.query(Signal.signal_type).filter(
                and_(Signal.ticker == ticker, Signal.generated_at >= cutoff_date)
            ).distinct().all()
            
            discovered_stocks.append({
                'ticker': ticker,
                'signal_count': signal_count,
                'alert_count': alert_count,
                'activity_score': signal_count * 2 + alert_count,
                'recent_signal_types': [s.signal_type for s in recent_signals],
                'is_tracked': existing_stock is not None and existing_stock.is_active if existing_stock else False,
                'discovery_confidence': min(1.0, (signal_count + alert_count) / 5.0),  # 0-1 confidence score
                'suggested_priority': 'high' if signal_count + alert_count >= 5 else 'normal' if signal_count + alert_count >= 2 else 'low'
            })
        
        # Sort by activity score
        discovered_stocks.sort(key=lambda x: x['activity_score'], reverse=True)
        
        return {
            'success': True,
            'discovery_period_days': days,
            'total_discovered': len(discovered_stocks),
            'discovered_stocks': discovered_stocks[:limit],
            'summary': {
                'high_confidence': len([s for s in discovered_stocks if s['discovery_confidence'] > 0.7]),
                'medium_confidence': len([s for s in discovered_stocks if 0.3 < s['discovery_confidence'] <= 0.7]),
                'low_confidence': len([s for s in discovered_stocks if s['discovery_confidence'] <= 0.3]),
                'already_tracked': len([s for s in discovered_stocks if s['is_tracked']])
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting AI discovered stocks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get AI discoveries: {str(e)}")


@router.get("/discovery-suggestions")
async def get_discovery_suggestions(
    db: Session = Depends(get_db),
    limit: int = Query(10, description="Number of suggestions to return")
):
    """Get AI suggestions for new stocks to track"""
    try:
        # This would use more sophisticated AI analysis in production
        # For now, we'll use signal/alert patterns
        
        suggestions = []
        
        # Get trending stocks from recent activity
        recent_activity = db.query(
            Signal.ticker,
            func.count(Signal.id).label('recent_signals'),
            func.avg(Signal.strength).label('avg_strength'),
            func.max(Signal.generated_at).label('latest_signal')
        ).filter(
            Signal.generated_at >= datetime.utcnow() - timedelta(days=3)
        ).group_by(Signal.ticker).having(
            func.count(Signal.id) >= 2
        ).order_by(desc('recent_signals'), desc('avg_strength')).all()
        
        for activity in recent_activity[:limit]:
            # Check if already tracked
            existing_stock = db.query(Stock).filter(Stock.symbol == activity.ticker).first()
            
            if not existing_stock or not existing_stock.is_active:
                suggestions.append({
                    'ticker': activity.ticker,
                    'reason': 'High signal activity detected',
                    'confidence': min(1.0, activity.recent_signals / 5.0),
                    'recent_signals': activity.recent_signals,
                    'avg_strength': float(activity.avg_strength) if activity.avg_strength else 0.0,
                    'latest_activity': activity.latest_signal.isoformat(),
                    'suggested_priority': 'high' if activity.recent_signals >= 5 else 'normal',
                    'auto_add_recommended': activity.recent_signals >= 3 and (activity.avg_strength or 0) > 0.7
                })
        
        return {
            'success': True,
            'total_suggestions': len(suggestions),
            'suggestions': suggestions,
            'auto_add_ready': len([s for s in suggestions if s['auto_add_recommended']])
        }
        
    except Exception as e:
        logger.error(f"Error getting discovery suggestions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")


def trigger_feature_calculation(symbol: str):
    """Background task to trigger feature calculation for new stock"""
    try:
        # This would trigger the feature calculation pipeline
        logger.info(f"Triggering feature calculation for {symbol}")
        # Implementation would call the feature calculation service
    except Exception as e:
        logger.error(f"Error triggering feature calculation for {symbol}: {e}")


@router.get("/stats")
async def get_stock_tracking_stats(db: Session = Depends(get_db)):
    """Get comprehensive statistics about stock tracking"""
    try:
        # Basic counts
        total_stocks = db.query(Stock).count()
        active_stocks = db.query(Stock).filter(Stock.is_active == True).count()
        
        # Priority distribution
        priority_dist = {}
        if hasattr(Stock, 'priority_level'):
            priority_query = db.query(Stock.priority_level, func.count()).group_by(Stock.priority_level).all()
            priority_dist = {level: count for level, count in priority_query}
        
        # Recent activity
        recent_signals = db.query(func.count(Signal.id)).filter(
            Signal.generated_at >= datetime.utcnow() - timedelta(days=7)
        ).scalar()
        
        recent_alerts = db.query(func.count(Alert.id)).filter(
            Alert.triggered_at >= datetime.utcnow() - timedelta(days=7)
        ).scalar()
        
        # Stocks with recent features
        stocks_with_features = db.query(func.count(func.distinct(TickerFeaturesDaily.ticker))).filter(
            TickerFeaturesDaily.date >= date.today() - timedelta(days=7)
        ).scalar()
        
        return {
            'success': True,
            'tracking_stats': {
                'total_stocks': total_stocks,
                'active_stocks': active_stocks,
                'inactive_stocks': total_stocks - active_stocks,
                'priority_distribution': priority_dist,
                'recent_activity': {
                    'signals_7d': recent_signals,
                    'alerts_7d': recent_alerts,
                    'stocks_with_features_7d': stocks_with_features
                },
                'coverage': {
                    'feature_coverage': f"{(stocks_with_features/max(active_stocks, 1)*100):.1f}%"
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting stock tracking stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
