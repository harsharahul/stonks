/**
 * WebSocket hooks for real-time communication
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { analyzeWebSocketError, WebSocketError } from '../utils/errorHandling';

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
  onError?: (error: WebSocketError) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export const useWebSocket = (url: string, options: UseWebSocketOptions = {}) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [connectionError, setConnectionError] = useState<WebSocketError | null>(null);
  
  const ws = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const mountedRef = useRef(true);
  const connectionIdRef = useRef(0);
  
  // Environment-specific configuration
  const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const maxAttempts = options.maxReconnectAttempts || 5;
  const reconnectInterval = options.reconnectInterval || (isDevelopment ? 1000 : 3000);

  const connect = useCallback(() => {
    try {
      // Prevent duplicate connections - check if already connected or connecting
      if (ws.current?.readyState === WebSocket.OPEN || 
          ws.current?.readyState === WebSocket.CONNECTING) {
        if (isDevelopment) {
          console.log(`🔄 WebSocket already connected/connecting (state: ${ws.current.readyState}), skipping...`);
        }
        return;
      }
      
      // Generate unique connection ID to track this attempt
      connectionIdRef.current += 1;
      const currentConnectionId = connectionIdRef.current;
      
      // Close existing connection if any
      if (ws.current && ws.current.readyState !== WebSocket.CLOSED) {
        ws.current.close();
      }
      
      // Reset error state before attempting connection
      setConnectionError(null);
      
      if (isDevelopment) {
        console.log(`🔗 Attempting WebSocket connection to: ${url} (ID: ${currentConnectionId})`);
      }
      ws.current = new WebSocket(url);
      
      ws.current.onopen = () => {
        // Verify this is still the current connection attempt
        if (currentConnectionId !== connectionIdRef.current) {
          if (isDevelopment) {
            console.log(`🔄 Stale connection opened (ID: ${currentConnectionId}), ignoring...`);
          }
          return;
        }
        
        if (isDevelopment) {
          console.log(`✅ WebSocket connected: ${url} (ID: ${currentConnectionId})`);
        }
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttempts.current = 0;
        options.onConnect?.();
      };
      
      ws.current.onmessage = (event) => {
        // Verify this is still the current connection
        if (currentConnectionId !== connectionIdRef.current) {
          if (isDevelopment) {
            console.log(`🔄 Message from stale connection (ID: ${currentConnectionId}), ignoring...`);
          }
          return;
        }
        
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          options.onMessage?.(message);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      ws.current.onclose = (event) => {
        // Only process close events for the current connection
        if (currentConnectionId !== connectionIdRef.current) {
          if (isDevelopment) {
            console.log(`🔄 Close event from stale connection (ID: ${currentConnectionId}), ignoring...`);
          }
          return;
        }
        
        if (isDevelopment) {
          console.log(`WebSocket disconnected: ${url} (ID: ${currentConnectionId})`, {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean
          });
        }
        
        setIsConnected(false);
        options.onDisconnect?.();
        
        // Analyze the error and set proper error state
        const wsError = analyzeWebSocketError(event, 'open');
        setConnectionError(wsError);
        
        // Don't reconnect for normal closures
        if (event.code === 1000) {
          return;
        }
        
        // Only attempt reconnection if component is still mounted and within attempt limits
        if (mountedRef.current && reconnectAttempts.current < maxAttempts) {
          reconnectAttempts.current++;
          const delay = reconnectInterval * Math.pow(1.5, reconnectAttempts.current - 1); // Gentler backoff
          
          if (isDevelopment) {
            console.log(`🔄 Reconnecting in ${delay}ms... (attempt ${reconnectAttempts.current}/${maxAttempts})`);
          }
          
          setTimeout(() => {
            if (mountedRef.current && reconnectAttempts.current <= maxAttempts) {
              connect();
            }
          }, delay);
        } else if (reconnectAttempts.current >= maxAttempts) {
          const maxAttemptsError: WebSocketError = {
            type: 'connection',
            message: 'Max reconnection attempts reached. Please refresh the page.',
            recoverable: false
          };
          setConnectionError(maxAttemptsError);
        }
      };
      
      ws.current.onerror = (error) => {
        // Only process errors for the current connection
        if (currentConnectionId !== connectionIdRef.current) {
          if (isDevelopment) {
            console.log(`🔄 Error from stale connection (ID: ${currentConnectionId}), ignoring...`);
          }
          return;
        }
        
        console.error('❌ WebSocket error:', error);
        
        const wsError = analyzeWebSocketError(error, ws.current?.readyState === WebSocket.CONNECTING ? 'connecting' : 'open');
        setConnectionError(wsError);
        options.onError?.(wsError);
      };
      
    } catch (error) {
      console.error('❌ Error creating WebSocket:', error);
      const creationError: WebSocketError = {
        type: 'connection',
        message: 'Failed to create WebSocket connection',
        recoverable: true,
        retryDelay: 3000
      };
      setConnectionError(creationError);
    }
  }, [url, maxAttempts, reconnectInterval]); // Removed options from dependencies to prevent recreation

  const disconnect = useCallback(() => {
    mountedRef.current = false;
    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    // Reset mounted state for new effect
    mountedRef.current = true;
    
    // React Strict Mode protection: add a small delay to prevent duplicate connections
    // and use a flag to track if the component is still mounted
    const timer = setTimeout(() => {
      if (mountedRef.current) {
        connect();
      }
    }, isDevelopment ? 150 : 50); // Longer delay in development to handle Strict Mode
    
    return () => {
      clearTimeout(timer);
      disconnect();
    };
  }, [url]); // Only depend on url, not on connect/disconnect functions
  
  // Update mounted state on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Debug function for development
  const getDebugInfo = useCallback(() => {
    return {
      url,
      isConnected,
      connectionId: connectionIdRef.current,
      reconnectAttempts: reconnectAttempts.current,
      readyState: ws.current?.readyState,
      isDevelopment,
      mounted: mountedRef.current
    };
  }, [url, isConnected, isDevelopment]);

  return {
    isConnected,
    lastMessage,
    connectionError,
    sendMessage,
    disconnect,
    reconnect: connect,
    debugInfo: isDevelopment ? getDebugInfo : undefined
  };
};

// Get WebSocket base URL based on environment
const getWebSocketBaseUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
};

// Specific hooks for different channels
export const useAlertsWebSocket = (userId?: string, options: UseWebSocketOptions = {}) => {
  const baseUrl = getWebSocketBaseUrl();
  const url = `${baseUrl}/api/v1/ws/alerts${userId ? `?user_id=${userId}` : ''}`;
  
  return useWebSocket(url, options);
};

export const useSignalsWebSocket = (ticker: string, options: UseWebSocketOptions = {}) => {
  const baseUrl = getWebSocketBaseUrl();
  const url = `${baseUrl}/api/v1/ws/signals/${ticker.toUpperCase()}`;
  
  return useWebSocket(url, options);
};

export const useMarketWebSocket = (options: UseWebSocketOptions = {}) => {
  const baseUrl = getWebSocketBaseUrl();
  const url = `${baseUrl}/api/v1/ws/market`;
  
  return useWebSocket(url, options);
};

export const useAnomaliesWebSocket = (ticker?: string, options: UseWebSocketOptions = {}) => {
  const baseUrl = getWebSocketBaseUrl();
  const url = `${baseUrl}/api/v1/ws/anomalies${ticker ? `?ticker=${ticker.toUpperCase()}` : ''}`;
  
  return useWebSocket(url, options);
};

export const useWSBTrendingWebSocket = (options: UseWebSocketOptions = {}) => {
  const baseUrl = getWebSocketBaseUrl();
  const url = `${baseUrl}/api/v1/ws/wsb/trending`;
  
  return useWebSocket(url, options);
};
