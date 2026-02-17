import React from 'react';
import { formatDistanceToNow } from 'date-fns';
import { cn } from '../utils/format';

interface FreshnessIndicatorProps {
  dataUpdatedAt: number | undefined;
  expectedIntervalMinutes: number;
  label?: string;
  className?: string;
}

const FreshnessIndicator: React.FC<FreshnessIndicatorProps> = ({
  dataUpdatedAt,
  expectedIntervalMinutes,
  label,
  className,
}) => {
  if (!dataUpdatedAt) return null;

  const ageMs = Date.now() - dataUpdatedAt;
  const expectedMs = expectedIntervalMinutes * 60 * 1000;

  let dotColor = 'bg-emerald-500';
  let textColor = 'text-neutral-500 dark:text-neutral-400';
  let prefix = '';

  if (ageMs > expectedMs * 2) {
    dotColor = 'bg-red-500';
    textColor = 'text-red-600 dark:text-red-400';
    prefix = 'Stale: ';
  } else if (ageMs > expectedMs) {
    dotColor = 'bg-amber-500';
    textColor = 'text-amber-600 dark:text-amber-400';
  }

  const timeAgo = formatDistanceToNow(new Date(dataUpdatedAt), { addSuffix: true });

  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs', textColor, className)}>
      <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', dotColor)} />
      {label && <span className="font-medium">{label}</span>}
      {prefix}{timeAgo}
    </span>
  );
};

export default FreshnessIndicator;
