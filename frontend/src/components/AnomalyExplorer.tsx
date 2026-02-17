import React, { useState, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, RefreshCw, Search, Activity, Target,
  ChevronDown, ChevronUp, X, ArrowUpRight,
} from 'lucide-react';
import { useAllAnomalies, usePriceAnomalies, useSentimentAnomalies, usePatternAnomalies } from '../hooks/useAnomalies';
import { cn, formatNumber, formatRelativeTime } from '../utils/format';
import type { Anomaly } from '../types/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const anomalyTypeLabel = (t: string) => t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

type SeverityLevel = 'all' | 'high' | 'medium' | 'low';
type SortField = 'severity' | 'z_score' | 'ticker' | 'confidence';

const severityColor = (s: number) =>
  s >= 0.7 ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' :
  s >= 0.4 ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300' :
  'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300';

const severityBarColor = (s: number) =>
  s >= 0.7 ? 'bg-red-500' : s >= 0.4 ? 'bg-yellow-500' : 'bg-blue-500';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const SeverityBadge: React.FC<{ severity: number }> = ({ severity }) => (
  <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded', severityColor(severity))}>
    {formatNumber(severity, 2)}
  </span>
);

const AnomalyDetailCard: React.FC<{ anomaly: Anomaly }> = ({ anomaly }) => (
  <div className="p-3 rounded-lg border border-neutral-100 bg-neutral-50 dark:bg-neutral-800 dark:border-neutral-700">
    <div className="flex items-center justify-between mb-2">
      <span className="text-sm font-medium text-neutral-900 dark:text-white">{anomalyTypeLabel(anomaly.anomaly_type)}</span>
      <SeverityBadge severity={anomaly.severity} />
    </div>
    <div className="grid grid-cols-2 gap-3 text-xs">
      <div>
        <span className="text-neutral-500 dark:text-neutral-400">Z-Score</span>
        <div className="font-semibold text-neutral-800 dark:text-neutral-200">{formatNumber(anomaly.z_score, 2)}</div>
      </div>
      <div>
        <span className="text-neutral-500 dark:text-neutral-400">Confidence</span>
        <div className="font-semibold text-neutral-800 dark:text-neutral-200">{formatNumber(anomaly.confidence, 2)}</div>
      </div>
      <div>
        <span className="text-neutral-500 dark:text-neutral-400">Current</span>
        <div className="font-semibold text-neutral-800 dark:text-neutral-200">{formatNumber(anomaly.current_value, 4)}</div>
      </div>
      <div>
        <span className="text-neutral-500 dark:text-neutral-400">Expected</span>
        <div className="font-semibold text-neutral-800 dark:text-neutral-200">{formatNumber(anomaly.expected_value, 4)}</div>
      </div>
    </div>
    {anomaly.metadata && Object.keys(anomaly.metadata).length > 0 && (
      <div className="mt-2 pt-2 border-t border-neutral-200 dark:border-neutral-700">
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(anomaly.metadata).slice(0, 4).map(([k, v]) => (
            <span key={k} className="px-1.5 py-0.5 bg-white border border-neutral-200 rounded text-[10px] text-neutral-600 dark:bg-neutral-700 dark:border-neutral-600 dark:text-neutral-300">
              {k.replace(/_/g, ' ')}: {typeof v === 'number' ? formatNumber(v, 2) : String(v)}
            </span>
          ))}
        </div>
      </div>
    )}
  </div>
);

// ---------------------------------------------------------------------------
// Drill-Down Panel
// ---------------------------------------------------------------------------

