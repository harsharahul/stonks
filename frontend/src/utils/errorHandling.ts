/**
 * Enhanced Error Handling Utilities for Frontend
 * 
 * Provides consistent error handling, user messaging, and error recovery mechanisms.
 */



export interface ApiError {
  error_code: string;
  message: string;
  technical_message?: string;
  details?: Record<string, any>;
  timestamp: string;
  support_message?: string;
}

export interface WebSocketError {
  type: 'connection' | 'message' | 'timeout' | 'protocol';
  message: string;
  code?: number;
  reason?: string;
  recoverable: boolean;
  retryDelay?: number;
}

export interface ErrorDisplayOptions {
  showTechnicalDetails?: boolean;
  showSupportInfo?: boolean;
  autoHide?: boolean;
  autoHideDelay?: number;
}

/**
 * Parse API error response into a standardized format
 */
export const parseApiError = (error: any): ApiError => {
  // Check if it's already a formatted error
  if (error.response?.data && error.response.data.error_code) {
    return error.response.data as ApiError;
  }

  // Handle axios errors
  if (error.response) {
    const status = error.response.status;
    const data = error.response.data;

    // Handle FastAPI validation errors
    if (status === 422 && data.detail) {
      return {
        error_code: 'VALIDATION_ERROR',
        message: 'Please check your input data.',
        technical_message: Array.isArray(data.detail) 
          ? data.detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join(', ')
          : data.detail,
        details: { validation_errors: data.detail },
        timestamp: new Date().toISOString(),
        support_message: 'Please review the highlighted fields and correct any errors.'
      };
    }

    // Handle other HTTP errors
    return {
      error_code: `HTTP_${status}`,
      message: getUserFriendlyMessage(status, data?.detail || data?.message),
      technical_message: data?.detail || data?.message || error.message,
      details: { status, response_data: data },
      timestamp: new Date().toISOString(),
      support_message: status >= 500 
        ? 'Our team has been notified. Please try again later.'
        : 'Please check your request and try again.'
    };
  }

  // Handle network errors
  if (error.request) {
    return {
      error_code: 'NETWORK_ERROR',
      message: 'Unable to connect to server. Please check your internet connection.',
      technical_message: 'Network request failed',
      details: { network_error: true },
      timestamp: new Date().toISOString(),
      support_message: 'Please verify your internet connection and try again.'
    };
  }

  // Handle unknown errors
  return {
    error_code: 'UNKNOWN_ERROR',
    message: 'An unexpected error occurred.',
    technical_message: error.message || 'Unknown error',
    details: { original_error: error },
    timestamp: new Date().toISOString(),
    support_message: 'Please refresh the page and try again.'
  };
};

/**
 * Get user-friendly message based on HTTP status code
 */
const getUserFriendlyMessage = (status: number, originalMessage?: string): string => {
  const statusMessages: Record<number, string> = {
    400: 'Invalid request. Please check your input.',
    401: 'Please log in to access this feature.',
    403: 'You don\'t have permission to perform this action.',
    404: 'The requested information was not found.',
    409: 'This action conflicts with existing data.',
    429: 'Too many requests. Please wait a moment and try again.',
    500: 'Server error. Our team has been notified.',
    502: 'Service temporarily unavailable. Please try again.',
    503: 'Service is temporarily down for maintenance.',
    504: 'Request timeout. Please try again.'
  };

  return statusMessages[status] || originalMessage || 'An error occurred';
};

/**
 * Analyze WebSocket error and provide recovery guidance
 */
