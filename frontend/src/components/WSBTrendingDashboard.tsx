import React, { useState, useMemo, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import {
  TrendingUp, TrendingDown, Activity, Users, MessageCircle,
  RefreshCw, AlertTriangle, Database, Zap, BarChart3,
  ArrowUpRight, ArrowDownRight, ChevronUp, ChevronDown,
} from 'lucide-react';

import {
  useWSBTrending, useLatestAlerts, useMarketAnomalies,
  useIngestionStatus, useSentimentAnalysis,
} from '../hooks/useWSBDashboard';
import { useFeaturesSummary, useFeatureHistory } from '../hooks/useFeatures';

import {
  cn, formatNumber, formatPercent, formatRelativeTime,
  getSentimentColor, getSentimentLabel, getReturnColor,
  prepareChartData,
} from '../utils/format';

import type { WSBTrendingTicker, Alert, Anomaly } from '../types/api';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Skeleton card for loading states */
const SkeletonCard: React.FC<{ lines?: number }> = ({ lines = 3 }) => (
  <div className="card animate-pulse">
    <div className="h-4 bg-neutral-200 dark:bg-neutral-700 rounded w-1/3 mb-4" />
    <div className="space-y-2">
      {[...Array(lines)].map((_, i) => (
        <div key={i} className="h-3 bg-neutral-200 dark:bg-neutral-700 rounded" style={{ width: `${80 - i * 15}%` }} />
      ))}
    </div>
  </div>
);

/** Mini KPI card for the market pulse strip */
const PulseCard: React.FC<{
  label: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
  isLoading?: boolean;
}> = ({ label, value, subtitle, icon, color, isLoading }) => {
  if (isLoading) {
    return (
      <div className="card animate-pulse">
        <div className="h-4 bg-neutral-200 dark:bg-neutral-700 rounded w-2/3 mb-2" />
        <div className="h-6 bg-neutral-200 dark:bg-neutral-700 rounded w-1/2" />
      </div>
    );
  }
  return (
    <div className="card hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wide">{label}</span>
        <span className={cn('p-1.5 rounded-lg', color)}>{icon}</span>
      </div>
      <div className="text-2xl font-bold text-neutral-900 dark:text-white">{value}</div>
      {subtitle && <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">{subtitle}</div>}
    </div>
  );
};

/** Severity badge for alerts */
const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
  const styles: Record<string, string> = {
    critical: 'bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800',
    high: 'bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400 dark:border-orange-800',
    medium: 'bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-800',
    low: 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800',
  };
  return (
    <span className={cn('px-1.5 py-0.5 text-[10px] font-semibold rounded border uppercase', styles[severity] || styles.low)}>
      {severity}
    </span>
  );
};

/** Sort indicator arrow */
const SortIcon: React.FC<{ active: boolean; direction: 'asc' | 'desc' }> = ({ active, direction }) => {
  if (!active) return <span className="text-neutral-300 dark:text-neutral-600 ml-0.5 inline-block w-3"><ChevronUp className="w-3 h-3" /></span>;
  return direction === 'asc'
    ? <ChevronUp className="w-3 h-3 ml-0.5 text-blue-600 dark:text-blue-400 inline-block" />
    : <ChevronDown className="w-3 h-3 ml-0.5 text-blue-600 dark:text-blue-400 inline-block" />;
};

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

const WSBTrendingDashboard: React.FC = () => {
  const navigate = useNavigate();

  // State
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [sortColumn, setSortColumn] = useState<string>('trending_score');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Data hooks
  const trending = useWSBTrending(7, 25);
  const alerts = useLatestAlerts(24);
  const anomalies = useMarketAnomalies();
  const ingestion = useIngestionStatus();
  const sentiment = useSentimentAnalysis();
  const featuresSummary = useFeaturesSummary(undefined, 50);

  // Feature history for selected ticker
  const effectiveTicker = selectedTicker || trending.data?.trending_tickers?.[0]?.ticker || '';
  const featureHistory = useFeatureHistory(effectiveTicker, 30);

  // ---- Derived data ----

  // Cross-reference trending tickers with feature summary
  const enrichedTrending = useMemo(() => {
    const tickers = trending.data?.trending_tickers;
    if (!tickers) return [];
    const featureMap = new Map(
      (featuresSummary.data?.features || []).map(f => [f.ticker, f]),
    );
    return tickers.map(t => ({
      ...t,
      ret_5d: featureMap.get(t.ticker)?.ret_5d ?? null,
      vol_z: featureMap.get(t.ticker)?.vol_z ?? null,
      sent_mean_7d: featureMap.get(t.ticker)?.sent_mean_7d ?? null,
    }));
  }, [trending.data, featuresSummary.data]);

  // Sorted trending
  const sortedTrending = useMemo(() => {
    const arr = [...enrichedTrending];
    arr.sort((a, b) => {
      const aVal = (a as any)[sortColumn] ?? -Infinity;
      const bVal = (b as any)[sortColumn] ?? -Infinity;
      return sortDirection === 'desc' ? bVal - aVal : aVal - bVal;
    });
    return arr;
  }, [enrichedTrending, sortColumn, sortDirection]);

  // Chart data
  const chartData = useMemo(() => {
    if (!featureHistory.data?.features) return [];
    return prepareChartData(featureHistory.data.features, 'date', 'sent_mean_7d');
  }, [featureHistory.data]);

  const returnsChartData = useMemo(() => {
    if (!featureHistory.data?.features) return [];
    return prepareChartData(featureHistory.data.features, 'date', 'ret_5d');
  }, [featureHistory.data]);

  // ---- Handlers ----

  const handleRefreshAll = useCallback(() => {
    trending.refetch();
    alerts.refetch();
    anomalies.refetch();
    ingestion.refetch();
    sentiment.refetch();
    featuresSummary.refetch();
  }, [trending, alerts, anomalies, ingestion, sentiment, featuresSummary]);

  const handleSort = useCallback((col: string) => {
    if (sortColumn === col) {
      setSortDirection(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(col);
      setSortDirection('desc');
    }
  }, [sortColumn]);

  // ---- Helpers ----

  const trendingScoreColor = (score: number) => {
    if (score >= 0.7) return 'text-purple-700 bg-purple-100 dark:text-purple-300 dark:bg-purple-900/30';
    if (score >= 0.5) return 'text-blue-700 bg-blue-100 dark:text-blue-300 dark:bg-blue-900/30';
    if (score >= 0.3) return 'text-yellow-700 bg-yellow-100 dark:text-yellow-300 dark:bg-yellow-900/30';
    return 'text-neutral-600 bg-neutral-100 dark:text-neutral-400 dark:bg-neutral-700';
  };

  const sentimentBarColor = (s: number) => {
    if (s >= 0.6) return 'from-green-400 to-green-600';
    if (s >= 0.4) return 'from-yellow-400 to-yellow-600';
    return 'from-red-400 to-red-600';
  };

  const anomalyTypeLabel = (t: string) => t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  const alertTypeIcon = (type: string) => {
    if (type.includes('sentiment')) return '💭';
    if (type.includes('momentum') || type.includes('breakout')) return '📈';
    if (type.includes('volume')) return '📊';
    if (type.includes('wsb') || type.includes('viral')) return '🚀';
    if (type.includes('price')) return '💰';
    return '⚡';
  };

  // ---- KPI values ----

  const trendingCount = trending.data?.total_found ?? 0;
  const overallSentiment = sentiment.data?.overall_sentiment;
  const alertCount = alerts.data?.count ?? 0;
  const pipelineHealth = ingestion.data
    ? `${ingestion.data.operational_sources}/${ingestion.data.total_sources}`
    : '—';

  // ===========================================================================
  // RENDER
  // ===========================================================================

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* ====== HEADER ====== */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-white">🦍 WSB Terminal</h1>
          <span className="flex items-center gap-1.5 px-2.5 py-1 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-xs font-semibold rounded-full">
            <span className="w-2 h-2 rounded-full bg-red-500 pulse-green" />
            LIVE
          </span>
        </div>
        <div className="flex items-center gap-3">
          {trending.dataUpdatedAt && (
            <span className="text-xs text-neutral-500 dark:text-neutral-400">
              Updated {new Date(trending.dataUpdatedAt).toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={handleRefreshAll}
            className="p-2 text-neutral-500 hover:text-blue-600 hover:bg-blue-50 dark:text-neutral-400 dark:hover:text-blue-400 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
            title="Refresh all panels"
          >
            <RefreshCw className={cn('w-4 h-4', trending.isFetching && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* ====== MARKET PULSE STRIP ====== */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <PulseCard
          label="Trending Tickers"
          value={trendingCount}
          subtitle={`Past ${trending.data?.days ?? 7} days`}
          icon={<TrendingUp className="w-4 h-4" />}
          color="bg-purple-50 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400"
          isLoading={trending.isLoading}
        />
        <PulseCard
          label="Market Sentiment"
          value={overallSentiment ? formatNumber(overallSentiment.score, 2) : '—'}
          subtitle={overallSentiment?.label ?? 'Loading...'}
          icon={<Activity className="w-4 h-4" />}
          color={cn(
            overallSentiment && overallSentiment.score > 0.6 ? 'bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400' :
            overallSentiment && overallSentiment.score < 0.4 ? 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400' :
            'bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400',
          )}
          isLoading={sentiment.isLoading}
        />
        <PulseCard
          label="Active Alerts"
          value={alertCount}
          subtitle="Past 24h"
          icon={<Zap className="w-4 h-4" />}
          color="bg-orange-50 text-orange-600 dark:bg-orange-900/20 dark:text-orange-400"
          isLoading={alerts.isLoading}
        />
        <PulseCard
          label="Pipeline Health"
          value={pipelineHealth}
          subtitle={ingestion.data ? `${ingestion.data.system_health ?? 'checking'}` : undefined}
          icon={<Database className="w-4 h-4" />}
          color={cn(
            ingestion.data?.system_health === 'healthy' ? 'bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400' :
            'bg-yellow-50 text-yellow-600 dark:bg-yellow-900/20 dark:text-yellow-400',
          )}
          isLoading={ingestion.isLoading}
        />
      </div>

      {/* ====== MAIN GRID ====== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ---------- LEFT COLUMN (8/12) ---------- */}
        <div className="lg:col-span-8 space-y-6">

          {/* -- WSB TRENDING TABLE -- */}
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between px-1 mb-4">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-purple-600" />
                Trending on r/wallstreetbets
              </h2>
              <span className="text-xs text-neutral-500 dark:text-neutral-400">
                {enrichedTrending.length} tickers
              </span>
            </div>

            {trending.isLoading ? (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-10 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
                ))}
              </div>
            ) : trending.error ? (
              <div className="text-center py-8">
                <AlertTriangle className="w-8 h-8 text-red-400 dark:text-red-500 mx-auto mb-2" />
                <p className="text-neutral-600 dark:text-neutral-400 text-sm">Failed to load trending data</p>
                <button onClick={() => trending.refetch()} className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline">Retry</button>
              </div>
            ) : sortedTrending.length === 0 ? (
              <div className="text-center py-12">
                <span className="text-4xl block mb-2">🦍</span>
                <p className="text-neutral-500 dark:text-neutral-400">No trending tickers found</p>
                <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">WSB data will appear here when available</p>
              </div>
            ) : (
              <div className="overflow-x-auto -mx-6">
                <table className="w-full text-sm" style={{ minWidth: '400px' }}>
                  <thead>
                    <tr className="border-b border-neutral-200 dark:border-neutral-700 text-left text-xs text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                      <th className="px-6 py-2 w-10">#</th>
                      <ThSortable col="ticker" label="Ticker" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                      <ThSortable col="trending_score" label="Score" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                      <ThSortable col="mention_count" label="Mentions" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                      <th className="px-3 py-2">Sentiment</th>
                      <ThSortable col="avg_reddit_score" label="Reddit" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} className="hidden md:table-cell" />
                      <ThSortable col="avg_comments" label="Comments" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} className="hidden md:table-cell" />
                      <ThSortable col="ret_5d" label="5d Ret" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700">
                    {sortedTrending.map((t, idx) => {
                      const originalIdx = enrichedTrending.findIndex(e => e.ticker === t.ticker);
                      const isSelected = effectiveTicker === t.ticker;
                      return (
                        <tr
                          key={t.ticker}
                          onClick={() => setSelectedTicker(t.ticker)}
                          className={cn(
                            'cursor-pointer transition-colors hover:bg-blue-50 dark:hover:bg-blue-900/30',
                            isSelected && 'bg-blue-50 dark:bg-blue-900/30 border-l-2 border-l-blue-500',
                          )}
                        >
                          <td className="px-6 py-2.5 font-medium text-neutral-400 dark:text-neutral-500">
                            {originalIdx === 0 ? '🥇' : originalIdx === 1 ? '🥈' : originalIdx === 2 ? '🥉' : originalIdx + 1}
                          </td>
                          <td className="px-3 py-2.5">
                            <Link to={`/stocks/${t.ticker}`} className="font-bold text-neutral-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400" onClick={e => e.stopPropagation()}>
                              ${t.ticker}
                            </Link>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className={cn('px-2 py-0.5 rounded text-xs font-semibold', trendingScoreColor(t.trending_score))}>
                              {t.trending_score.toFixed(2)}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 font-medium text-neutral-900 dark:text-white">{t.mention_count}</td>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-1.5 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                                <div
                                  className={cn('h-full rounded-full bg-gradient-to-r', sentimentBarColor(t.avg_sentiment))}
                                  style={{ width: `${Math.max(t.avg_sentiment * 100, 5)}%` }}
                                />
                              </div>
                              <span className={cn('text-xs font-medium', getSentimentColor(t.avg_sentiment))}>
                                {formatNumber(t.avg_sentiment, 2)}
                              </span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5 text-neutral-700 dark:text-neutral-300 hidden md:table-cell">{formatNumber(t.avg_reddit_score, 0)}</td>
                          <td className="px-3 py-2.5 text-neutral-700 dark:text-neutral-300 hidden md:table-cell">{formatNumber(t.avg_comments, 0)}</td>
                          <td className="px-3 py-2.5">
                            {t.ret_5d !== null ? (
                              <span className={cn('flex items-center gap-0.5 font-medium text-xs', getReturnColor(t.ret_5d))}>
                                {t.ret_5d > 0 ? <ArrowUpRight className="w-3 h-3" /> : t.ret_5d < 0 ? <ArrowDownRight className="w-3 h-3" /> : null}
                                {formatPercent(t.ret_5d, 1)}
                              </span>
                            ) : (
                              <span className="text-neutral-400 dark:text-neutral-500 text-xs">—</span>
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

          {/* -- SENTIMENT HEATMAP -- */}
          {sentiment.data?.stock_breakdown && sentiment.data.stock_breakdown.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-2">
                <Activity className="w-5 h-5 text-blue-600" />
                Sentiment Heatmap
              </h2>
              <div className="flex flex-wrap gap-2">
                {sentiment.data.stock_breakdown.map(s => {
                  const bg = s.sentiment >= 0.6 ? 'bg-green-100 border-green-200 text-green-800 dark:bg-green-900/30 dark:border-green-800 dark:text-green-300'
                    : s.sentiment >= 0.4 ? 'bg-yellow-50 border-yellow-200 text-yellow-800 dark:bg-yellow-900/30 dark:border-yellow-800 dark:text-yellow-300'
                    : 'bg-red-100 border-red-200 text-red-800 dark:bg-red-900/30 dark:border-red-800 dark:text-red-300';
                  const isSelected = effectiveTicker === s.ticker;
                  return (
                    <button
                      key={s.ticker}
                      onClick={() => navigate(`/stocks/${s.ticker}`)}
                      className={cn(
                        'px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all hover:shadow-sm hover:scale-105',
                        bg,
                        isSelected && 'ring-2 ring-blue-500 ring-offset-1',
                      )}
                      title={`View ${s.ticker} details`}
                    >
                      {s.ticker} <span className="font-normal">{formatNumber(s.sentiment, 2)}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* -- SELECTED TICKER CHART -- */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-green-600" />
                {effectiveTicker ? `$${effectiveTicker} — 30-Day Trends` : 'Select a ticker'}
              </h2>
              {effectiveTicker && (
                <Link to={`/stocks/${effectiveTicker}`} className="text-xs text-blue-600 hover:underline">
                  Full detail →
                </Link>
              )}
            </div>

            {!effectiveTicker ? (
              <div className="text-center py-12 text-neutral-400 dark:text-neutral-500">
                Click a ticker in the table or heatmap to view its trend
              </div>
            ) : featureHistory.isLoading ? (
              <div className="h-48 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
            ) : featureHistory.error || (chartData.length === 0 && returnsChartData.length === 0) ? (
              <div className="text-center py-12 text-neutral-400 dark:text-neutral-500 text-sm">
                No feature history available for ${effectiveTicker}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Sentiment chart */}
                {chartData.length > 0 && (
                  <div>
                    <h3 className="text-xs font-medium text-neutral-500 dark:text-neutral-400 mb-2 uppercase tracking-wide">Sentiment (7d Mean)</h3>
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" className="dark:stroke-neutral-700" />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 10, fill: '#737373' }}
                          tickFormatter={(d: string) => {
                            try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); } catch { return d; }
                          }}
                        />
                        <YAxis tick={{ fontSize: 10, fill: '#737373' }} domain={[0, 1]} />
                        <Tooltip
                          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e5e5' }}
                          formatter={(v: number) => [formatNumber(v, 3), 'Sentiment']}
                          labelFormatter={(d: string) => {
                            try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
                          }}
                        />
                        <Line type="monotone" dataKey="value" stroke="#10b981" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
                {/* Returns chart */}
                {returnsChartData.length > 0 && (
                  <div>
                    <h3 className="text-xs font-medium text-neutral-500 dark:text-neutral-400 mb-2 uppercase tracking-wide">Returns (5d)</h3>
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={returnsChartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" className="dark:stroke-neutral-700" />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 10, fill: '#737373' }}
                          tickFormatter={(d: string) => {
                            try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); } catch { return d; }
                          }}
                        />
                        <YAxis tick={{ fontSize: 10, fill: '#737373' }} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
                        <Tooltip
                          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e5e5' }}
                          formatter={(v: number) => [formatPercent(v, 2), 'Return 5d']}
                          labelFormatter={(d: string) => {
                            try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
                          }}
                        />
                        <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ---------- RIGHT COLUMN (4/12) ---------- */}
        <div className="lg:col-span-4 space-y-6">

          {/* -- LIVE ALERTS FEED -- */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-white flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-orange-500" />
                Live Alerts
              </h2>
              <span className="text-[10px] text-neutral-400 dark:text-neutral-500">{alertCount} in 24h</span>
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
                {alerts.data!.alerts.map((a: Alert) => (
                  <div key={a.id} className="p-2.5 bg-neutral-50 dark:bg-neutral-800 rounded-lg border border-neutral-100 dark:border-neutral-700 hover:border-neutral-200 dark:hover:border-neutral-600 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">{alertTypeIcon(a.alert_type)}</span>
                        <Link to={`/stocks/${a.ticker}`} className="font-bold text-xs text-neutral-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400">
                          ${a.ticker}
                        </Link>
                        <SeverityBadge severity={a.severity} />
                      </div>
                      <span className="text-[10px] text-neutral-400 dark:text-neutral-500">{formatRelativeTime(a.triggered_at)}</span>
                    </div>
                    <p className="text-[11px] text-neutral-600 dark:text-neutral-400 leading-tight line-clamp-2">{a.title}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* -- MARKET ANOMALIES -- */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-white flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-red-500" />
                Anomalies
              </h2>
            </div>

            {anomalies.isLoading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => <div key={i} className="h-10 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : anomalies.error ? (
              <p className="text-xs text-red-500 dark:text-red-400 py-4 text-center">Failed to load anomalies</p>
            ) : (anomalies.data?.market_anomalies?.length ?? 0) === 0 ? (
              <p className="text-xs text-neutral-400 dark:text-neutral-500 py-6 text-center">No anomalies detected</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                {anomalies.data!.market_anomalies.slice(0, 10).map((a: Anomaly, i: number) => (
                  <div key={`${a.ticker}-${a.anomaly_type}-${i}`} className="p-2.5 rounded-lg border border-neutral-100 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800">
                    <div className="flex items-center justify-between mb-1">
                      <Link to={`/stocks/${a.ticker}`} className="font-bold text-xs text-neutral-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400">
                        ${a.ticker}
                      </Link>
                      <span className={cn(
                        'text-[10px] font-semibold px-1.5 py-0.5 rounded',
                        a.severity >= 0.7 ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                        a.severity >= 0.4 ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' :
                        'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
                      )}>
                        {formatNumber(a.severity, 2)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-neutral-500 dark:text-neutral-400">{anomalyTypeLabel(a.anomaly_type)}</span>
                      <span className="text-neutral-400 dark:text-neutral-500">z={formatNumber(a.z_score, 1)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* -- PIPELINE STATUS -- */}
          <div className="card">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-1.5">
              <Database className="w-4 h-4 text-blue-500" />
              Data Pipeline
            </h2>

            {ingestion.isLoading ? (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <div key={i} className="h-6 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : ingestion.error ? (
              <p className="text-xs text-red-500 dark:text-red-400 py-2 text-center">Failed to load</p>
            ) : (
              <div className="space-y-2">
                {ingestion.data?.sources.map(src => {
                  const statusColor = src.status === 'operational' ? 'bg-green-500' :
                    src.status === 'degraded' ? 'bg-yellow-500' : 'bg-red-500';
                  const statusBg = src.status === 'operational' ? 'bg-green-50 dark:bg-green-900/20' :
                    src.status === 'degraded' ? 'bg-yellow-50 dark:bg-yellow-900/20' : 'bg-red-50 dark:bg-red-900/20';
                  return (
                    <div key={src.name} className={cn('flex items-center justify-between p-2 rounded-lg', statusBg)}>
                      <div className="flex items-center gap-2">
                        <span className={cn('w-2 h-2 rounded-full', statusColor)} />
                        <span className="text-xs font-medium text-neutral-700 dark:text-neutral-300">{src.name}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[10px] text-neutral-500 dark:text-neutral-400">
                        <span>{src.article_count} articles</span>
                        {src.freshness_minutes !== null && (
                          <span>{src.freshness_minutes < 60 ? `${Math.round(src.freshness_minutes)}m ago` : `${Math.round(src.freshness_minutes / 60)}h ago`}</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* -- QUICK STATS from sentiment analysis -- */}
          {sentiment.data?.statistics && (
            <div className="card">
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-1.5">
                <BarChart3 className="w-4 h-4 text-indigo-500" />
                Coverage
              </h2>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
                  <div className="text-lg font-bold text-neutral-900 dark:text-white">{sentiment.data.statistics.stocks_analyzed}</div>
                  <div className="text-[10px] text-neutral-500 dark:text-neutral-400">Stocks</div>
                </div>
                <div className="p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
                  <div className="text-lg font-bold text-neutral-900 dark:text-white">{sentiment.data.statistics.total_articles}</div>
                  <div className="text-[10px] text-neutral-500 dark:text-neutral-400">Articles</div>
                </div>
                <div className="p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
                  <div className="text-lg font-bold text-neutral-900 dark:text-white">{formatNumber(sentiment.data.statistics.avg_sentiment, 2)}</div>
                  <div className="text-[10px] text-neutral-500 dark:text-neutral-400">Avg Sent</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ====== FOOTER ====== */}
      <div className="text-center text-xs text-neutral-400 dark:text-neutral-500 pt-2 border-t border-neutral-200 dark:border-neutral-700">
        Data sourced from r/wallstreetbets, SEC EDGAR, Google News, and computed features
        {trending.data?.generated_at && (
          <span> · Last generated {formatRelativeTime(trending.data.generated_at)}</span>
        )}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Sortable Table Header
// ---------------------------------------------------------------------------

const ThSortable: React.FC<{
  col: string;
  label: string;
  sortColumn: string;
  sortDirection: 'asc' | 'desc';
  onSort: (col: string) => void;
  className?: string;
}> = ({ col, label, sortColumn, sortDirection, onSort, className }) => (
  <th
    className={cn("px-3 py-2 cursor-pointer select-none hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors", className)}
    onClick={() => onSort(col)}
  >
    <span className="inline-flex items-center">
      {label}
      <SortIcon active={sortColumn === col} direction={sortDirection} />
    </span>
  </th>
);

export default WSBTrendingDashboard;
