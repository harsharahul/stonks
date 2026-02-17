import React from 'react';
import { cn, formatPercent, formatNumber, getSentimentColor, getReturnColor } from '../utils/format';

interface FeatureCardProps {
  title: string;
  value: number | null;
  format?: 'number' | 'percent' | 'sentiment' | 'return';
  subtitle?: string;
  trend?: 'up' | 'down' | 'flat';
  className?: string;
  isLoading?: boolean;
}

const FeatureCard: React.FC<FeatureCardProps> = ({
  title,
  value,
  format = 'number',
  subtitle,
  trend,
  className,
  isLoading = false
}) => {
  const formatValue = (val: number | null) => {
    if (val === null || val === undefined) return '—';
    
    switch (format) {
      case 'percent':
        return formatPercent(val);
      case 'sentiment':
        return formatNumber(val, 3);
      case 'return':
        return formatPercent(val);
      default:
        return formatNumber(val);
    }
  };

  const getValueColor = (val: number | null) => {
    if (val === null || val === undefined) return 'text-neutral-500 dark:text-neutral-400';

    switch (format) {
      case 'sentiment':
        return getSentimentColor(val);
      case 'return':
        return getReturnColor(val);
      case 'percent':
        return val > 0 ? 'text-success-600' : val < 0 ? 'text-danger-600' : 'text-neutral-600 dark:text-neutral-400';
      default:
        return 'text-neutral-900 dark:text-neutral-100';
    }
  };

  const getTrendIcon = () => {
    if (!trend) return null;
    
    switch (trend) {
      case 'up':
        return (
          <svg className="w-4 h-4 text-success-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M3.293 9.707a1 1 0 010-1.414l6-6a1 1 0 011.414 0l6 6a1 1 0 01-1.414 1.414L11 5.414V17a1 1 0 11-2 0V5.414L4.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
          </svg>
        );
      case 'down':
        return (
          <svg className="w-4 h-4 text-danger-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M16.707 10.293a1 1 0 010 1.414l-6 6a1 1 0 01-1.414 0l-6-6a1 1 0 111.414-1.414L9 14.586V3a1 1 0 012 0v11.586l4.293-4.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
        );
      case 'flat':
        return (
          <svg className="w-4 h-4 text-neutral-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
        );
      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <div className={cn('card', className)}>
        <div className="animate-pulse">
          <div className="h-4 bg-neutral-200 dark:bg-neutral-700 rounded w-1/2 mb-2"></div>
          <div className="h-8 bg-neutral-200 dark:bg-neutral-700 rounded w-3/4 mb-1"></div>
          <div className="h-3 bg-neutral-200 dark:bg-neutral-700 rounded w-1/3"></div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('card', className)}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400 mb-1">{title}</p>
          <div className="flex items-center space-x-2">
            <p className={cn('text-2xl font-bold', getValueColor(value))}>
              {formatValue(value)}
            </p>
            {getTrendIcon()}
          </div>
          {subtitle && (
            <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">{subtitle}</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default FeatureCard;
