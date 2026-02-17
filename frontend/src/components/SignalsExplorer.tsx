import React, { useState, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Zap, RefreshCw, AlertTriangle, ArrowUpRight, ArrowDownRight,
  ArrowRight, Activity, ChevronUp, ChevronDown, X, ChevronRight,
  Shield, Info,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';

import { useAllSignals, useTickerSignals, useSignalTypes, useAlertStats } from '../hooks/useSignals';
import { useLatestAlerts } from '../hooks/useWSBDashboard';
import { signalsApi } from '../api/client';
import { useToast } from '../hooks/useToast';
import ToastManager from './ToastManager';
import {
  cn, formatNumber, formatPercent, formatRelativeTime,
  getStrengthColor, getDirectionColor, getSignalTypeLabel,
} from '../utils/format';
import type { Signal, Alert } from '../types/api';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
  const styles: Record<string, string> = {
    critical: 'bg-red-100 text-red-700 border-red-200 dark:bg-red-900/40 dark:text-red-300 dark:border-red-800',
    high: 'bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/40 dark:text-orange-300 dark:border-orange-800',
    medium: 'bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-300 dark:border-yellow-800',
    low: 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:border-blue-800',
  };
  return (
    <span className={cn('px-1.5 py-0.5 text-[10px] font-semibold rounded border uppercase', styles[severity] || styles.low)}>
      {severity}
    </span>
  );
};

const DirectionBadge: React.FC<{ direction: string }> = ({ direction }) => {
  const Icon = direction === 'bullish' ? ArrowUpRight : direction === 'bearish' ? ArrowDownRight : ArrowRight;
  return (
    <span className={cn('inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-semibold rounded border uppercase', getDirectionColor(direction))}>
      <Icon className="w-3 h-3" />
      {direction}
    </span>
  );
};

const StrengthBar: React.FC<{ strength: number }> = ({ strength }) => {
  const abs = Math.abs(strength);
  const barColor = strength >= 0
    ? (abs >= 0.7 ? 'bg-green-500' : abs >= 0.4 ? 'bg-green-400' : 'bg-neutral-400')
    : (abs >= 0.7 ? 'bg-red-500' : abs >= 0.4 ? 'bg-red-400' : 'bg-neutral-400');
  return (
    <div className="flex items-center gap-2">
      <div className="w-14 h-1.5 bg-neutral-200 dark:bg-neutral-600 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full', barColor)}
          style={{ width: `${Math.max(abs * 100, 5)}%` }}
        />
      </div>
      <span className={cn('text-xs font-medium tabular-nums', getStrengthColor(strength))}>
        {formatNumber(strength, 2)}
      </span>
    </div>
  );
};

const SortIcon: React.FC<{ active: boolean; direction: 'asc' | 'desc' }> = ({ active, direction }) => {
  if (!active) return <ChevronDown className="w-3 h-3 ml-0.5 text-neutral-300 dark:text-neutral-600 inline-block" />;
  return direction === 'asc'
    ? <ChevronUp className="w-3 h-3 ml-0.5 text-blue-600 dark:text-blue-400 inline-block" />
    : <ChevronDown className="w-3 h-3 ml-0.5 text-blue-600 dark:text-blue-400 inline-block" />;
};

const ThSortable: React.FC<{
  col: string;
  label: string;
  sortColumn: string;
  sortDirection: 'asc' | 'desc';
  onSort: (col: string) => void;
  className?: string;
}> = ({ col, label, sortColumn, sortDirection, onSort, className }) => (
  <th
    className={cn('px-3 py-2 cursor-pointer select-none hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors', className)}
    onClick={() => onSort(col)}
  >
    <span className="inline-flex items-center">
      {label}
      <SortIcon active={sortColumn === col} direction={sortDirection} />
    </span>
  </th>
);

// Signal type categories for grouping in the reference panel
const signalTypeCategories: Record<string, string[]> = {
  'Momentum': ['momentum_bullish', 'momentum_bearish'],
  'Sentiment': ['sentiment_spike', 'sentiment_momentum_divergence'],
  'WSB / Retail': ['wsb_viral', 'retail_buzz'],
  'Volume': ['volume_spike'],
  'News': ['breaking_news'],
  'Composite': ['strong_buy', 'strong_sell'],
};

