import React, { useMemo } from 'react';
import { X, BarChart3 } from 'lucide-react';
import { cn, formatNumber, formatPercent } from '../utils/format';

export interface ComparisonStock {
  symbol: string;
  name: string;
  sentiment: number | null;
  returns_5d: number | null;
  volume_z: number | null;
  article_count: number;
  signals_7d: number;
  alerts_7d: number;
}

interface StockComparisonDrawerProps {
  stocks: ComparisonStock[];
  onRemove: (symbol: string) => void;
  onClose: () => void;
}

const COLORS = [
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-purple-500',
  'bg-rose-500',
  'bg-cyan-500',
  'bg-indigo-500',
  'bg-orange-500',
];

const CHIP_COLORS = [
  'bg-blue-100 text-blue-700',
  'bg-emerald-100 text-emerald-700',
  'bg-amber-100 text-amber-700',
  'bg-purple-100 text-purple-700',
  'bg-rose-100 text-rose-700',
  'bg-cyan-100 text-cyan-700',
  'bg-indigo-100 text-indigo-700',
  'bg-orange-100 text-orange-700',
];

interface MetricConfig {
  key: string;
  label: string;
  getValue: (s: ComparisonStock) => number | null;
  format: (v: number) => string;
}

const metrics: MetricConfig[] = [
  {
    key: 'sentiment',
    label: 'Sentiment',
    getValue: (s) => s.sentiment,
    format: (v) => formatNumber(v, 3),
  },
  {
    key: 'returns_5d',
    label: '5d Return',
    getValue: (s) => s.returns_5d,
    format: (v) => formatPercent(v, 1),
  },
  {
    key: 'volume_z',
    label: 'Vol Z-Score',
    getValue: (s) => s.volume_z,
    format: (v) => formatNumber(v, 2),
  },
  {
    key: 'articles',
    label: 'Articles',
    getValue: (s) => s.article_count,
    format: (v) => v.toString(),
  },
  {
    key: 'activity',
    label: 'Activity (7d)',
    getValue: (s) => s.signals_7d + s.alerts_7d,
    format: (v) => v.toString(),
  },
];

const MetricRow: React.FC<{
  config: MetricConfig;
  stocks: ComparisonStock[];
}> = ({ config, stocks }) => {
  const values = stocks.map((s) => config.getValue(s));
  const numericValues = values.filter((v): v is number => v !== null);
  const min = numericValues.length > 0 ? Math.min(...numericValues) : 0;
  const max = numericValues.length > 0 ? Math.max(...numericValues) : 1;
  const range = max - min || 1;

  return (
    <div className="py-3">
      <div className="text-xs font-medium text-neutral-500 dark:text-neutral-400 mb-2">{config.label}</div>
      <div className="space-y-1.5">
        {stocks.map((stock, i) => {
          const value = config.getValue(stock);
          const barWidth = value !== null ? Math.max(((value - min) / range) * 100, 4) : 0;

          return (
            <div key={stock.symbol} className="flex items-center gap-2">
              <span className="w-12 text-xs font-mono font-semibold text-neutral-700 dark:text-neutral-300 shrink-0 text-right">
                {stock.symbol}
              </span>
              <div className="flex-1 h-5 bg-neutral-100 dark:bg-neutral-700 rounded overflow-hidden relative">
                {value !== null ? (
                  <div
                    className={cn(
                      'h-full rounded transition-all duration-300',
                      COLORS[i % COLORS.length],
                    )}
                    style={{ width: `${barWidth}%` }}
                  />
                ) : (
                  <div className="h-full flex items-center px-2">
                    <span className="text-[10px] text-neutral-400">No data</span>
                  </div>
                )}
              </div>
              <span className="w-16 text-xs text-neutral-600 dark:text-neutral-400 font-mono shrink-0 text-right">
                {value !== null ? config.format(value) : '—'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const StockComparisonDrawer: React.FC<StockComparisonDrawerProps> = ({
  stocks,
  onRemove,
  onClose,
}) => {
  if (stocks.length < 2) return null;

  return (
    <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100 dark:border-neutral-700">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
            Comparing {stocks.length} Stocks
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-neutral-100 dark:hover:bg-neutral-700 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Stock chips */}
      <div className="px-4 py-2.5 border-b border-neutral-100 dark:border-neutral-700 flex flex-wrap gap-1.5">
        {stocks.map((stock, i) => (
          <span
            key={stock.symbol}
            className={cn(
              'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
              CHIP_COLORS[i % CHIP_COLORS.length],
            )}
          >
            {stock.symbol}
            <button
              onClick={() => onRemove(stock.symbol)}
              className="ml-0.5 hover:opacity-70 transition-opacity"
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
      </div>

      {/* Metric rows */}
      <div className="px-4 divide-y divide-neutral-100 dark:divide-neutral-700">
        {metrics.map((m) => (
          <MetricRow key={m.key} config={m} stocks={stocks} />
        ))}
      </div>
    </div>
  );
};

export default StockComparisonDrawer;
