/**
 * Real-Time Alerts Component
 * 
 * Displays live alerts and notifications using WebSocket connection
 */

import React, { useState, useEffect } from 'react';
import { useAlertsWebSocket, WebSocketMessage } from '../hooks/useWebSocket';

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

  const { isConnected, lastMessage, connectionError, sendMessage } = useAlertsWebSocket(
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
      },
      onDisconnect: () => {
        console.log('Disconnected from alerts WebSocket');
      }
    }
  );

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
      case 'critical': return 'bg-red-100 border-red-500 text-red-800';
      case 'high': return 'bg-orange-100 border-orange-500 text-orange-800';
      case 'medium': return 'bg-yellow-100 border-yellow-500 text-yellow-800';
      case 'low': return 'bg-blue-100 border-blue-500 text-blue-800';
      default: return 'bg-gray-100 border-gray-500 text-gray-800';
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
    <div className="fixed top-4 right-4 z-50 w-96">
      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-t-lg shadow-lg">
        <div className="flex items-center justify-between p-3 border-b border-gray-200">
          <div className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <h3 className="font-semibold text-gray-900">Live Alerts</h3>
            {unreadCount > 0 && (
              <span className="bg-red-500 text-white text-xs px-2 py-1 rounded-full">
                {unreadCount}
              </span>
            )}
          </div>
          
          <div className="flex items-center space-x-2">
            <button
              onClick={clearAllAlerts}
              className="text-gray-500 hover:text-gray-700 text-sm"
              title="Clear all alerts"
            >
              Clear
            </button>
            <button
              onClick={() => setIsMinimized(!isMinimized)}
              className="text-gray-500 hover:text-gray-700"
            >
              {isMinimized ? '▲' : '▼'}
            </button>
          </div>
        </div>
        
        {/* Connection Status */}
        {connectionError && (
          <div className="p-2 bg-red-50 border-b border-red-200">
            <p className="text-red-600 text-sm">⚠️ {connectionError}</p>
          </div>
        )}
      </div>

      {/* Alerts List */}
      {!isMinimized && (
        <div className="bg-white border-x border-b border-gray-200 rounded-b-lg shadow-lg max-h-96 overflow-y-auto">
          {alerts.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              <p>No alerts yet</p>
              <p className="text-sm mt-1">
                {isConnected ? 'Listening for real-time alerts...' : 'Connecting...'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`p-3 ${getSeverityColor(alert.severity)} ${
                    alert.acknowledged_at ? 'opacity-60' : ''
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        <span className="text-lg">{getSeverityIcon(alert.severity)}</span>
                        <span className="font-medium text-sm">{alert.ticker}</span>
                        <span className="text-xs px-2 py-1 bg-white bg-opacity-50 rounded">
                          {alert.severity.toUpperCase()}
                        </span>
                      </div>
                      
                      <h4 className="font-semibold text-sm mb-1">{alert.title}</h4>
                      <p className="text-sm mb-2">{alert.message}</p>
                      
                      <div className="flex items-center justify-between text-xs">
                        <span>{formatTime(alert.triggered_at)}</span>
                        <span className="capitalize">{alert.alert_type.replace('_', ' ')}</span>
                      </div>
                    </div>
                    
                    {!alert.acknowledged_at && (
                      <button
                        onClick={() => acknowledgeAlert(alert.id)}
                        className="ml-2 text-xs px-2 py-1 bg-white bg-opacity-70 hover:bg-opacity-90 rounded transition-colors"
                        title="Acknowledge alert"
                      >
                        ✓
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default RealTimeAlerts;
