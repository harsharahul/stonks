import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { cn } from '../utils/format';
import type { DetectedPattern } from '../utils/candlestickPatterns';
import { PATTERN_META } from '../utils/candlestickPatterns';

interface PatternSummaryPanelProps {
  patterns: DetectedPattern[];
  className?: string;
}

const PatternSummaryPanel: React.FC<PatternSummaryPanelProps> = ({ patterns, className }) => {
  const [expanded, setExpanded] = useState(true);

  if (patterns.length === 0) return null;

  const bullish = patterns.filter((p) => p.sentiment === 'bullish').length;
  const bearish = patterns.filter((p) => p.sentiment === 'bearish').length;
  const neutral = patterns.filter((p) => p.sentiment === 'neutral').length;
  const total = patterns.length;

  const bullishPct = Math.round((bullish / total) * 100);
  const bearishPct = Math.round((bearish / total) * 100);

  const overallSignal =
    bullishPct >= 60
      ? 'Bullish bias'
      : bearishPct >= 60
      ? 'Bearish bias'
      : 'Mixed signals';

  const signalColor =
    bullishPct >= 60
      ? 'text-green-600 dark:text-green-400'
      : bearishPct >= 60
      ? 'text-red-600 dark:text-red-400'
      : 'text-amber-600 dark:text-amber-400';

  // Sort by date descending (most recent first)
  const sorted = [...patterns].sort((a, b) => b.index - a.index);

  return (
    <div className={cn('card', className)}>
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-purple-500" />
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">Pattern Analysis</h3>
          <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-700 px-2 py-0.5 rounded-full">
            {total} detected
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-neutral-400 dark:text-neutral-500" />
        ) : (
          <ChevronDown className="w-5 h-5 text-neutral-400 dark:text-neutral-500" />
        )}
      </button>

      {expanded && (
        <div className="mt-4 space-y-4">
          {/* Summary bar */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-4 text-sm mb-2">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded-sm bg-green-500 inline-block" />
                  <span className="text-neutral-600 dark:text-neutral-400">Bullish: <span className="font-semibold text-neutral-900 dark:text-white">{bullish}</span></span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded-sm bg-red-500 inline-block" />
                  <span className="text-neutral-600 dark:text-neutral-400">Bearish: <span className="font-semibold text-neutral-900 dark:text-white">{bearish}</span></span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded-sm bg-amber-400 inline-block" />
                  <span className="text-neutral-600 dark:text-neutral-400">Neutral: <span className="font-semibold text-neutral-900 dark:text-white">{neutral}</span></span>
                </span>
              </div>
              {/* Progress bar */}
              <div className="w-full h-2.5 bg-neutral-100 dark:bg-neutral-700 rounded-full overflow-hidden flex">
                {bullish > 0 && (
                  <div
                    className="bg-green-500 h-full"
                    style={{ width: `${bullishPct}%` }}
                  />
                )}
                {neutral > 0 && (
                  <div
                    className="bg-amber-400 h-full"
                    style={{ width: `${Math.round((neutral / total) * 100)}%` }}
                  />
                )}
                {bearish > 0 && (
                  <div
                    className="bg-red-500 h-full"
                    style={{ width: `${bearishPct}%` }}
                  />
                )}
              </div>
            </div>
            <div className="text-right sm:min-w-[120px]">
              <div className="text-xs text-neutral-500 dark:text-neutral-400">Overall Signal</div>
              <div className={cn('text-sm font-bold', signalColor)}>
                {overallSignal}
              </div>
              <div className="text-xs text-neutral-400 dark:text-neutral-500">
                {bullishPct}% bullish
              </div>
            </div>
          </div>

          {/* Pattern list */}
          <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg overflow-hidden">
            <div className="max-h-[280px] overflow-y-auto">
              {sorted.map((p, i) => {
                const meta = PATTERN_META[p.type] || { icon: '?', color: '#737373' };
                return (
                  <div
                    key={`${p.type}-${p.index}-${i}`}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 text-sm',
                      i > 0 && 'border-t border-neutral-100 dark:border-neutral-700'
                    )}
                  >
                    {/* Date */}
                    <span className="text-xs text-neutral-500 dark:text-neutral-400 w-[70px] shrink-0">
                      {(() => {
                        try {
                          return format(parseISO(p.date), 'MMM d');
                        } catch {
                          return p.date;
                        }
                      })()}
                    </span>
                    {/* Icon */}
                    <span
                      className="w-6 h-6 flex items-center justify-center rounded-full text-xs border shrink-0"
                      style={{ borderColor: meta.color, color: meta.color }}
                    >
                      {meta.icon}
                    </span>
                    {/* Name */}
                    <span className="font-medium text-neutral-900 dark:text-white flex-1 min-w-0 truncate">
                      {p.name}
                    </span>
                    {/* Sentiment badge */}
                    <span
                      className={cn(
                        'px-2 py-0.5 text-xs font-medium rounded-full shrink-0',
                        p.sentiment === 'bullish'
                          ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                          : p.sentiment === 'bearish'
                          ? 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                          : 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400'
                      )}
                    >
                      {p.sentiment}
                    </span>
                    {/* Reliability */}
                    <span
                      className={cn(
                        'text-xs shrink-0 w-[52px] text-right',
                        p.reliability === 'high'
                          ? 'text-green-600 dark:text-green-400 font-semibold'
                          : p.reliability === 'medium'
                          ? 'text-neutral-500 dark:text-neutral-400'
                          : 'text-neutral-400 dark:text-neutral-500'
                      )}
                    >
                      {p.reliability}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PatternSummaryPanel;
