/**
 * Toast Notification Component
 * 
 * Provides user-friendly notifications for success, error, and info messages.
 */

import React, { useEffect, useState } from 'react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastProps {
  id: string;
  type: ToastType;
  title: string;
  message: string;
  onDismiss: (id: string) => void;
  autoHide?: boolean;
  autoHideDelay?: number;
  showIcon?: boolean;
}

const Toast: React.FC<ToastProps> = ({
  id,
  type,
  title,
  message,
  onDismiss,
  autoHide = true,
  autoHideDelay = 5000,
  showIcon = true
}) => {
  const [isVisible, setIsVisible] = useState(true);
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
    setTimeout(() => onDismiss(id), 300); // Allow animation to complete
  };

  const getToastTheme = () => {
    switch (type) {
      case 'success':
        return {
          background: 'bg-gradient-to-r from-green-50 to-green-100 dark:from-green-900/40 dark:to-green-800/40',
          border: 'border-l-4 border-green-500',
          text: 'text-green-900 dark:text-green-200',
          icon: '✅',
          progress: 'bg-green-500'
        };
      case 'error':
        return {
          background: 'bg-gradient-to-r from-red-50 to-red-100 dark:from-red-900/40 dark:to-red-800/40',
          border: 'border-l-4 border-red-500',
          text: 'text-red-900 dark:text-red-200',
          icon: '❌',
          progress: 'bg-red-500'
        };
      case 'warning':
        return {
          background: 'bg-gradient-to-r from-yellow-50 to-yellow-100 dark:from-yellow-900/40 dark:to-yellow-800/40',
          border: 'border-l-4 border-yellow-500',
          text: 'text-yellow-900 dark:text-yellow-200',
          icon: '⚠️',
          progress: 'bg-yellow-500'
        };
      case 'info':
      default:
        return {
          background: 'bg-gradient-to-r from-blue-50 to-blue-100 dark:from-blue-900/40 dark:to-blue-800/40',
          border: 'border-l-4 border-blue-500',
          text: 'text-blue-900 dark:text-blue-200',
          icon: 'ℹ️',
          progress: 'bg-blue-500'
        };
    }
  };

  const theme = getToastTheme();

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
          <div className="absolute top-0 left-0 h-1 bg-gray-300 dark:bg-neutral-600 w-full">
            <div 
              className={`h-full ${theme.progress} transition-all duration-1000 ease-linear`}
              style={{ 
                width: `${(timeRemaining / (autoHideDelay / 1000)) * 100}%` 
              }}
            />
          </div>
        )}

        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center space-x-2">
            {showIcon && (
              <span className="text-xl">{theme.icon}</span>
            )}
            <h3 className="font-bold text-lg">{title}</h3>
          </div>
          
          <div className="flex items-center space-x-1">
            {autoHide && timeRemaining > 0 && (
              <span className="text-xs font-medium opacity-70">
                {timeRemaining}s
              </span>
            )}
            <button
              onClick={handleDismiss}
              className="text-gray-500 dark:text-neutral-400 hover:text-gray-700 dark:hover:text-neutral-200 p-1 rounded transition-colors"
              title="Dismiss"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>

        {/* Message */}
        <div className="mb-4">
          <p className="text-sm leading-relaxed whitespace-pre-line">
            {message}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end">
          <button
            onClick={handleDismiss}
            className="px-3 py-1 bg-gray-500 dark:bg-neutral-600 hover:bg-gray-600 dark:hover:bg-neutral-500 text-white rounded text-sm font-medium transition-colors duration-200"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
};

export default Toast;
