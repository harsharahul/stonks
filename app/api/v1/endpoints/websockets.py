"""
WebSocket API endpoints for real-time communication

Provides WebSocket connections for:
- Real-time alerts
- Trading signals  
- Market updates
- Anomaly notifications
- WSB trending updates
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Query, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.websocket_manager import connection_manager, event_broadcaster, WebSocketMessage

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/alerts")
async def websocket_alerts(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="OIDC access token for authenticated channel"),
    user_id: Optional[str] = Query(None, description="Legacy user ID (deprecated, use token)"),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time alerts

    Channels:
    - alerts:global - System-wide alerts
    - alerts:{user_id} - User-specific alerts (requires valid token)
    """
    # Per-user channels require a VALID token, the bare user_id query param is
    # never trusted on its own (it would let any client subscribe to any user's
    # alert stream). No token / invalid token ⇒ global channel only.
    resolved_user_id = None
    if token:
        try:
            from app.core.auth import validate_token, extract_user_info
            claims = await validate_token(token)
            resolved_user_id = extract_user_info(claims).get("provider_user_id")
        except Exception as e:
            # M3: Log invalid tokens for monitoring
            logger.warning(f"WebSocket token validation failed: {e}")
            # Fall back to global channel for invalid tokens

    channel = f"alerts:{resolved_user_id}" if resolved_user_id else "alerts:global"
    
    try:
        await connection_manager.connect(websocket, channel, user_id)
        
        # Send connection confirmation message
        connection_message = {
            "type": "connection",
            "channel": channel,
            "data": {
                "status": "connected",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await websocket.send_text(json.dumps(connection_message))
        
        while True:
            # Keep connection alive and handle incoming messages
            try:
                data = await websocket.receive_text()
                
                # Handle client messages (e.g., alert acknowledgments)
                try:
                    message = json.loads(data)
                    await handle_client_message(message, websocket, db)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from client: {data}")
                
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"Error in alerts WebSocket: {e}")
    finally:
        connection_manager.disconnect(websocket)


@router.websocket("/signals/{ticker}")
async def websocket_ticker_signals(
    websocket: WebSocket,
    ticker: str,
    user_id: Optional[str] = Query(None, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for ticker-specific trading signals
    """
    channel = f"signals:{ticker.upper()}"
    
    try:
        await connection_manager.connect(websocket, channel, user_id)
        
        # Send current signals for this ticker on connection
        from app.services.signal_generator import SignalGenerator
        generator = SignalGenerator(db)
        current_signals = generator.get_active_signals(ticker.upper(), limit=10)
        
        if current_signals:
            initial_data = {
                "type": "initial_signals",
                "ticker": ticker.upper(),
                "signals": [signal.to_dict() for signal in current_signals],
                "count": len(current_signals)
            }
            
            await event_broadcaster.broadcast_signal(initial_data)
        
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any client messages if needed
                
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"Error in signals WebSocket for {ticker}: {e}")
    finally:
        connection_manager.disconnect(websocket)


@router.websocket("/market")
async def websocket_market_updates(
    websocket: WebSocket,
    user_id: Optional[str] = Query(None, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for general market updates and overview
    """
    channel = "market:general"
    
    try:
        await connection_manager.connect(websocket, channel, user_id)
        
        # Send initial market overview
        try:
            from app.services.signal_generator import SignalGenerator
            from app.services.alert_engine import AlertEngine
            
            generator = SignalGenerator(db)
            alert_engine = AlertEngine(db)
            
            # Get market overview data
            top_signals = generator.get_active_signals(limit=20)
            recent_alerts = alert_engine.get_recent_alerts(hours=4, limit=10)
            alert_stats = alert_engine.get_alert_stats(days=1)
            
            market_overview = {
                "type": "market_overview",
                "top_signals": [signal.to_dict() for signal in top_signals],
                "recent_alerts": [alert.to_dict() for alert in recent_alerts],
                "alert_stats": alert_stats,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            await event_broadcaster.broadcast_market_update(market_overview)
            
        except Exception as e:
            logger.error(f"Error sending initial market overview: {e}")
        
        while True:
            try:
                data = await websocket.receive_text()
                # Handle client messages
                
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"Error in market WebSocket: {e}")
    finally:
        connection_manager.disconnect(websocket)


@router.websocket("/anomalies")
async def websocket_anomalies(
    websocket: WebSocket,
    ticker: Optional[str] = Query(None, description="Specific ticker to monitor"),
    user_id: Optional[str] = Query(None, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time anomaly notifications
    """
    channel = f"anomalies:{ticker.upper()}" if ticker else "anomalies:all"
    
    try:
        await connection_manager.connect(websocket, channel, user_id)
        
        while True:
            try:
                data = await websocket.receive_text()
                # Handle client messages
                
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"Error in anomalies WebSocket: {e}")
    finally:
        connection_manager.disconnect(websocket)


@router.websocket("/wsb/trending")
async def websocket_wsb_trending(
    websocket: WebSocket,
    user_id: Optional[str] = Query(None, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for WSB trending stocks updates
    """
    channel = "wsb:trending"
    
    try:
        await connection_manager.connect(websocket, channel, user_id)
        
        # Send initial trending data
        try:
            from app.features.retail_sentiment import RetailSentimentFeatures
            trending = RetailSentimentFeatures.get_trending_tickers(db, days=7, limit=20)
            
            trending_data = {
                "type": "wsb_trending",
                "trending_tickers": trending,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            await event_broadcaster.broadcast_wsb_trending(trending_data)
            
        except Exception as e:
            logger.error(f"Error sending initial WSB trending: {e}")
        
        while True:
            try:
                data = await websocket.receive_text()
                # Handle client messages
                
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"Error in WSB trending WebSocket: {e}")
    finally:
        connection_manager.disconnect(websocket)


async def handle_client_message(message: Dict[str, Any], websocket: WebSocket, db: Session):
    """
    Handle incoming messages from WebSocket clients
    """
    message_type = message.get("type")
    
    if message_type == "acknowledge_alert":
        # Handle alert acknowledgment
        alert_id = message.get("alert_id")
        if alert_id:
            from app.services.alert_engine import AlertEngine
            alert_engine = AlertEngine(db)
            success = alert_engine.acknowledge_alert(alert_id)
            
            response = {
                "type": "acknowledgment_response",
                "alert_id": alert_id,
                "success": success,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            response_msg = WebSocketMessage(
                type="response",
                channel="client",
                data=response,
                timestamp=datetime.utcnow().isoformat()
            )
            
            await connection_manager._send_to_websocket(websocket, response_msg)
    
    elif message_type == "ping":
        # Handle ping/pong for connection health
        pong_msg = WebSocketMessage(
            type="pong",
            channel="client",
            data={"timestamp": datetime.utcnow().isoformat()},
            timestamp=datetime.utcnow().isoformat()
        )
        
        await connection_manager._send_to_websocket(websocket, pong_msg)
    
    elif message_type == "subscribe_ticker":
        # Handle dynamic ticker subscription
        ticker = message.get("ticker")
        if ticker:
            # This would require more complex connection management
            # For now, clients need to establish separate connections per ticker
            pass
    
    else:
        logger.warning(f"Unknown message type from client: {message_type}")
