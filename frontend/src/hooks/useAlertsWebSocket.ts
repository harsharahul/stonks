/**
 * WebSocket hook specifically for alerts
 */

import { useEffect, useRef, useState, useCallback } from 'react';

export interface WebSocketMessage {
  type: string;
  channel: string;
  data: any;
  timestamp: string;
}

export interface UseAlertsWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export const useAlertsWebSocket = (
  userId?: string,
  options: UseAlertsWebSocketOptions = {}
) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  
  const ws = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const maxAttempts = options.maxReconnectAttempts || 5;
  const reconnectInterval = options.reconnectInterval || 3000;

  // Build WebSocket URL
  const wsUrl = userId 
    ? `ws://localhost:8080/api/v1/ws/alerts?user_id=${userId}`
    : `ws://localhost:8080/api/v1/ws/alerts`;

  const connect = useCallback(() => {
    try {
      console.log(`Connecting to alerts WebSocket: ${wsUrl}`);
      ws.current = new WebSocket(wsUrl);
      
      ws.current.onopen = () => {
        console.log(`WebSocket connected: ${wsUrl}`);
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttempts.current = 0;
        options.onConnect?.();
      };
      
      ws.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          console.log('Received WebSocket message:', message);
          setLastMessage(message);
          options.onMessage?.(message);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      ws.current.onclose = () => {
        console.log(`WebSocket disconnected: ${wsUrl}`);
        setIsConnected(false);
        options.onDisconnect?.();
        
        // Attempt reconnection
        if (reconnectAttempts.current < maxAttempts) {
          reconnectAttempts.current++;
          console.log(`Reconnecting... (attempt ${reconnectAttempts.current}/${maxAttempts})`);
          setTimeout(connect, reconnectInterval);
        } else {
          setConnectionError('Max reconnection attempts reached');
        }
      };
      
      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionError('Connection error');
        options.onError?.(error);
      };
      
    } catch (error) {
      console.error('Error creating WebSocket:', error);
      setConnectionError('Failed to create connection');
    }
  }, [wsUrl, options, maxAttempts, reconnectInterval]);

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    connect();
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    connectionError,
    sendMessage,
    disconnect,
    connect
  };
};
