import { format, formatDistanceToNow, parseISO } from 'date-fns';
import clsx, { ClassValue } from 'clsx';

// CSS class utility
export const cn = (...inputs: ClassValue[]) => {
  return clsx(inputs);
};

// Number formatting utilities
export const formatPercent = (value: number | null, decimals: number = 2): string => {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(decimals)}%`;
};

export const formatCurrency = (value: number | null, currency: string = 'USD'): string => {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
};

export const formatNumber = (value: number | null, decimals: number = 2): string => {
  if (value === null || value === undefined) return '—';
  return value.toFixed(decimals);
};

export const formatLargeNumber = (value: number | null): string => {
  if (value === null || value === undefined) return '—';
  
  if (value >= 1e9) {
    return `${(value / 1e9).toFixed(1)}B`;
  }
  if (value >= 1e6) {
    return `${(value / 1e6).toFixed(1)}M`;
  }
  if (value >= 1e3) {
    return `${(value / 1e3).toFixed(1)}K`;
  }
  return value.toString();
};

// Date formatting utilities
export const formatDate = (dateString: string | null): string => {
  if (!dateString) return '—';
  try {
    return format(parseISO(dateString), 'MMM d, yyyy');
  } catch {
    return '—';
  }
};

export const formatDateTime = (dateString: string | null): string => {
  if (!dateString) return '—';
  try {
    return format(parseISO(dateString), 'MMM d, yyyy h:mm a');
  } catch {
    return '—';
  }
};

export const formatRelativeTime = (dateString: string | null): string => {
  if (!dateString) return '—';
  try {
    return formatDistanceToNow(parseISO(dateString), { addSuffix: true });
  } catch {
    return '—';
  }
};

// Sentiment and metrics utilities
export const getSentimentColor = (sentiment: number | null): string => {
  if (sentiment === null || sentiment === undefined) return 'text-neutral-500';
  
  if (sentiment > 0.6) return 'text-success-600';
  if (sentiment > 0.4) return 'text-neutral-600';
  return 'text-danger-600';
};

export const getSentimentLabel = (sentiment: number | null): string => {
  if (sentiment === null || sentiment === undefined) return 'Neutral';
  
  if (sentiment > 0.7) return 'Very Positive';
  if (sentiment > 0.6) return 'Positive';
  if (sentiment > 0.4) return 'Neutral';
  if (sentiment > 0.3) return 'Negative';
  return 'Very Negative';
};

export const getReturnColor = (returnValue: number | null): string => {
  if (returnValue === null || returnValue === undefined) return 'text-neutral-500';
  
  if (returnValue > 0) return 'text-success-600';
  if (returnValue < 0) return 'text-danger-600';
  return 'text-neutral-600';
};

export const getReturnBgColor = (returnValue: number | null): string => {
  if (returnValue === null || returnValue === undefined) return 'bg-neutral-50';
  
  if (returnValue > 0) return 'bg-success-50';
  if (returnValue < 0) return 'bg-danger-50';
  return 'bg-neutral-50';
};

// Data validation utilities
export const isValidNumber = (value: any): value is number => {
  return typeof value === 'number' && !isNaN(value) && isFinite(value);
};

export const isValidDate = (dateString: string | null): boolean => {
  if (!dateString) return false;
  try {
    const date = parseISO(dateString);
    return !isNaN(date.getTime());
  } catch {
    return false;
  }
};

// Chart data utilities
export const prepareChartData = (data: any[], xKey: string, yKey: string) => {
  return data
    .filter(item => isValidNumber(item[yKey]) && isValidDate(item[xKey]))
    .map(item => ({
      date: item[xKey],
      value: item[yKey],
      ...item
    }))
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
};

// Signal & strength utilities
export const getStrengthColor = (strength: number): string => {
  const abs = Math.abs(strength);
  if (abs >= 0.7) return strength >= 0 ? 'text-green-600' : 'text-red-600';
  if (abs >= 0.4) return strength >= 0 ? 'text-green-500' : 'text-red-500';
  return 'text-neutral-600';
};

export const getDirectionColor = (direction: string): string => {
  if (direction === 'bullish') return 'bg-green-100 text-green-700 border-green-200';
  if (direction === 'bearish') return 'bg-red-100 text-red-700 border-red-200';
  return 'bg-neutral-100 text-neutral-700 border-neutral-200';
};

export const getSignalTypeLabel = (type: string): string =>
  type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

// Text utilities
export const truncateText = (text: string | null, maxLength: number = 100): string => {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength).trim() + '...';
};

export const highlightTickers = (text: string, tickers: string[]): string => {
  if (!tickers || tickers.length === 0) return text;
  
  let highlighted = text;
  tickers.forEach(ticker => {
    const regex = new RegExp(`\\b${ticker}\\b`, 'gi');
    highlighted = highlighted.replace(regex, `<mark class="bg-blue-100 text-blue-800 px-1 rounded">$&</mark>`);
  });
  
  return highlighted;
};