export const analyzeWebSocketError = (
  event: CloseEvent | Event,
  connectionState: 'connecting' | 'open' | 'closing' | 'closed'
): WebSocketError => {
  if (event instanceof CloseEvent) {
    const { code, reason, wasClean } = event;

    // WebSocket close codes and their meanings
    switch (code) {
      case 1000:
        return {
          type: 'connection',
          message: 'Connection closed normally',
          code,
          reason,
          recoverable: false
        };

      case 1001:
        return {
          type: 'connection',
          message: 'Server is going away',
          code,
          reason,
          recoverable: true,
          retryDelay: 5000
        };

      case 1006:
        return {
          type: 'connection',
          message: 'Connection lost unexpectedly',
          code,
          reason: 'Network interruption or server restart',
          recoverable: true,
          retryDelay: 2000
        };

      case 1011:
        return {
          type: 'protocol',
          message: 'Server encountered an error',
          code,
          reason,
          recoverable: true,
          retryDelay: 10000
        };

      case 1012:
        return {
          type: 'connection',
          message: 'Server is restarting',
          code,
          reason,
          recoverable: true,
          retryDelay: 15000
        };

      default:
        return {
          type: 'connection',
          message: `Connection closed with code ${code}`,
          code,
          reason: reason || 'Unknown reason',
          recoverable: code >= 1000 && code < 1016,
          retryDelay: 5000
        };
    }
  }

  // Handle other WebSocket errors
  return {
    type: 'connection',
    message: 'WebSocket connection error',
    recoverable: true,
    retryDelay: 3000
  };
};

/**
 * Format error for display to user
 */
export const formatErrorForDisplay = (
  error: ApiError | WebSocketError,
  options: ErrorDisplayOptions = {}
): string => {
  const {
    showTechnicalDetails = false,
    showSupportInfo = true
  } = options;

  let message = error.message;

  if (showTechnicalDetails && 'technical_message' in error && error.technical_message) {
    message += `\n\nTechnical details: ${error.technical_message}`;
  }

  if (showSupportInfo && 'support_message' in error && error.support_message) {
    message += `\n\n${error.support_message}`;
  }

  return message;
};

/**
 * Check if error is recoverable (user can retry)
 */
export const isRecoverableError = (error: ApiError | WebSocketError): boolean => {
  if ('recoverable' in error) {
    return error.recoverable;
  }

  const recoverableErrorCodes = [
    'NETWORK_ERROR',
    'WEBSOCKET_ERROR',
    'RATE_LIMIT_EXCEEDED',
    'SERVICE_UNAVAILABLE',
    'DATABASE_UNAVAILABLE',
    'EXTERNAL_SERVICE_ERROR'
  ];

  return recoverableErrorCodes.includes(error.error_code);
};

/**
 * Get recommended retry delay for recoverable errors
 */
export const getRetryDelay = (error: ApiError | WebSocketError, attemptNumber: number = 1): number => {
  if ('retryDelay' in error && error.retryDelay) {
    return error.retryDelay;
  }

  // Exponential backoff with jitter
  const baseDelay = 1000;
  const maxDelay = 30000;
  const delay = Math.min(baseDelay * Math.pow(2, attemptNumber - 1), maxDelay);
  const jitter = Math.random() * 1000;
  
  return delay + jitter;
};



/**
 * Utility to safely execute async operations with error handling
 */
export const safeAsyncOperation = async <T>(
  operation: () => Promise<T>,
  onError?: (error: ApiError) => void,
  maxRetries: number = 0
): Promise<T | null> => {
  let lastError: ApiError | null = null;

  for (let attempt = 1; attempt <= maxRetries + 1; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = parseApiError(error);
      
      // Don't retry if error is not recoverable or we've reached max retries
      if (!isRecoverableError(lastError) || attempt > maxRetries) {
        break;
      }

      // Wait before retrying
      const delay = getRetryDelay(lastError, attempt);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  if (onError && lastError) {
    onError(lastError);
  }

  return null;
};

/**
 * Create a toast notification for errors
 */
export const createErrorToast = (error: ApiError | WebSocketError, options: ErrorDisplayOptions = {}) => {
  const message = formatErrorForDisplay(error, options);
  
  return {
    id: `error-${Date.now()}`,
    type: 'error' as const,
    title: 'Error',
    message,
    duration: options.autoHide ? (options.autoHideDelay || 8000) : 0,
    actions: isRecoverableError(error) ? [
      {
        label: 'Retry',
        action: () => window.location.reload()
      }
    ] : undefined
  };
};
