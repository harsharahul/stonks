/**
 * WebSocket hooks for real-time communication
 */

import { useEffect, useRef, useState, useCallback } from 'react';

export interface WebSocketMessage {
  type: string;
  channel: string;
  data: any;
  timestamp: string;
}

export interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export const useWebSocket = (url: string, options: UseWebSocketOptions = {}) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  
  const ws = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const maxAttempts = options.maxReconnectAttempts || 5;
  const reconnectInterval = options.reconnectInterval || 3000;

  const connect = useCallback(() => {
    try {
      ws.current = new WebSocket(url);
      
      ws.current.onopen = () => {
        console.log(`WebSocket connected: ${url}`);
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttempts.current = 0;
        options.onConnect?.();
      };
      
      ws.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          options.onMessage?.(message);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      ws.current.onclose = () => {
        console.log(`WebSocket disconnected: ${url}`);
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
  }, [url, options, maxAttempts, reconnectInterval]);

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
    reconnect: connect
  };
};

// Specific hooks for different channels
export const useAlertsWebSocket = (userId?: string, options: UseWebSocketOptions = {}) => {
  const baseUrl = process.env.NODE_ENV === 'development' 
    ? 'ws://localhost:8080' 
    : `ws://${window.location.host}`;
  
  const url = `${baseUrl}/api/v1/ws/alerts${userId ? `?user_id=${userId}` : ''}`;
  
  return useWebSocket(url, options);
};

export const useSignalsWebSocket = (ticker: string, options: UseWebSocketOptions = {}) => {
  const baseUrl = process.env.NODE_ENV === 'development' 
    ? 'ws://localhost:8080' 
    : `ws://${window.location.host}`;
  
  const url = `${baseUrl}/api/v1/ws/signals/${ticker.toUpperCase()}`;
  
  return useWebSocket(url, options);
};

export const useMarketWebSocket = (options: UseWebSocketOptions = {}) => {
  const baseUrl = process.env.NODE_ENV === 'development' 
    ? 'ws://localhost:8080' 
    : `ws://${window.location.host}`;
  
  const url = `${baseUrl}/api/v1/ws/market`;
  
  return useWebSocket(url, options);
};

export const useAnomaliesWebSocket = (ticker?: string, options: UseWebSocketOptions = {}) => {
  const baseUrl = process.env.NODE_ENV === 'development' 
    ? 'ws://localhost:8080' 
    : `ws://${window.location.host}`;
  
  const url = `${baseUrl}/api/v1/ws/anomalies${ticker ? `?ticker=${ticker.toUpperCase()}` : ''}`;
  
  return useWebSocket(url, options);
};

export const useWSBTrendingWebSocket = (options: UseWebSocketOptions = {}) => {
  const baseUrl = process.env.NODE_ENV === 'development' 
    ? 'ws://localhost:8080' 
    : `ws://${window.location.host}`;
  
  const url = `${baseUrl}/api/v1/ws/wsb/trending`;
  
  return useWebSocket(url, options);
};
