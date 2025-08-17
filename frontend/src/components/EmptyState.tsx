import React from 'react';
import { cn } from '../utils/format';

interface EmptyStateProps {
  title?: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
  height?: number;
}

const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No data available',
  message = 'Data will appear here when available.',
  actionLabel,
  onAction,
  className,
  height = 300,
}) => {
  return (
    <div 
      className={cn('flex items-center justify-center bg-neutral-50 rounded border-2 border-dashed border-neutral-200', className)}
      style={{ height }}
    >
      <div className="text-center px-4">
        <svg
          className="mx-auto h-12 w-12 text-neutral-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-neutral-900">{title}</h3>
        <p className="mt-1 text-sm text-neutral-500">{message}</p>
        {actionLabel && onAction && (
          <button onClick={onAction} className="btn-primary mt-3">
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
};

export default EmptyState;


