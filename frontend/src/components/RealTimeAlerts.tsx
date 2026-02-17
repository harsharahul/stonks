/**
 * Real-Time Alerts Component
 * 
 * Displays live alerts and notifications using WebSocket connection
 * Enhanced with modern UI, animations, and improved UX
 */

import React, { useState, useEffect, useRef } from 'react';
import { useAlertsWebSocket, WebSocketMessage } from '../hooks/useWebSocket';
import { parseApiError, formatErrorForDisplay } from '../utils/errorHandling';
import ErrorToast from './ErrorToast';
import apiClient from '../api/client';

interface Alert {
  id: string;
  ticker: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  triggered_at: string;
  acknowledged_at?: string;
  metadata: any;
}

interface RealTimeAlertsProps {
  userId?: string;
  maxAlerts?: number;
  autoAcknowledge?: boolean;
}

const RealTimeAlerts: React.FC<RealTimeAlertsProps> = ({ 
  userId, 
  maxAlerts = 10,
  autoAcknowledge = false 
}) => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [showNewAlertAnimation, setShowNewAlertAnimation] = useState(false);
  const [isLoadingAlerts, setIsLoadingAlerts] = useState(true);
  const [apiError, setApiError] = useState<any>(null);
  const alertSoundRef = useRef<HTMLAudioElement | null>(null);

  // Draggable overlay state
  const containerRef = useRef<HTMLDivElement | null>(null);
  const dragOffsetRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [position, setPosition] = useState<{ x: number; y: number }>({ x: 0, y: 100 });

  const { isConnected, lastMessage, connectionError, sendMessage, reconnect } = useAlertsWebSocket(
    userId,
    {
      onMessage: (message: WebSocketMessage) => {
        console.log('Received WebSocket message:', message);
        
        if (message.type === 'alert') {
          const newAlert = message.data as Alert;
          
          setAlerts(prev => {
            const updated = [newAlert, ...prev];
            return updated.slice(0, maxAlerts); // Keep only recent alerts
          });
          
          // Trigger new alert animation
          setShowNewAlertAnimation(true);
          setTimeout(() => setShowNewAlertAnimation(false), 1000);
          
          // Play notification sound for high priority alerts
          if (newAlert.severity === 'critical' || newAlert.severity === 'high') {
            playNotificationSound();
          }
          
          // Increment unread count if not auto-acknowledging
          if (!autoAcknowledge && !newAlert.acknowledged_at) {
            setUnreadCount(prev => prev + 1);
          }
          
          // Auto-acknowledge if enabled
          if (autoAcknowledge) {
            acknowledgeAlert(newAlert.id);
          }
        }
      },
      onConnect: () => {
        console.log('Connected to alerts WebSocket');
        setApiError(null); // Clear any previous errors on successful connection
      },
      onDisconnect: () => {
        console.log('Disconnected from alerts WebSocket');
      },
      onError: (error) => {
        console.error('WebSocket error:', error);
        setApiError(error);
      }
    }
  );

  // Initialize position (persisted or default below navbar, top-right)
  useEffect(() => {
    try {
      const saved = localStorage.getItem('liveAlertsPosition');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (typeof parsed?.x === 'number' && typeof parsed?.y === 'number') {
          setPosition({ x: parsed.x, y: parsed.y });
          return;
        }
      }
    } catch {}

    // Default after first paint to compute width
    requestAnimationFrame(() => {
      const width = containerRef.current?.offsetWidth ?? 320;
      const x = Math.max(16, window.innerWidth - width - 16);
      const y = 96; // place below navbar by default
      setPosition({ x, y });
    });
  }, []);

  // Keep overlay inside viewport on resize
  useEffect(() => {
    const onResize = () => {
      const width = containerRef.current?.offsetWidth ?? 320;
      const height = containerRef.current?.offsetHeight ?? 400;
      const x = Math.min(Math.max(position.x, 8), window.innerWidth - width - 8);
      const y = Math.min(Math.max(position.y, 8), window.innerHeight - height - 8);
      if (x !== position.x || y !== position.y) setPosition({ x, y });
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [position]);

  // Drag handlers
  const onHeaderMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    const rect = containerRef.current?.getBoundingClientRect();
    dragOffsetRef.current = { x: e.clientX - (rect?.left ?? 0), y: e.clientY - (rect?.top ?? 0) };
    e.preventDefault();
  };

  const onHeaderTouchStart = (e: React.TouchEvent) => {
    const t = e.touches[0];
    setIsDragging(true);
    const rect = containerRef.current?.getBoundingClientRect();
    dragOffsetRef.current = { x: t.clientX - (rect?.left ?? 0), y: t.clientY - (rect?.top ?? 0) };
  };

  useEffect(() => {
    if (!isDragging) return;

    const move = (clientX: number, clientY: number) => {
      const width = containerRef.current?.offsetWidth ?? 320;
      const height = containerRef.current?.offsetHeight ?? 400;
      const nextX = Math.min(Math.max(clientX - dragOffsetRef.current.x, 8), window.innerWidth - width - 8);
      const nextY = Math.min(Math.max(clientY - dragOffsetRef.current.y, 8), window.innerHeight - height - 8);
      setPosition({ x: nextX, y: nextY });
    };

    const onMouseMove = (e: MouseEvent) => move(e.clientX, e.clientY);
    const onMouseUp = () => {
      setIsDragging(false);
      try { localStorage.setItem('liveAlertsPosition', JSON.stringify(position)); } catch {}
    };

    const onTouchMove = (e: TouchEvent) => {
      const t = e.touches[0];
      move(t.clientX, t.clientY);
    };
    const onTouchEnd = () => {
      setIsDragging(false);
      try { localStorage.setItem('liveAlertsPosition', JSON.stringify(position)); } catch {}
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    window.addEventListener('touchmove', onTouchMove);
    window.addEventListener('touchend', onTouchEnd);

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onTouchEnd);
    };
  }, [isDragging, position]);

  // Fetch recent alerts on component mount
  const fetchRecentAlerts = async () => {
    try {
      setIsLoadingAlerts(true);
      const response = await apiClient.get('/signals/alerts?hours=6&limit=10');
      const recentAlerts = response.data.alerts;
      
      if (recentAlerts && recentAlerts.length > 0) {
        setAlerts(recentAlerts);
        // Don't count existing alerts as unread initially
        console.log(`📥 Loaded ${recentAlerts.length} recent alerts`);
      } else {
        console.log('📭 No recent alerts found');
      }
    } catch (error) {
      console.error('❌ Failed to fetch recent alerts:', error);
      const parsedError = parseApiError(error);
      setApiError(parsedError);
    } finally {
      setIsLoadingAlerts(false);
    }
  };

  // Load recent alerts on component mount
  useEffect(() => {
    fetchRecentAlerts();
  }, []);

  // Play notification sound
  const playNotificationSound = () => {
    try {
      // Create a simple notification sound using Web Audio API
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
      oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1);
      
      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
      
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.3);
    } catch (error) {
      console.log('Audio notification not available');
    }
  };

  const acknowledgeAlert = (alertId: string) => {
    const success = sendMessage({
      type: 'acknowledge_alert',
      alert_id: alertId
    });
    
    if (success) {
      setAlerts(prev => 
        prev.map(alert => 
          alert.id === alertId 
            ? { ...alert, acknowledged_at: new Date().toISOString() }
            : alert
        )
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    }
  };

  const clearAllAlerts = () => {
    setAlerts([]);
    setUnreadCount(0);
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-gradient-to-r from-red-50 to-red-100 dark:from-red-900/30 dark:to-red-900/20 border-l-4 border-red-500 dark:border-red-600 text-red-900 dark:text-red-300 shadow-red-100 dark:shadow-red-900/20';
      case 'high': return 'bg-gradient-to-r from-orange-50 to-orange-100 dark:from-orange-900/30 dark:to-orange-900/20 border-l-4 border-orange-500 dark:border-orange-600 text-orange-900 dark:text-orange-300 shadow-orange-100 dark:shadow-orange-900/20';
      case 'medium': return 'bg-gradient-to-r from-yellow-50 to-yellow-100 dark:from-yellow-900/30 dark:to-yellow-900/20 border-l-4 border-yellow-500 dark:border-yellow-600 text-yellow-900 dark:text-yellow-300 shadow-yellow-100 dark:shadow-yellow-900/20';
      case 'low': return 'bg-gradient-to-r from-blue-50 to-blue-100 dark:from-blue-900/30 dark:to-blue-900/20 border-l-4 border-blue-500 dark:border-blue-600 text-blue-900 dark:text-blue-300 shadow-blue-100 dark:shadow-blue-900/20';
      default: return 'bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-900/30 dark:to-gray-900/20 border-l-4 border-gray-500 dark:border-gray-600 text-gray-900 dark:text-gray-300 shadow-gray-100 dark:shadow-gray-900/20';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical': return '🚨';
      case 'high': return '⚠️';
      case 'medium': return '📊';
      case 'low': return 'ℹ️';
      default: return '📢';
    }
  };

  const getSeverityBadgeColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500 dark:bg-red-600 text-white';
      case 'high': return 'bg-orange-500 dark:bg-orange-600 text-white';
      case 'medium': return 'bg-yellow-500 dark:bg-yellow-600 text-yellow-900 dark:text-yellow-100';
      case 'low': return 'bg-blue-500 dark:bg-blue-600 text-white';
      default: return 'bg-gray-500 dark:bg-gray-600 text-white';
    }
  };

  const getAlertTypeIcon = (alertType: string) => {
    switch (alertType) {
      case 'momentum_breakout': return '📈';
      case 'sentiment_spike': return '💭';
      case 'wsb_viral': return '🚀';
      case 'volume_spike': return '📊';
      case 'strong_signal': return '⚡';
      case 'retail_buzz': return '👥';
      case 'breaking_news': return '📰';
      case 'sentiment_momentum_divergence': return '🔄';
      default: return '🔔';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div
      ref={containerRef}
      className={`fixed z-30 w-80 max-w-sm ${isDragging ? 'cursor-grabbing' : ''} select-none`}
      style={{ top: position.y, left: position.x }}
    >
      {/* Header */}
      <div className={`bg-white/95 dark:bg-neutral-800/95 backdrop-blur-sm border border-gray-200/50 dark:border-neutral-700/50 rounded-t-xl shadow-xl transition-all duration-300 ${
        showNewAlertAnimation ? 'animate-pulse shadow-2xl' : ''
      }`}>
        <div
          className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-neutral-700 cursor-move"
          onMouseDown={onHeaderMouseDown}
          onTouchStart={onHeaderTouchStart}
        >
          <div className="flex items-center space-x-3">
            <div className="relative float">
              <div className={`w-3 h-3 rounded-full transition-all duration-300 ${
                isConnected ? 'bg-green-500 dark:bg-green-400 shadow-green-200 dark:shadow-green-900 pulse-green' : 'bg-red-500 dark:bg-red-400 shadow-red-200 dark:shadow-red-900'
              }`}></div>
              {isConnected && (
                <div className="absolute inset-0 w-3 h-3 rounded-full bg-green-500 dark:bg-green-400 animate-ping opacity-75"></div>
              )}
            </div>
            <h3 className="font-bold text-gray-900 dark:text-white text-lg tracking-tight">Live Alerts</h3>
            {unreadCount > 0 && (
              <div className="relative">
                <span className="bg-gradient-to-r from-red-500 to-red-600 text-white text-xs font-bold px-2.5 py-1 rounded-full shadow-lg animate-bounce">
                  {unreadCount}
                </span>
              </div>
            )}
          </div>
          
          <div className="flex items-center space-x-1">
            {!isConnected && (
              <button
                onClick={reconnect}
                className="text-gray-400 dark:text-neutral-400 hover:text-blue-500 text-sm font-medium px-2 py-1 rounded-md hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-all duration-200"
                title="Reconnect to server"
              >
                🔄
              </button>
            )}
            <button
              onClick={clearAllAlerts}
              className="text-gray-400 dark:text-neutral-400 hover:text-red-500 text-sm font-medium px-2 py-1 rounded-md hover:bg-red-50 dark:hover:bg-red-900/30 transition-all duration-200"
              title="Clear all alerts"
            >
              Clear
            </button>
            <button
              onClick={() => setIsMinimized(!isMinimized)}
              className="text-gray-400 dark:text-neutral-400 hover:text-gray-600 dark:hover:text-neutral-200 p-1 rounded-md hover:bg-gray-100 dark:hover:bg-neutral-700 transition-all duration-200"
            >
              <svg className={`w-4 h-4 transition-transform duration-200 ${isMinimized ? 'rotate-180' : ''}`} fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
        
        {/* Connection Status */}
        {connectionError && (
          <div className="p-3 bg-gradient-to-r from-red-50 to-red-100 dark:from-red-900/30 dark:to-red-900/20 border-b border-red-200 dark:border-red-700">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="text-red-500 dark:text-red-400">⚠️</span>
                <p className="text-red-700 dark:text-red-400 text-sm font-medium">
                  {formatErrorForDisplay(connectionError, { showTechnicalDetails: false })}
                </p>
              </div>
              <button
                onClick={reconnect}
                className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 text-xs font-medium px-2 py-1 rounded bg-red-100 dark:bg-red-900/40 hover:bg-red-200 dark:hover:bg-red-900/60 transition-colors"
                title="Retry connection"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Connection Status Indicator */}
        {!connectionError && (
          <div className="px-4 py-2 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/30 dark:to-emerald-900/20 border-b border-green-100 dark:border-green-700">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-green-400 dark:bg-green-500 rounded-full animate-pulse"></div>
              <p className="text-green-700 dark:text-green-400 text-xs font-medium">
                {isConnected ? 'Connected to live market data' : 'Connecting...'}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Alerts List */}
      <div className={`transition-all duration-300 ease-in-out overflow-hidden ${
        isMinimized ? 'max-h-0' : 'max-h-96'
      }`}>
        <div className="bg-white/95 dark:bg-neutral-800/95 backdrop-blur-sm border-x border-b border-gray-200/50 dark:border-neutral-700/50 rounded-b-xl shadow-xl overflow-y-auto max-h-96 alerts-scroll">
          {alerts.length === 0 ? (
            <div className="p-8 text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-blue-900/30 dark:to-indigo-900/30 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-blue-500 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-5 5-5-5h5V3h0z" />
                </svg>
              </div>
              <p className="text-gray-600 dark:text-neutral-400 font-medium mb-2">
                {isLoadingAlerts ? "Loading alerts..." : "No alerts yet"}
              </p>
              <p className="text-gray-400 dark:text-neutral-500 text-sm">
                {isLoadingAlerts
                  ? "Fetching recent alerts..."
                  : isConnected
                    ? "Monitoring real-time market data..."
                    : "Establishing connection..."
                }
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-neutral-700">
              {alerts.map((alert, index) => (
                <div
                  key={alert.id}
                  className={`p-4 transition-all duration-500 hover:bg-gray-50 dark:hover:bg-neutral-700 ${getSeverityColor(alert.severity)} ${
                    alert.acknowledged_at ? 'opacity-50 scale-95' : 'transform hover:scale-[1.02]'
                  } ${index === 0 && showNewAlertAnimation ? 'alert-shake' : ''} ${
                    index === 0 ? 'alert-slide-in' : ''
                  }`}
                  style={{
                    animationDelay: `${index * 100}ms`,
                  }}
                >
                  <div className="flex items-start justify-between space-x-3">
                    <div className="flex-1 min-w-0">
                      {/* Alert Header */}
                      <div className="flex items-center space-x-2 mb-2">
                        <span className="text-xl">{getSeverityIcon(alert.severity)}</span>
                        <span className="text-lg">{getAlertTypeIcon(alert.alert_type)}</span>
                        <span className="font-bold text-sm bg-black/10 dark:bg-white/10 px-2 py-1 rounded-md">
                          {alert.ticker}
                        </span>
                        <span className={`text-xs font-bold px-2 py-1 rounded-full ${getSeverityBadgeColor(alert.severity)}`}>
                          {alert.severity.toUpperCase()}
                        </span>
                      </div>
                      
                      {/* Alert Content */}
                      <h4 className="font-bold text-base mb-2 leading-tight">{alert.title}</h4>
                      <p className="text-sm leading-relaxed mb-3 text-gray-700 dark:text-neutral-300">{alert.message}</p>
                      
                      {/* Alert Footer */}
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center space-x-2">
                          <svg className="w-3 h-3 text-gray-400 dark:text-neutral-500" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                          </svg>
                          <span className="text-gray-600 dark:text-neutral-400 font-medium">{formatTime(alert.triggered_at)}</span>
                        </div>
                        <span className="capitalize text-gray-500 dark:text-neutral-400 font-medium bg-gray-100 dark:bg-neutral-700 px-2 py-1 rounded-md">
                          {alert.alert_type.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                    
                    {/* Action Button */}
                    {!alert.acknowledged_at && (
                      <button
                        onClick={() => acknowledgeAlert(alert.id)}
                        className="flex-shrink-0 ml-3 bg-white/80 dark:bg-neutral-700/80 hover:bg-white dark:hover:bg-neutral-600 text-gray-600 dark:text-neutral-300 hover:text-green-600 dark:hover:text-green-400 p-2 rounded-lg shadow-sm hover:shadow-md transition-all duration-200 group"
                        title="Acknowledge alert"
                      >
                        <svg className="w-4 h-4 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </button>
                    )}

                    {alert.acknowledged_at && (
                      <div className="flex-shrink-0 ml-3 text-green-500 dark:text-green-400 p-2">
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Error Toast for API errors */}
      {apiError && (
        <ErrorToast
          error={apiError}
          onDismiss={() => setApiError(null)}
          onRetry={() => {
            setApiError(null);
            fetchRecentAlerts();
          }}
          autoHide={true}
          autoHideDelay={10000}
        />
      )}
    </div>
  );
};

export default RealTimeAlerts;