// ---------------------------------------------------------------------------
// Ticker Drilldown
// ---------------------------------------------------------------------------

const TickerDrilldown: React.FC<{ ticker: string; onClose: () => void }> = ({ ticker, onClose }) => {
  const { data, isLoading, error } = useTickerSignals(ticker);

  return (
    <div className="card border-2 border-blue-200 dark:border-blue-700 mt-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Link to={`/stocks/${ticker}`} className="text-lg font-bold text-neutral-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400">
            ${ticker}
          </Link>
          <span className="text-xs text-neutral-400 dark:text-neutral-500">Signal Drilldown</span>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-neutral-100 dark:hover:bg-neutral-700 rounded">
          <X className="w-4 h-4 text-neutral-500 dark:text-neutral-400" />
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => <div key={i} className="h-8 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
        </div>
      ) : error ? (
        <p className="text-sm text-red-500 dark:text-red-400">Failed to load ticker signals</p>
      ) : data ? (
        <>
          {/* Summary strip */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
            <div className="text-center p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
              <div className="text-lg font-bold text-neutral-900 dark:text-white">{data.summary.signal_count}</div>
              <div className="text-[10px] text-neutral-500 dark:text-neutral-400">Total</div>
            </div>
            <div className="text-center p-2 bg-green-50 dark:bg-green-900/30 rounded-lg">
              <div className="text-lg font-bold text-green-700 dark:text-green-400">{data.summary.bullish_signals}</div>
              <div className="text-[10px] text-green-600 dark:text-green-500">Bullish</div>
            </div>
            <div className="text-center p-2 bg-red-50 dark:bg-red-900/30 rounded-lg">
              <div className="text-lg font-bold text-red-700 dark:text-red-400">{data.summary.bearish_signals}</div>
              <div className="text-[10px] text-red-600 dark:text-red-500">Bearish</div>
            </div>
            <div className="text-center p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
              <div className="text-lg font-bold text-neutral-900 dark:text-white">{formatNumber(data.summary.max_strength, 2)}</div>
              <div className="text-[10px] text-neutral-500 dark:text-neutral-400">Max Str</div>
            </div>
            <div className="text-center p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
              <div className="text-lg font-bold text-neutral-900 dark:text-white">{formatPercent(data.summary.avg_confidence, 0)}</div>
              <div className="text-[10px] text-neutral-500 dark:text-neutral-400">Avg Conf</div>
            </div>
          </div>

          {/* Signal list */}
          {data.signals.length === 0 ? (
            <p className="text-xs text-neutral-400 dark:text-neutral-500 text-center py-4">No signals for this ticker</p>
          ) : (
            <div className="space-y-2 max-h-48 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
              {data.signals.map((s: Signal) => (
                <div key={s.id} className="flex items-center justify-between p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
                  <div className="flex items-center gap-2">
                    <DirectionBadge direction={s.direction} />
                    <span className="text-xs font-medium text-neutral-700 dark:text-neutral-300">{getSignalTypeLabel(s.signal_type)}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <StrengthBar strength={s.strength} />
                    <span className="text-[10px] text-neutral-400 dark:text-neutral-500">{formatRelativeTime(s.generated_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          <Link
            to={`/stocks/${ticker}`}
            className="mt-3 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-medium"
          >
            View Stock Detail <ChevronRight className="w-3 h-3" />
          </Link>
        </>
      ) : null}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const SignalsExplorer: React.FC = () => {
  const queryClient = useQueryClient();
  const { toasts, showError: showErrorToast, removeToast } = useToast();

  // Filters
  const [directionFilter, setDirectionFilter] = useState<'all' | 'bullish' | 'bearish' | 'neutral'>('all');
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [minStrength, setMinStrength] = useState(0);
  const [tickerSearch, setTickerSearch] = useState('');

  // Sorting
  const [sortColumn, setSortColumn] = useState<string>('strength');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Drilldown
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  // Acknowledge loading state
  const [ackLoading, setAckLoading] = useState<string | null>(null);

  // Data hooks
  const allSignals = useAllSignals({ active_only: true, limit: 200 });
  const signalTypes = useSignalTypes();
  const alertStats = useAlertStats(7);
  const alerts = useLatestAlerts(24);

  // Refresh all
  const handleRefreshAll = useCallback(() => {
    allSignals.refetch();
    signalTypes.refetch();
    alertStats.refetch();
    alerts.refetch();
  }, [allSignals, signalTypes, alertStats, alerts]);

  // Sort handler
  const handleSort = useCallback((col: string) => {
    if (sortColumn === col) {
      setSortDirection(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(col);
      setSortDirection('desc');
    }
  }, [sortColumn]);

  // Acknowledge an alert
  const handleAcknowledge = useCallback(async (alertId: string) => {
    setAckLoading(alertId);
    try {
      await signalsApi.acknowledgeAlert(alertId);
      queryClient.invalidateQueries({ queryKey: ['wsb-dashboard', 'alerts'] });
      queryClient.invalidateQueries({ queryKey: ['signals', 'alert-stats'] });
    } catch (err) {
      showErrorToast('Acknowledge Failed', 'Could not acknowledge alert.');
    } finally {
      setAckLoading(null);
    }
  }, [queryClient]);

  // Filtered & sorted signals
  const filteredSignals = useMemo(() => {
    const signals = allSignals.data?.signals || [];
    let result = [...signals];

    if (directionFilter !== 'all') {
      result = result.filter(s => s.direction === directionFilter);
    }
    if (typeFilter) {
      result = result.filter(s => s.signal_type === typeFilter);
    }
    if (minStrength > 0) {
      result = result.filter(s => Math.abs(s.strength) >= minStrength);
    }
    if (tickerSearch) {
      const q = tickerSearch.toUpperCase();
      result = result.filter(s => s.ticker.includes(q));
    }

    result.sort((a, b) => {
      let cmp = 0;
      switch (sortColumn) {
        case 'ticker': cmp = a.ticker.localeCompare(b.ticker); break;
        case 'type': cmp = a.signal_type.localeCompare(b.signal_type); break;
        case 'direction': cmp = a.direction.localeCompare(b.direction); break;
        case 'strength': cmp = Math.abs(a.strength) - Math.abs(b.strength); break;
        case 'confidence': cmp = a.confidence - b.confidence; break;
        case 'generated_at': cmp = new Date(a.generated_at).getTime() - new Date(b.generated_at).getTime(); break;
        default: cmp = Math.abs(a.strength) - Math.abs(b.strength);
      }
      return sortDirection === 'asc' ? cmp : -cmp;
    });

    return result;
  }, [allSignals.data, directionFilter, typeFilter, minStrength, tickerSearch, sortColumn, sortDirection]);

  // KPI counts
  const bullishCount = useMemo(() =>
    (allSignals.data?.signals || []).filter(s => s.direction === 'bullish').length
  , [allSignals.data]);
  const bearishCount = useMemo(() =>
    (allSignals.data?.signals || []).filter(s => s.direction === 'bearish').length
  , [allSignals.data]);

  const hasActiveFilters = directionFilter !== 'all' || typeFilter !== null || minStrength > 0 || tickerSearch !== '';

  // Signal type names for the dropdown
  const typeNames = useMemo(() =>
    signalTypes.data ? Object.keys(signalTypes.data.signal_types).sort() : []
  , [signalTypes.data]);

  // Alert type icon
  const alertTypeIcon = (type: string) => {
    if (type.includes('sentiment')) return '\u{1F4AD}';
    if (type.includes('momentum') || type.includes('breakout')) return '\u{1F4C8}';
    if (type.includes('volume')) return '\u{1F4CA}';
    if (type.includes('wsb') || type.includes('viral')) return '\u{1F680}';
    if (type.includes('price')) return '\u{1F4B0}';
    return '\u26A1';
  };

  // =========================================================================
  // RENDER
  // =========================================================================

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">

      {/* ====== HEADER ====== */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <Zap className="w-6 h-6 text-purple-600" />
            Signal Explorer
          </h1>
          <span className="flex items-center gap-1.5 px-2.5 py-1 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 text-green-700 dark:text-green-400 text-xs font-semibold rounded-full">
            <span className="w-2 h-2 rounded-full bg-green-500 pulse-green" />
            LIVE
          </span>
        </div>
        <div className="flex items-center gap-3">
          {allSignals.dataUpdatedAt && (
            <span className="text-xs text-neutral-500 dark:text-neutral-400">
              Updated {new Date(allSignals.dataUpdatedAt).toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={handleRefreshAll}
            className="p-2 text-neutral-500 dark:text-neutral-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
            title="Refresh all panels"
          >
            <RefreshCw className={cn('w-4 h-4', allSignals.isFetching && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* ====== KPI STRIP ====== */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wide">Active Signals</span>
            <span className="p-1.5 rounded-lg bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400"><Zap className="w-4 h-4" /></span>
          </div>
          {allSignals.isLoading ? (
            <div className="h-7 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
          ) : (
            <div className="text-2xl font-bold text-neutral-900 dark:text-white">{allSignals.data?.count ?? 0}</div>
          )}
        </div>

        <div className="card hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wide">Bullish</span>
            <span className="p-1.5 rounded-lg bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400"><ArrowUpRight className="w-4 h-4" /></span>
          </div>
          {allSignals.isLoading ? (
            <div className="h-7 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
          ) : (
            <div className="text-2xl font-bold text-green-700 dark:text-green-400">{bullishCount}</div>
          )}
        </div>

        <div className="card hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wide">Bearish</span>
            <span className="p-1.5 rounded-lg bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400"><ArrowDownRight className="w-4 h-4" /></span>
          </div>
          {allSignals.isLoading ? (
            <div className="h-7 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
          ) : (
            <div className="text-2xl font-bold text-red-700 dark:text-red-400">{bearishCount}</div>
          )}
        </div>

        <div className="card hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wide">Alerts (24h)</span>
            <span className="p-1.5 rounded-lg bg-orange-50 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400"><Activity className="w-4 h-4" /></span>
          </div>
          {alerts.isLoading ? (
            <div className="h-7 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
          ) : (
            <>
              <div className="text-2xl font-bold text-neutral-900 dark:text-white">{alerts.data?.count ?? 0}</div>
              {alertStats.data && (
                <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">{alertStats.data.unacknowledged_count} unacknowledged</div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ====== FILTER BAR ====== */}
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          {/* Direction pills */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-neutral-500 dark:text-neutral-400 mr-1">Direction:</span>
            {(['all', 'bullish', 'bearish', 'neutral'] as const).map(d => (
              <button
                key={d}
                onClick={() => setDirectionFilter(d)}
                className={cn(
                  'px-2.5 py-1 text-xs font-medium rounded-full border transition-colors',
                  directionFilter === d
                    ? 'bg-neutral-900 text-white border-neutral-900 dark:bg-white dark:text-neutral-900 dark:border-white'
                    : 'bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400 dark:bg-neutral-800 dark:border-neutral-700 dark:text-neutral-300 dark:hover:border-neutral-500',
                )}
              >
                {d.charAt(0).toUpperCase() + d.slice(1)}
              </button>
            ))}
          </div>

          {/* Type dropdown */}
          <select
            value={typeFilter ?? ''}
            onChange={e => setTypeFilter(e.target.value || null)}
            className="text-xs border border-neutral-200 rounded-lg px-2.5 py-1.5 text-neutral-700 bg-white dark:bg-neutral-800 dark:border-neutral-600 dark:text-neutral-300"
          >
            <option value="">All types</option>
            {typeNames.map(t => (
              <option key={t} value={t}>{getSignalTypeLabel(t)}</option>
            ))}
          </select>

          {/* Strength filter */}
          <select
            value={minStrength}
            onChange={e => setMinStrength(Number(e.target.value))}
            className="text-xs border border-neutral-200 rounded-lg px-2.5 py-1.5 text-neutral-700 bg-white dark:bg-neutral-800 dark:border-neutral-600 dark:text-neutral-300"
          >
            <option value={0}>Any strength</option>
            <option value={0.3}>&ge; 0.3 (Moderate+)</option>
            <option value={0.5}>&ge; 0.5 (Strong+)</option>
            <option value={0.7}>&ge; 0.7 (Very Strong)</option>
          </select>

          {/* Ticker search */}
          <div className="relative flex-1 max-w-xs">
            <input
              type="text"
              value={tickerSearch}
              onChange={e => setTickerSearch(e.target.value)}
              placeholder="Search ticker..."
              className="w-full pl-3 pr-8 py-1.5 text-xs border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-neutral-800 dark:border-neutral-600 dark:text-neutral-300 dark:placeholder-neutral-500"
            />
            {tickerSearch && (
              <button
                onClick={() => setTickerSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {hasActiveFilters && (
            <button
              onClick={() => { setDirectionFilter('all'); setTypeFilter(null); setMinStrength(0); setTickerSearch(''); }}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline whitespace-nowrap"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* ====== MAIN GRID ====== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ---------- LEFT COLUMN (8/12) ---------- */}
        <div className="lg:col-span-8 space-y-0">

          {/* Signals Table */}
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between px-1 mb-4">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-purple-600" />
                Trading Signals
              </h2>
              <span className="text-xs text-neutral-500 dark:text-neutral-400">
                {filteredSignals.length}{hasActiveFilters ? ` of ${allSignals.data?.count ?? 0}` : ''} signals
              </span>
            </div>

            {allSignals.isLoading ? (
              <div className="space-y-2">
                {[...Array(6)].map((_, i) => <div key={i} className="h-10 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : allSignals.error ? (
              <div className="text-center py-8">
                <AlertTriangle className="w-8 h-8 text-red-400 dark:text-red-500 mx-auto mb-2" />
                <p className="text-neutral-600 dark:text-neutral-400 text-sm">Failed to load signals</p>
                <button onClick={() => allSignals.refetch()} className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline">Retry</button>
              </div>
            ) : filteredSignals.length === 0 ? (
              <div className="text-center py-12">
                <Zap className="w-10 h-10 text-neutral-300 dark:text-neutral-700 mx-auto mb-2" />
                <p className="text-neutral-500 dark:text-neutral-400">
                  {hasActiveFilters ? 'No signals match your filters' : 'No active signals'}
                </p>
                {hasActiveFilters && (
                  <button
                    onClick={() => { setDirectionFilter('all'); setTypeFilter(null); setMinStrength(0); setTickerSearch(''); }}
                    className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    Clear filters
                  </button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto -mx-6">
                <table className="w-full text-sm" style={{ minWidth: '420px' }}>
                  <thead>
                    <tr className="border-b border-neutral-200 dark:border-neutral-700 text-left text-xs text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                      <ThSortable col="ticker" label="Ticker" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} className="px-6" />
                      <ThSortable col="type" label="Type" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                      <th className="px-3 py-2">Direction</th>
                      <ThSortable col="strength" label="Strength" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                      <ThSortable col="confidence" label="Conf" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} className="hidden md:table-cell" />
                      <ThSortable col="generated_at" label="Age" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                      <th className="px-3 py-2 hidden md:table-cell">Expires</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700">
                    {filteredSignals.map(s => {
                      const isSelected = selectedTicker === s.ticker;
                      const isExpired = s.expires_at && new Date(s.expires_at) < new Date();
                      return (
                        <tr
                          key={s.id}
                          className={cn(
                            'hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors cursor-pointer',
                            isSelected && 'bg-blue-50 dark:bg-blue-900/30',
                          )}
                          onClick={() => setSelectedTicker(prev => prev === s.ticker ? null : s.ticker)}
                        >
                          <td className="px-6 py-2.5">
                            <Link
                              to={`/stocks/${s.ticker}`}
                              className="font-bold text-neutral-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400"
                              onClick={e => e.stopPropagation()}
                            >
                              ${s.ticker}
                            </Link>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="text-xs text-neutral-600 dark:text-neutral-400">{getSignalTypeLabel(s.signal_type)}</span>
                          </td>
                          <td className="px-3 py-2.5">
                            <DirectionBadge direction={s.direction} />
                          </td>
                          <td className="px-3 py-2.5">
                            <StrengthBar strength={s.strength} />
                          </td>
                          <td className="px-3 py-2.5 hidden md:table-cell">
                            <span className={cn(
                              'text-xs font-medium',
                              s.confidence >= 0.7 ? 'text-green-600 dark:text-green-400' :
                              s.confidence >= 0.4 ? 'text-yellow-600 dark:text-yellow-400' :
                              'text-neutral-500 dark:text-neutral-400',
                            )}>
                              {formatPercent(s.confidence, 0)}
                            </span>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="text-xs text-neutral-500 dark:text-neutral-400">{formatRelativeTime(s.generated_at)}</span>
                          </td>
                          <td className="px-3 py-2.5 hidden md:table-cell">
                            {isExpired ? (
                              <span className="text-[10px] text-red-400 dark:text-red-500 font-medium">Expired</span>
                            ) : s.expires_at ? (
                              <span className="text-[10px] text-neutral-400 dark:text-neutral-500">{formatRelativeTime(s.expires_at)}</span>
                            ) : (
                              <span className="text-[10px] text-neutral-300 dark:text-neutral-700">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Ticker Drilldown */}
          {selectedTicker && (
            <TickerDrilldown ticker={selectedTicker} onClose={() => setSelectedTicker(null)} />
          )}
        </div>

        {/* ---------- RIGHT COLUMN (4/12) ---------- */}
        <div className="lg:col-span-4 space-y-6">

          {/* Alert Stats */}
          <div className="card">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-blue-500" />
              Alert Stats (7d)
            </h2>

            {alertStats.isLoading ? (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <div key={i} className="h-6 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : alertStats.error ? (
              <p className="text-xs text-red-500 dark:text-red-400 py-2 text-center">Failed to load stats</p>
            ) : alertStats.data ? (
              <div className="space-y-3">
                {/* Total + Ack Rate */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-neutral-600 dark:text-neutral-400">Total Alerts</span>
                  <span className="text-sm font-bold text-neutral-900 dark:text-white">{alertStats.data.total_alerts}</span>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-neutral-600 dark:text-neutral-400">Acknowledgment Rate</span>
                    <span className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
                      {formatPercent(alertStats.data.acknowledgment_rate, 0)}
                    </span>
                  </div>
                  <div className="w-full h-2 bg-neutral-200 dark:bg-neutral-600 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 rounded-full"
                      style={{ width: `${alertStats.data.acknowledgment_rate * 100}%` }}
                    />
                  </div>
                </div>

                {/* Severity breakdown */}
                <div>
                  <div className="text-[10px] text-neutral-400 dark:text-neutral-500 uppercase tracking-wider mb-1.5">Severity</div>
                  <div className="grid grid-cols-4 gap-2">
                    {(['critical', 'high', 'medium', 'low'] as const).map(sev => {
                      const count = alertStats.data!.severity_breakdown[sev] ?? 0;
                      const colors: Record<string, string> = {
                        critical: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400',
                        high: 'bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
                        medium: 'bg-yellow-50 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
                        low: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
                      };
                      return (
                        <div key={sev} className={cn('text-center p-1.5 rounded-lg', colors[sev])}>
                          <div className="text-sm font-bold">{count}</div>
                          <div className="text-[9px] uppercase">{sev}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Top alert types */}
                {alertStats.data.top_alert_types.length > 0 && (
                  <div>
                    <div className="text-[10px] text-neutral-400 dark:text-neutral-500 uppercase tracking-wider mb-1.5">Top Types</div>
                    <div className="space-y-1">
                      {alertStats.data.top_alert_types.slice(0, 5).map((t, i) => (
                        <div key={i} className="flex items-center justify-between text-xs">
                          <span className="text-neutral-600 dark:text-neutral-400">{getSignalTypeLabel(t.type)}</span>
                          <span className="font-medium text-neutral-800 dark:text-neutral-200">{t.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>

          {/* Signal Types Reference */}
          <div className="card">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-1.5">
              <Info className="w-4 h-4 text-indigo-500" />
              Signal Types
            </h2>

            {signalTypes.isLoading ? (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <div key={i} className="h-6 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : signalTypes.error ? (
              <p className="text-xs text-red-500 dark:text-red-400 py-2 text-center">Failed to load</p>
            ) : signalTypes.data ? (
              <div className="space-y-3 max-h-72 overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                {Object.entries(signalTypeCategories).map(([category, types]) => {
                  const available = types.filter(t => signalTypes.data!.signal_types[t]);
                  if (available.length === 0) return null;
                  return (
                    <div key={category}>
                      <div className="text-[10px] font-medium text-neutral-400 dark:text-neutral-500 uppercase tracking-wider mb-1">{category}</div>
                      <div className="space-y-1.5">
                        {available.map(t => {
                          const info = signalTypes.data!.signal_types[t];
                          return (
                            <div key={t} className="p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
                              <div className="flex items-center justify-between mb-0.5">
                                <span className="text-xs font-medium text-neutral-800 dark:text-neutral-200">{getSignalTypeLabel(t)}</span>
                                <span className="text-[9px] text-neutral-400 dark:text-neutral-500">{info.timeframe} · {info.expires_hours}h</span>
                              </div>
                              <p className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-tight">{info.description}</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>

          {/* Recent Alerts */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-white flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-orange-500" />
                Recent Alerts
              </h2>
              <span className="text-[10px] text-neutral-400 dark:text-neutral-500">{alerts.data?.count ?? 0} in 24h</span>
            </div>

            {alerts.isLoading ? (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <div key={i} className="h-12 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : alerts.error ? (
              <p className="text-xs text-red-500 dark:text-red-400 py-4 text-center">Failed to load alerts</p>
            ) : (alerts.data?.alerts?.length ?? 0) === 0 ? (
              <p className="text-xs text-neutral-400 dark:text-neutral-500 py-6 text-center">No recent alerts</p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                {alerts.data!.alerts.slice(0, 10).map((a: Alert) => (
                  <div key={a.id} className="p-2.5 bg-neutral-50 dark:bg-neutral-800 rounded-lg border border-neutral-100 dark:border-neutral-700 hover:border-neutral-200 dark:hover:border-neutral-600 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">{alertTypeIcon(a.alert_type)}</span>
                        <Link to={`/stocks/${a.ticker}`} className="font-bold text-xs text-neutral-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400">
                          ${a.ticker}
                        </Link>
                        <SeverityBadge severity={a.severity} />
                      </div>
                      <span className="text-[10px] text-neutral-400 dark:text-neutral-500">{formatRelativeTime(a.triggered_at)}</span>
                    </div>
                    <p className="text-[11px] text-neutral-600 dark:text-neutral-400 leading-tight line-clamp-2 mb-1.5">{a.title}</p>
                    {!a.acknowledged_at && (
                      <button
                        onClick={() => handleAcknowledge(a.id)}
                        disabled={ackLoading === a.id}
                        className="text-[10px] text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium disabled:opacity-50"
                      >
                        {ackLoading === a.id ? 'Acknowledging...' : 'Acknowledge'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ====== FOOTER ====== */}
      <div className="text-center text-xs text-neutral-400 dark:text-neutral-500 pt-2 border-t border-neutral-200 dark:border-neutral-700">
        Signal Explorer — 11 signal types across {allSignals.data?.count ?? 0} active signals
        {allSignals.dataUpdatedAt && (
          <span> · Updated {formatRelativeTime(new Date(allSignals.dataUpdatedAt).toISOString())}</span>
        )}
      </div>
      <ToastManager toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};

export default SignalsExplorer;
