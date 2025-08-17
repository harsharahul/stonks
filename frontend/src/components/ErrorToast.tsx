/**
 * Enhanced Error Toast Component
 * 
 * Provides user-friendly error notifications with actions and auto-dismissal.
 */

import React, { useEffect, useState } from 'react';
import { ApiError, WebSocketError, formatErrorForDisplay, isRecoverableError } from '../utils/errorHandling';

interface ErrorToastProps {
  error: ApiError | WebSocketError;
  onDismiss: () => void;
  onRetry?: () => void;
  autoHide?: boolean;
  autoHideDelay?: number;
  showTechnicalDetails?: boolean;
}

const ErrorToast: React.FC<ErrorToastProps> = ({
  error,
  onDismiss,
  onRetry,
  autoHide = true,
  autoHideDelay = 8000,
  showTechnicalDetails = false
}) => {
  const [isVisible, setIsVisible] = useState(true);
  const [showDetails, setShowDetails] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(autoHide ? autoHideDelay / 1000 : 0);

  useEffect(() => {
    if (!autoHide) return;

    const interval = setInterval(() => {
      setTimeRemaining(prev => {
        if (prev <= 1) {
          handleDismiss();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [autoHide, autoHideDelay]);

  const handleDismiss = () => {
    setIsVisible(false);
    setTimeout(() => onDismiss(), 300); // Allow animation to complete
  };

  const handleRetry = () => {
    if (onRetry) {
      onRetry();
    }
    handleDismiss();
  };

  const getErrorIcon = () => {
    if ('type' in error) {
      // WebSocket error
      switch (error.type) {
        case 'connection':
          return '🔌';
        case 'timeout':
          return '⏱️';
        case 'protocol':
          return '⚠️';
        default:
          return '❌';
      }
    }

    // API error
    switch (error.error_code) {
      case 'NETWORK_ERROR':
        return '🌐';
      case 'VALIDATION_ERROR':
        return '📝';
      case 'RATE_LIMIT_EXCEEDED':
        return '🚦';
      case 'DATA_NOT_FOUND':
        return '🔍';
      default:
        return '❌';
    }
  };

  const getErrorTheme = () => {
    const recoverable = isRecoverableError(error);
    
    if (recoverable) {
      return {
        background: 'bg-gradient-to-r from-orange-50 to-orange-100',
        border: 'border-l-4 border-orange-500',
        text: 'text-orange-900',
        button: 'bg-orange-500 hover:bg-orange-600 text-white'
      };
    }

    return {
      background: 'bg-gradient-to-r from-red-50 to-red-100',
      border: 'border-l-4 border-red-500',
      text: 'text-red-900',
      button: 'bg-red-500 hover:bg-red-600 text-white'
    };
  };

  const theme = getErrorTheme();
  const message = formatErrorForDisplay(error, { 
    showTechnicalDetails: showDetails,
    showSupportInfo: false 
  });

  if (!isVisible) {
    return null;
  }

  return (
    <div className={`
      fixed top-4 right-4 z-50 max-w-md w-full
      transform transition-all duration-300 ease-in-out
      ${isVisible ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0'}
    `}>
      <div className={`
        ${theme.background} ${theme.border} ${theme.text}
        rounded-lg shadow-lg p-4 relative overflow-hidden
      `}>
        {/* Auto-hide progress bar */}
        {autoHide && timeRemaining > 0 && (
          <div className="absolute top-0 left-0 h-1 bg-gray-300 w-full">
            <div 
              className="h-full bg-gray-600 transition-all duration-1000 ease-linear"
              style={{ 
                width: `${(timeRemaining / (autoHideDelay / 1000)) * 100}%` 
              }}
            />
          </div>
        )}

        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center space-x-2">
            <span className="text-xl">{getErrorIcon()}</span>
            <h3 className="font-bold text-lg">
              {isRecoverableError(error) ? 'Connection Issue' : 'Error'}
            </h3>
          </div>
          
          <div className="flex items-center space-x-1">
            {autoHide && timeRemaining > 0 && (
              <span className="text-xs font-medium opacity-70">
                {timeRemaining}s
              </span>
            )}
            <button
              onClick={handleDismiss}
              className="text-gray-500 hover:text-gray-700 p-1 rounded transition-colors"
              title="Dismiss"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>

        {/* Error Message */}
        <div className="mb-4">
          <p className="text-sm leading-relaxed whitespace-pre-line">
            {message}
          </p>
          
          {/* Technical Details Toggle */}
          {showTechnicalDetails && 'technical_message' in error && error.technical_message && (
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="text-xs underline mt-2 hover:no-underline"
            >
              {showDetails ? 'Hide' : 'Show'} technical details
            </button>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <div className="flex space-x-2">
            {isRecoverableError(error) && onRetry && (
              <button
                onClick={handleRetry}
                className={`
                  ${theme.button}
                  px-3 py-1 rounded text-sm font-medium
                  transition-colors duration-200
                  flex items-center space-x-1
                `}
              >
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
                </svg>
                <span>Retry</span>
              </button>
            )}
            
            <button
              onClick={handleDismiss}
              className="px-3 py-1 bg-gray-500 hover:bg-gray-600 text-white rounded text-sm font-medium transition-colors duration-200"
            >
              Dismiss
            </button>
          </div>
          
          {/* Support Info */}
          {'support_message' in error && error.support_message && (
            <div className="text-xs opacity-70 max-w-xs">
              {error.support_message}
            </div>
          )}
        </div>

        {/* Error Code for Support */}
        <div className="mt-3 pt-2 border-t border-gray-300 text-xs opacity-60">
          Error Code: {error.error_code}
          {'timestamp' in error && (
            <span className="ml-2">
              • {new Date(error.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ErrorToast;