const TickerDrillDown: React.FC<{ ticker: string; onClose: () => void }> = ({ ticker, onClose }) => {
  const [activeTab, setActiveTab] = useState<'price' | 'sentiment' | 'patterns'>('price');

  const price = usePriceAnomalies(ticker);
  const sentiment = useSentimentAnomalies(ticker);
  const patterns = usePatternAnomalies(ticker);

  const tabs = [
    { key: 'price' as const, label: 'Price & Volume', count: price.data?.price_anomalies?.length ?? 0 },
    { key: 'sentiment' as const, label: 'Sentiment', count: sentiment.data?.sentiment_anomalies?.length ?? 0 },
    { key: 'patterns' as const, label: 'Patterns', count: patterns.data?.pattern_anomalies?.length ?? 0 },
  ];

  const activeData =
    activeTab === 'price' ? price.data?.price_anomalies :
    activeTab === 'sentiment' ? sentiment.data?.sentiment_anomalies :
    patterns.data?.pattern_anomalies;

  const isLoading =
    activeTab === 'price' ? price.isLoading :
    activeTab === 'sentiment' ? sentiment.isLoading :
    patterns.isLoading;

  const isError =
    activeTab === 'price' ? price.error :
    activeTab === 'sentiment' ? sentiment.error :
    patterns.error;

  return (
    <div className="card border-2 border-blue-200 dark:border-blue-700">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Link to={`/stocks/${ticker}`} className="text-lg font-bold text-neutral-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400 flex items-center gap-1">
            ${ticker} <ArrowUpRight className="w-4 h-4" />
          </Link>
          <span className="text-xs text-neutral-500 dark:text-neutral-400">Ticker Deep-Dive</span>
        </div>
        <button onClick={onClose} className="p-1 text-neutral-400 hover:text-neutral-700 dark:text-neutral-500 dark:hover:text-neutral-200 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-700">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-neutral-200 dark:border-neutral-600">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-3 py-2 text-sm font-medium border-b-2 transition-colors -mb-px',
              activeTab === tab.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300 dark:text-neutral-400 dark:hover:text-neutral-200 dark:hover:border-neutral-500',
            )}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 bg-neutral-100 text-neutral-600 dark:bg-neutral-600 dark:text-neutral-300 text-[10px] font-semibold rounded-full">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {isLoading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => <div key={i} className="h-16 bg-neutral-100 dark:bg-neutral-700 rounded-lg animate-pulse" />)}
        </div>
      ) : isError ? (
        <p className="text-xs text-red-500 dark:text-red-400 py-4 text-center">Failed to load {activeTab} anomalies for {ticker}</p>
      ) : !activeData || activeData.length === 0 ? (
        <div className="text-center py-6">
          <AlertTriangle className="w-6 h-6 text-neutral-300 dark:text-neutral-600 mx-auto mb-2" />
          <p className="text-xs text-neutral-400 dark:text-neutral-500">No {activeTab} anomalies detected for {ticker}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {activeData.map((a: Anomaly, i: number) => (
            <AnomalyDetailCard key={`${a.anomaly_type}-${i}`} anomaly={a} />
          ))}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const AnomalyExplorer: React.FC = () => {
  // State
  const [severityFilter, setSeverityFilter] = useState<SeverityLevel>('all');
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [tickerSearch, setTickerSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('severity');
  const [sortAsc, setSortAsc] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  // Data
  const allAnomalies = useAllAnomalies({ limit: 100 });
  const anomalies = allAnomalies.data?.anomalies ?? [];

  // Filtering
  const filtered = useMemo(() => {
    let result = [...anomalies];

    if (severityFilter === 'high') result = result.filter(a => a.severity >= 0.7);
    else if (severityFilter === 'medium') result = result.filter(a => a.severity >= 0.4 && a.severity < 0.7);
    else if (severityFilter === 'low') result = result.filter(a => a.severity < 0.4);

    if (typeFilter) result = result.filter(a => a.anomaly_type === typeFilter);

    if (tickerSearch) {
      const search = tickerSearch.toUpperCase();
      result = result.filter(a => a.ticker.includes(search));
    }

    // Sort
    result.sort((a, b) => {
      let cmp = 0;
      if (sortField === 'severity') cmp = b.severity - a.severity;
      else if (sortField === 'z_score') cmp = Math.abs(b.z_score) - Math.abs(a.z_score);
      else if (sortField === 'ticker') cmp = a.ticker.localeCompare(b.ticker);
      else if (sortField === 'confidence') cmp = b.confidence - a.confidence;
      return sortAsc ? -cmp : cmp;
    });

    return result;
  }, [anomalies, severityFilter, typeFilter, tickerSearch, sortField, sortAsc]);

  // Derived stats (from filtered data)
  const stats = useMemo(() => {
    const highCount = filtered.filter(a => a.severity >= 0.7).length;
    const uniqueTickers = new Set(filtered.map(a => a.ticker)).size;
    const avgSeverity = filtered.length > 0
      ? filtered.reduce((sum, a) => sum + a.severity, 0) / filtered.length
      : 0;
    return { total: filtered.length, highCount, uniqueTickers, avgSeverity };
  }, [filtered]);

  // Type breakdown (from all anomalies, not filtered)
  const typeBreakdown = useMemo(() => {
    const counts: Record<string, number> = {};
    anomalies.forEach(a => {
      counts[a.anomaly_type] = (counts[a.anomaly_type] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [anomalies]);

  const maxTypeCount = typeBreakdown.length > 0 ? typeBreakdown[0][1] : 1;

  // Severity distribution (from all anomalies)
  const severityDist = useMemo(() => {
    const high = anomalies.filter(a => a.severity >= 0.7).length;
    const medium = anomalies.filter(a => a.severity >= 0.4 && a.severity < 0.7).length;
    const low = anomalies.filter(a => a.severity < 0.4).length;
    const total = anomalies.length || 1;
    return { high, medium, low, total };
  }, [anomalies]);

  // Top affected tickers
  const topTickers = useMemo(() => {
    const counts: Record<string, number> = {};
    anomalies.forEach(a => {
      counts[a.ticker] = (counts[a.ticker] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [anomalies]);

  const maxTickerCount = topTickers.length > 0 ? topTickers[0][1] : 1;

  // Sort handler
  const handleSort = useCallback((field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  }, [sortField, sortAsc]);

  const SortIcon: React.FC<{ field: SortField }> = ({ field }) => {
    if (sortField !== field) return null;
    return sortAsc ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />;
  };

  const clearFilters = () => {
    setSeverityFilter('all');
    setTypeFilter(null);
    setTickerSearch('');
  };

  const hasActiveFilters = severityFilter !== 'all' || typeFilter !== null || tickerSearch !== '';

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">

      {/* ====== HEADER ====== */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-red-600" />
            Anomaly Explorer
          </h1>
          <span className="flex items-center gap-1.5 px-2.5 py-1 bg-green-50 border border-green-200 text-green-700 dark:bg-green-900/30 dark:border-green-700 dark:text-green-400 text-xs font-semibold rounded-full">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            LIVE
          </span>
        </div>
        <div className="flex items-center gap-3">
          {allAnomalies.data?.generated_at && (
            <span className="text-xs text-neutral-500 dark:text-neutral-400">
              Generated {formatRelativeTime(allAnomalies.data.generated_at)}
            </span>
          )}
          <button
            onClick={() => allAnomalies.refetch()}
            className="p-2 text-neutral-500 hover:text-blue-600 hover:bg-blue-50 dark:text-neutral-400 dark:hover:text-blue-400 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
            title="Refresh anomalies"
          >
            <RefreshCw className={cn('w-4 h-4', allAnomalies.isFetching && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* ====== CONTROL BAR ====== */}
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          {/* Severity pills */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-neutral-500 dark:text-neutral-400 mr-1">Severity:</span>
            {(['all', 'high', 'medium', 'low'] as SeverityLevel[]).map(level => (
              <button
                key={level}
                onClick={() => setSeverityFilter(level)}
                className={cn(
                  'px-2.5 py-1 text-xs font-medium rounded-full border transition-colors',
                  severityFilter === level
                    ? level === 'high' ? 'bg-red-100 text-red-700 border-red-200 dark:bg-red-900/40 dark:text-red-300 dark:border-red-700'
                      : level === 'medium' ? 'bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-300 dark:border-yellow-700'
                      : level === 'low' ? 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:border-blue-700'
                      : 'bg-neutral-900 text-white border-neutral-900 dark:bg-white dark:text-neutral-900 dark:border-white'
                    : 'bg-white text-neutral-600 border-neutral-200 hover:border-neutral-300 dark:bg-neutral-800 dark:border-neutral-600 dark:text-neutral-300 dark:hover:border-neutral-500',
                )}
              >
                {level === 'all' ? 'All' : level.charAt(0).toUpperCase() + level.slice(1)}
              </button>
            ))}
          </div>

          {/* Type filter */}
          {typeBreakdown.length > 0 && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-neutral-500 dark:text-neutral-400 mr-1">Type:</span>
              <select
                value={typeFilter ?? ''}
                onChange={e => setTypeFilter(e.target.value || null)}
                className="text-xs border border-neutral-200 rounded-lg px-2 py-1 text-neutral-700 bg-white dark:bg-neutral-800 dark:border-neutral-600 dark:text-neutral-200"
              >
                <option value="">All types</option>
                {typeBreakdown.map(([type]) => (
                  <option key={type} value={type}>{anomalyTypeLabel(type)}</option>
                ))}
              </select>
            </div>
          )}

          {/* Ticker search */}
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-400" />
            <input
              type="text"
              value={tickerSearch}
              onChange={e => setTickerSearch(e.target.value)}
              placeholder="Search ticker..."
              className="w-full pl-8 pr-3 py-1.5 text-xs border border-neutral-200 rounded-lg focus:outline-none focus:border-blue-300 dark:bg-neutral-800 dark:border-neutral-600 dark:text-neutral-300 dark:placeholder-neutral-500"
            />
          </div>

          {/* Clear filters */}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-red-600 dark:text-red-400 hover:underline flex items-center gap-1"
            >
              <X className="w-3 h-3" /> Clear
            </button>
          )}
        </div>
      </div>

      {/* ====== KPI STRIP ====== */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Total Anomalies</span>
            <AlertTriangle className="w-4 h-4 text-orange-500" />
          </div>
          {allAnomalies.isLoading ? (
            <div className="h-7 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
          ) : (
            <div className="text-2xl font-bold text-neutral-900 dark:text-white">{stats.total}</div>
          )}
        </div>
        <div className="card">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">High Severity</span>
            <AlertTriangle className="w-4 h-4 text-red-500" />
          </div>
          {allAnomalies.isLoading ? (
            <div className="h-7 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
          ) : (
            <div className="text-2xl font-bold text-red-600">{stats.highCount}</div>
          )}
        </div>
        <div className="card">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Tickers Affected</span>
            <Target className="w-4 h-4 text-purple-500" />
          </div>
          {allAnomalies.isLoading ? (
            <div className="h-7 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
          ) : (
            <div className="text-2xl font-bold text-neutral-900 dark:text-white">{stats.uniqueTickers}</div>
          )}
        </div>
        <div className="card">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Avg Severity</span>
            <Activity className="w-4 h-4 text-blue-500" />
          </div>
          {allAnomalies.isLoading ? (
            <div className="h-7 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
          ) : (
            <div className="text-2xl font-bold text-neutral-900 dark:text-white">{formatNumber(stats.avgSeverity, 2)}</div>
          )}
        </div>
      </div>

      {/* ====== MAIN GRID ====== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ---------- LEFT COLUMN (8/12) ---------- */}
        <div className="lg:col-span-8 space-y-6">

          {/* -- ANOMALY TABLE -- */}
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between px-1 mb-4">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
                <Activity className="w-5 h-5 text-orange-600" />
                Detected Anomalies
              </h2>
              <span className="text-xs text-neutral-500 dark:text-neutral-400">{filtered.length} results</span>
            </div>

            {allAnomalies.isLoading ? (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => <div key={i} className="h-10 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : allAnomalies.error ? (
              <div className="text-center py-8">
                <AlertTriangle className="w-8 h-8 text-red-400 dark:text-red-500 mx-auto mb-2" />
                <p className="text-neutral-600 dark:text-neutral-400 text-sm">Failed to load anomalies</p>
                <button onClick={() => allAnomalies.refetch()} className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline">Retry</button>
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-12">
                <AlertTriangle className="w-10 h-10 text-neutral-300 dark:text-neutral-600 mx-auto mb-2" />
                <p className="text-neutral-500 dark:text-neutral-400">
                  {hasActiveFilters
                    ? 'No anomalies match your filters'
                    : 'No anomalies detected \u2014 the market is behaving within normal parameters'}
                </p>
                {hasActiveFilters && (
                  <button onClick={clearFilters} className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline">Clear filters</button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto -mx-6">
                <table className="w-full text-sm" style={{ minWidth: '400px' }}>
                  <thead>
                    <tr className="border-b border-neutral-200 dark:border-neutral-700 text-left text-xs text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                      <th className="px-6 py-2 cursor-pointer hover:text-neutral-700 dark:hover:text-neutral-200" onClick={() => handleSort('ticker')}>
                        Ticker <SortIcon field="ticker" />
                      </th>
                      <th className="px-3 py-2">Type</th>
                      <th className="px-3 py-2 cursor-pointer hover:text-neutral-700 dark:hover:text-neutral-200" onClick={() => handleSort('severity')}>
                        Severity <SortIcon field="severity" />
                      </th>
                      <th className="px-3 py-2 cursor-pointer hover:text-neutral-700 dark:hover:text-neutral-200" onClick={() => handleSort('z_score')}>
                        Z-Score <SortIcon field="z_score" />
                      </th>
                      <th className="px-3 py-2 cursor-pointer hover:text-neutral-700 dark:hover:text-neutral-200 hidden sm:table-cell" onClick={() => handleSort('confidence')}>
                        Confidence <SortIcon field="confidence" />
                      </th>
                      <th className="px-3 py-2 hidden sm:table-cell">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700">
                    {filtered.map((a, i) => (
                      <tr
                        key={`${a.ticker}-${a.anomaly_type}-${i}`}
                        className={cn(
                          'hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors cursor-pointer',
                          selectedTicker === a.ticker && 'bg-blue-50 dark:bg-blue-900/30',
                        )}
                        onClick={() => setSelectedTicker(selectedTicker === a.ticker ? null : a.ticker)}
                      >
                        <td className="px-6 py-2.5">
                          <span className="font-bold text-neutral-900 dark:text-white">${a.ticker}</span>
                        </td>
                        <td className="px-3 py-2.5 text-xs text-neutral-600 dark:text-neutral-400">{anomalyTypeLabel(a.anomaly_type)}</td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="w-12 h-1.5 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                              <div
                                className={cn('h-full rounded-full', severityBarColor(a.severity))}
                                style={{ width: `${Math.min(100, a.severity * 100)}%` }}
                              />
                            </div>
                            <SeverityBadge severity={a.severity} />
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={cn(
                            'text-xs font-medium',
                            Math.abs(a.z_score) > 3 ? 'text-red-600 dark:text-red-400' :
                            Math.abs(a.z_score) > 2 ? 'text-yellow-600 dark:text-yellow-400' :
                            'text-neutral-600 dark:text-neutral-400',
                          )}>
                            {formatNumber(a.z_score, 2)}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-xs text-neutral-600 dark:text-neutral-400 hidden sm:table-cell">{formatNumber(a.confidence, 2)}</td>
                        <td className="px-3 py-2.5 text-xs text-neutral-400 dark:text-neutral-500 hidden sm:table-cell">{formatRelativeTime(a.detected_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* -- TICKER DRILL-DOWN -- */}
          {selectedTicker && (
            <TickerDrillDown
              ticker={selectedTicker}
              onClose={() => setSelectedTicker(null)}
            />
          )}
        </div>

        {/* ---------- RIGHT COLUMN (4/12) ---------- */}
        <div className="lg:col-span-4 space-y-6">

          {/* -- TYPE BREAKDOWN -- */}
          <div className="card">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-purple-500" />
              Type Breakdown
            </h2>

            {allAnomalies.isLoading ? (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <div key={i} className="h-6 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : typeBreakdown.length === 0 ? (
              <p className="text-xs text-neutral-400 dark:text-neutral-500 py-4 text-center">No data</p>
            ) : (
              <div className="space-y-2">
                {typeBreakdown.map(([type, count]) => (
                  <button
                    key={type}
                    onClick={() => setTypeFilter(typeFilter === type ? null : type)}
                    className={cn(
                      'w-full flex items-center gap-2 p-1.5 rounded-lg transition-colors text-left',
                      typeFilter === type ? 'bg-blue-50 ring-1 ring-blue-200 dark:bg-blue-900/30 dark:ring-blue-700' : 'hover:bg-neutral-50 dark:hover:bg-neutral-800',
                    )}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-neutral-700 dark:text-neutral-300 truncate">{anomalyTypeLabel(type)}</div>
                      <div className="w-full h-1.5 bg-neutral-100 dark:bg-neutral-700 rounded-full overflow-hidden mt-1">
                        <div
                          className="h-full bg-purple-500 rounded-full"
                          style={{ width: `${(count / maxTypeCount) * 100}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-xs font-semibold text-neutral-600 dark:text-neutral-300 shrink-0">{count}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* -- SEVERITY DISTRIBUTION -- */}
          <div className="card">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-orange-500" />
              Severity Distribution
            </h2>

            {allAnomalies.isLoading ? (
              <div className="h-20 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
            ) : anomalies.length === 0 ? (
              <p className="text-xs text-neutral-400 dark:text-neutral-500 py-4 text-center">No data</p>
            ) : (
              <div>
                <div className="space-y-2 mb-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-sm bg-red-500" />
                      <span className="text-neutral-600 dark:text-neutral-400">High (&ge;0.7)</span>
                    </span>
                    <span className="font-semibold text-neutral-900 dark:text-white">{severityDist.high}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-sm bg-yellow-500" />
                      <span className="text-neutral-600 dark:text-neutral-400">Medium (0.4&ndash;0.7)</span>
                    </span>
                    <span className="font-semibold text-neutral-900 dark:text-white">{severityDist.medium}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-sm bg-blue-500" />
                      <span className="text-neutral-600 dark:text-neutral-400">Low (&lt;0.4)</span>
                    </span>
                    <span className="font-semibold text-neutral-900 dark:text-white">{severityDist.low}</span>
                  </div>
                </div>
                {/* Stacked bar */}
                <div className="w-full h-2.5 bg-neutral-100 dark:bg-neutral-700 rounded-full overflow-hidden flex">
                  {severityDist.high > 0 && (
                    <div className="bg-red-500 h-full" style={{ width: `${(severityDist.high / severityDist.total) * 100}%` }} />
                  )}
                  {severityDist.medium > 0 && (
                    <div className="bg-yellow-500 h-full" style={{ width: `${(severityDist.medium / severityDist.total) * 100}%` }} />
                  )}
                  {severityDist.low > 0 && (
                    <div className="bg-blue-500 h-full" style={{ width: `${(severityDist.low / severityDist.total) * 100}%` }} />
                  )}
                </div>
              </div>
            )}
          </div>

          {/* -- TOP AFFECTED TICKERS -- */}
          <div className="card">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-1.5">
              <Target className="w-4 h-4 text-red-500" />
              Top Affected Tickers
            </h2>

            {allAnomalies.isLoading ? (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => <div key={i} className="h-6 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : topTickers.length === 0 ? (
              <p className="text-xs text-neutral-400 dark:text-neutral-500 py-4 text-center">No data</p>
            ) : (
              <div className="space-y-1.5">
                {topTickers.map(([ticker, count]) => (
                  <button
                    key={ticker}
                    onClick={() => setSelectedTicker(selectedTicker === ticker ? null : ticker)}
                    className={cn(
                      'w-full flex items-center gap-2 p-1.5 rounded-lg transition-colors text-left',
                      selectedTicker === ticker ? 'bg-blue-50 ring-1 ring-blue-200 dark:bg-blue-900/30 dark:ring-blue-700' : 'hover:bg-neutral-50 dark:hover:bg-neutral-800',
                    )}
                  >
                    <span className="text-xs font-bold text-neutral-900 dark:text-white w-12">${ticker}</span>
                    <div className="flex-1 h-1.5 bg-neutral-100 dark:bg-neutral-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-red-500 rounded-full"
                        style={{ width: `${(count / maxTickerCount) * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-neutral-500 dark:text-neutral-400 shrink-0">{count}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ====== FOOTER ====== */}
      <div className="text-center text-xs text-neutral-400 dark:text-neutral-500 pt-2 border-t border-neutral-200 dark:border-neutral-700">
        Real-time anomaly detection across statistical, cross-asset, and time-series analysis
        {allAnomalies.data?.generated_at && (
          <span> &middot; Generated {formatRelativeTime(allAnomalies.data.generated_at)}</span>
        )}
      </div>
    </div>
  );
};

export default AnomalyExplorer;
