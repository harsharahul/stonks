"""
WebSocket Manager for Real-Time Communication

Manages WebSocket connections, channels, and real-time event broadcasting.
Supports multiple channels: alerts, signals, market data, WSB trending.
"""

import json
import logging
from typing import Dict, List, Set, Any, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class WebSocketMessage:
    """Standardized WebSocket message format"""
    type: str  # 'alert', 'signal', 'anomaly', 'market_update', etc.
    channel: str
    data: Dict[str, Any]
    timestamp: str
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))


class ConnectionManager:
    """
    Manages WebSocket connections and channel subscriptions
    """
    
    def __init__(self):
        # Active connections by channel
        self.connections: Dict[str, Set[WebSocket]] = {}
        
        # Connection metadata
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}
        
        # Channel statistics
        self.channel_stats: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str, user_id: str = None):
        """
        Accept a new WebSocket connection and subscribe to channel
        """
        await websocket.accept()
        
        # Initialize channel if doesn't exist
        if channel not in self.connections:
            self.connections[channel] = set()
            self.channel_stats[channel] = {
                "total_connections": 0,
                "active_connections": 0,
                "messages_sent": 0,
                "created_at": datetime.utcnow().isoformat()
            }
        
        # Add connection to channel
        self.connections[channel].add(websocket)
        
        # Store connection metadata
        self.connection_info[websocket] = {
            "channel": channel,
            "user_id": user_id,
            "connected_at": datetime.utcnow().isoformat(),
            "messages_received": 0
        }
        
        # Update stats
        self.channel_stats[channel]["total_connections"] += 1
        self.channel_stats[channel]["active_connections"] = len(self.connections[channel])
        
        logger.info(f"WebSocket connected to channel '{channel}' (user: {user_id})")
        
        # Send welcome message
        welcome_msg = WebSocketMessage(
            type="connection",
            channel=channel,
            data={
                "status": "connected",
                "channel": channel,
                "user_id": user_id,
                "server_time": datetime.utcnow().isoformat()
            },
            timestamp=datetime.utcnow().isoformat()
        )
        
        await self._send_to_websocket(websocket, welcome_msg)
    
    def disconnect(self, websocket: WebSocket):
        """
        Handle WebSocket disconnection
        """
        if websocket in self.connection_info:
            channel = self.connection_info[websocket]["channel"]
            user_id = self.connection_info[websocket].get("user_id")
            
            # Remove from channel
            if channel in self.connections:
                self.connections[channel].discard(websocket)
                self.channel_stats[channel]["active_connections"] = len(self.connections[channel])
            
            # Remove connection info
            del self.connection_info[websocket]
            
            logger.info(f"WebSocket disconnected from channel '{channel}' (user: {user_id})")
    
    async def broadcast_to_channel(self, channel: str, message: WebSocketMessage):
        """
        Broadcast message to all connections in a channel
        """
        if channel not in self.connections:
            logger.warning(f"Attempted to broadcast to non-existent channel: {channel}")
            return
        
        connections_to_remove = set()
        sent_count = 0
        
        for websocket in self.connections[channel].copy():
            try:
                await self._send_to_websocket(websocket, message)
                sent_count += 1
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                connections_to_remove.add(websocket)
        
        # Clean up dead connections
        for websocket in connections_to_remove:
            self.disconnect(websocket)
        
        # Update stats
        if channel in self.channel_stats:
            self.channel_stats[channel]["messages_sent"] += sent_count
        
        logger.debug(f"Broadcast to channel '{channel}': {sent_count} recipients")
    
    async def send_to_user(self, user_id: str, message: WebSocketMessage):
        """
        Send message to all connections for a specific user
        """
        user_connections = [
            ws for ws, info in self.connection_info.items()
            if info.get("user_id") == user_id
        ]
        
        for websocket in user_connections:
            try:
                await self._send_to_websocket(websocket, message)
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")
                self.disconnect(websocket)
    
    async def _send_to_websocket(self, websocket: WebSocket, message: WebSocketMessage):
        """
        Send message to a specific WebSocket connection
        """
        try:
            await websocket.send_text(message.to_json())
            
            # Update connection stats
            if websocket in self.connection_info:
                self.connection_info[websocket]["messages_received"] += 1
                
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            raise
    
    def get_channel_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all channels
        """
        return {
            "channels": self.channel_stats,
            "total_active_connections": sum(len(conns) for conns in self.connections.values()),
            "total_channels": len(self.connections),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def get_connection_info(self) -> List[Dict[str, Any]]:
        """
        Get information about active connections
        """
        return [
            {
                "channel": info["channel"],
                "user_id": info.get("user_id"),
                "connected_at": info["connected_at"],
                "messages_received": info["messages_received"]
            }
            for info in self.connection_info.values()
        ]


# Global connection manager instance
connection_manager = ConnectionManager()


class EventBroadcaster:
    """
    Handles broadcasting of different event types to appropriate channels
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
    
    async def broadcast_alert(self, alert_data: Dict[str, Any], user_id: str = None):
        """
        Broadcast alert to appropriate channels
        """
        message = WebSocketMessage(
            type="alert",
            channel=f"alerts:{user_id}" if user_id else "alerts:global",
            data=alert_data,
            timestamp=datetime.utcnow().isoformat()
        )
        
        if user_id:
            await self.connection_manager.send_to_user(user_id, message)
        else:
            await self.connection_manager.broadcast_to_channel("alerts:global", message)
    
    async def broadcast_signal(self, signal_data: Dict[str, Any]):
        """
        Broadcast trading signal to ticker-specific channel
        """
        ticker = signal_data.get("ticker", "UNKNOWN")
        
        message = WebSocketMessage(
            type="signal",
            channel=f"signals:{ticker}",
            data=signal_data,
            timestamp=datetime.utcnow().isoformat()
        )
        
        await self.connection_manager.broadcast_to_channel(f"signals:{ticker}", message)
        
        # Also broadcast to general signals channel
        await self.connection_manager.broadcast_to_channel("signals:all", message)
    
    async def broadcast_anomaly(self, anomaly_data: Dict[str, Any]):
        """
        Broadcast anomaly detection result
        """
        ticker = anomaly_data.get("ticker", "MARKET")
        
        message = WebSocketMessage(
            type="anomaly",
            channel=f"anomalies:{ticker}",
            data=anomaly_data,
            timestamp=datetime.utcnow().isoformat()
        )
        
        await self.connection_manager.broadcast_to_channel(f"anomalies:{ticker}", message)
        await self.connection_manager.broadcast_to_channel("anomalies:all", message)
    
    async def broadcast_market_update(self, market_data: Dict[str, Any]):
        """
        Broadcast general market updates
        """
        message = WebSocketMessage(
            type="market_update",
            channel="market:general",
            data=market_data,
            timestamp=datetime.utcnow().isoformat()
        )
        
        await self.connection_manager.broadcast_to_channel("market:general", message)
    
    async def broadcast_wsb_trending(self, trending_data: Dict[str, Any]):
        """
        Broadcast WSB trending updates
        """
        message = WebSocketMessage(
            type="wsb_trending",
            channel="wsb:trending",
            data=trending_data,
            timestamp=datetime.utcnow().isoformat()
        )
        
        await self.connection_manager.broadcast_to_channel("wsb:trending", message)
    
    async def broadcast_price_update(self, price_data: Dict[str, Any]):
        """
        Broadcast real-time price updates
        """
        ticker = price_data.get("ticker", "UNKNOWN")
        
        message = WebSocketMessage(
            type="price_update",
            channel=f"prices:{ticker}",
            data=price_data,
            timestamp=datetime.utcnow().isoformat()
        )
        
        await self.connection_manager.broadcast_to_channel(f"prices:{ticker}", message)
        await self.connection_manager.broadcast_to_channel("prices:all", message)


# Global event broadcaster instance
event_broadcaster = EventBroadcaster(connection_manager)
