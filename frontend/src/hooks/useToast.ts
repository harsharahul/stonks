/**
 * Custom hook for managing toast notifications
 */

import { useState, useCallback, useRef } from 'react';
import { ToastMessage } from '../components/ToastManager';

export const useToast = () => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const nextId = useRef(1);

  const addToast = useCallback((
    type: ToastMessage['type'],
    title: string,
    message: string,
    options: Partial<Pick<ToastMessage, 'autoHide' | 'autoHideDelay'>> = {}
  ) => {
    const id = `toast-${nextId.current++}`;
    const newToast: ToastMessage = {
      id,
      type,
      title,
      message,
      autoHide: options.autoHide ?? true,
      autoHideDelay: options.autoHideDelay ?? 5000
    };

    setToasts(prev => [...prev, newToast]);

    // Auto-remove toast after delay if autoHide is enabled
    if (newToast.autoHide) {
      setTimeout(() => {
        removeToast(id);
      }, newToast.autoHideDelay);
    }

    return id;
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  const clearAllToasts = useCallback(() => {
    setToasts([]);
  }, []);

  // Convenience methods
  const showSuccess = useCallback((title: string, message: string, options?: Partial<Pick<ToastMessage, 'autoHide' | 'autoHideDelay'>>) => {
    return addToast('success', title, message, options);
  }, [addToast]);

  const showError = useCallback((title: string, message: string, options?: Partial<Pick<ToastMessage, 'autoHide' | 'autoHideDelay'>>) => {
    return addToast('error', title, message, options);
  }, [addToast]);

  const showInfo = useCallback((title: string, message: string, options?: Partial<Pick<ToastMessage, 'autoHide' | 'autoHideDelay'>>) => {
    return addToast('info', title, message, options);
  }, [addToast]);

  const showWarning = useCallback((title: string, message: string, options?: Partial<Pick<ToastMessage, 'autoHide' | 'autoHideDelay'>>) => {
    return addToast('warning', title, message, options);
  }, [addToast]);

  return {
    toasts,
    addToast,
    removeToast,
    clearAllToasts,
    showSuccess,
    showError,
    showInfo,
    showWarning
  };
};
