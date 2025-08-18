/**
 * Toast Manager Component
 * 
 * Manages multiple toast notifications with stacking and auto-dismissal.
 */

import React, { useState, useCallback } from 'react';
import Toast, { ToastType } from './Toast';

export interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  message: string;
  autoHide?: boolean;
  autoHideDelay?: number;
}

interface ToastManagerProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

const ToastManager: React.FC<ToastManagerProps> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) {
    return null;
  }

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2">
      {toasts.map((toast, index) => (
        <div
          key={toast.id}
          className="transform transition-all duration-300 ease-in-out"
          style={{
            transform: `translateY(${index * 10}px)`,
            zIndex: 50 - index
          }}
        >
          <Toast
            {...toast}
            onDismiss={onDismiss}
          />
        </div>
      ))}
    </div>
  );
};

export default ToastManager;
