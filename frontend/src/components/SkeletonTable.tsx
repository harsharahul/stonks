import React from 'react';
import { cn } from '../utils/format';

interface SkeletonTableProps {
  rows?: number;
  columns?: number;
  className?: string;
}

const SkeletonTable: React.FC<SkeletonTableProps> = ({ rows = 6, columns = 6, className }) => (
  <div className={cn('animate-pulse', className)}>
    {/* Header row */}
    <div className="flex gap-3 px-4 py-3 bg-neutral-100 dark:bg-neutral-800 rounded-t-lg">
      {Array.from({ length: columns }).map((_, i) => (
        <div key={i} className="h-3 bg-neutral-300 dark:bg-neutral-600 rounded flex-1" />
      ))}
    </div>
    {/* Body rows */}
    {Array.from({ length: rows }).map((_, r) => (
      <div key={r} className="flex gap-3 px-4 py-3 border-b border-neutral-100 dark:border-neutral-700">
        {Array.from({ length: columns }).map((_, c) => (
          <div
            key={c}
            className={cn(
              'h-3 bg-neutral-200 dark:bg-neutral-600 rounded flex-1',
              c === 0 && 'max-w-[60px]',
              c === columns - 1 && 'max-w-[40px]',
            )}
          />
        ))}
      </div>
    ))}
  </div>
);

export default SkeletonTable;
