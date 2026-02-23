import React, { useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Brain, Calendar, Shield, Target, RefreshCw, AlertTriangle,
  TrendingUp, Activity, Zap, ArrowUpRight,
  ArrowDownRight, CheckCircle, ChevronRight, Clock,
} from 'lucide-react';

import {
  useTomorrowOutlook, useIntelMarketOverview,
  usePressureTest, useDailyRecommendations, useMorningBrief,
} from '../hooks/useMarketIntelligence';
import {
  useSentimentAnalysis, useLatestAlerts, useMarketAnomalies,
} from '../hooks/useWSBDashboard';
import { useFeaturesSummary } from '../hooks/useFeatures';

import {
  cn, formatNumber, formatPercent, formatRelativeTime,
  getSentimentColor, getReturnColor,
} from '../utils/format';

import type { Alert, Anomaly, Recommendation } from '../types/api';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

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

const ActionBadge: React.FC<{ action: string }> = ({ action }) => {
  const styles: Record<string, string> = {
    buy: 'bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800',
    sell: 'bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800',
    hold: 'bg-neutral-100 text-neutral-600 border-neutral-200 dark:bg-neutral-700 dark:text-neutral-400 dark:border-neutral-600',
  };
  return (
    <span className={cn('px-2 py-0.5 text-xs font-bold rounded border uppercase', styles[action] || styles.hold)}>
      {action}
    </span>
  );
};

const StatusDot: React.FC<{ status: string }> = ({ status }) => {
  const isGood = status.includes('OPERATIONAL') || status.includes('EXCELLENT') || status.includes('WORKING') || status.includes('READY');
  const isPartial = status.includes('FUNCTIONAL') || status.includes('%');
  const dotColor = isGood ? 'bg-green-500' : isPartial ? 'bg-yellow-500' : 'bg-neutral-400';
  return (
    <div className="flex items-center gap-2">
      <span className={cn('w-2 h-2 rounded-full', dotColor)} />
      <span className="text-xs text-neutral-600 dark:text-neutral-400">{status}</span>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const MarketIntelligence: React.FC = () => {
  // Data hooks — each panel loads independently
  const outlook = useTomorrowOutlook();
  const overview = useIntelMarketOverview();
  const sentiment = useSentimentAnalysis();
  const alerts = useLatestAlerts(24);
  const anomalies = useMarketAnomalies();
  const recommendations = useDailyRecommendations();
  const pressureTest = usePressureTest();
  const morningBrief = useMorningBrief();
  const featuresSummary = useFeaturesSummary(undefined, 50);

  // Enriched stock data: cross-reference overview stocks with features + morning brief
  const enrichedStocks = useMemo(() => {
    const stocks = overview.data?.recent_stocks;
    if (!stocks) return [];
    const featureMap = new Map(
      (featuresSummary.data?.features || []).map(f => [f.ticker, f]),
    );
    const briefMap = new Map(
      (morningBrief.data?.stocks || []).map((s: any) => [s.ticker, s]),
    );
    return stocks.map(s => {
      const brief = briefMap.get(s.ticker);
      return {
        ...s,
        vol_z: featureMap.get(s.ticker)?.vol_z ?? s.volume_z,
        article_count_7d: featureMap.get(s.ticker)?.article_count_7d ?? s.articles,
        sentiment_trend_direction: brief?.sentiment_trend_direction ?? null,
        top_event: brief?.top_event ?? null,
        narrative: brief?.narrative ?? null,
      };
    });
  }, [overview.data, featuresSummary.data, morningBrief.data]);

  // Refresh all panels
  const handleRefreshAll = useCallback(() => {
    outlook.refetch();
    overview.refetch();
    sentiment.refetch();
    alerts.refetch();
    anomalies.refetch();
    recommendations.refetch();
    pressureTest.refetch();
    featuresSummary.refetch();
    morningBrief.refetch();
  }, [outlook, overview, sentiment, alerts, anomalies, recommendations, pressureTest, featuresSummary, morningBrief]);

  // Helpers
  const sentimentBarColor = (s: number) => {
    if (s >= 0.6) return 'from-green-400 to-green-600';
    if (s >= 0.4) return 'from-yellow-400 to-yellow-600';
    return 'from-red-400 to-red-600';
  };

  const outlookGradient = (label: string) => {
    if (label === 'OPTIMISTIC') return 'from-green-600 to-emerald-700';
    if (label === 'DEFENSIVE') return 'from-red-600 to-rose-700';
    return 'from-blue-600 to-indigo-700';
  };

  const alertTypeIcon = (type: string) => {
    if (type.includes('sentiment')) return '💭';
    if (type.includes('momentum') || type.includes('breakout')) return '📈';
    if (type.includes('volume')) return '📊';
    if (type.includes('wsb') || type.includes('viral')) return '🚀';
    if (type.includes('price')) return '💰';
    return '⚡';
  };

  const anomalyTypeLabel = (t: string) => t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  // KPI values
  const systemHealth = overview.data?.system_health;
  const overallSentiment = sentiment.data?.overall_sentiment;
  const alertCount = alerts.data?.count ?? 0;

  // =========================================================================
  // RENDER
  // =========================================================================

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">

      {/* ====== HEADER ====== */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <Brain className="w-6 h-6 text-purple-600" />
            AI Intelligence
          </h1>
          <span className="flex items-center gap-1.5 px-2.5 py-1 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400 text-xs font-semibold rounded-full">
            <span className="w-2 h-2 rounded-full bg-green-500 pulse-green" />
            LIVE
          </span>
        </div>
        <div className="flex items-center gap-3">
          {outlook.dataUpdatedAt && (
            <span className="text-xs text-neutral-500 dark:text-neutral-400">
              Updated {new Date(outlook.dataUpdatedAt).toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={handleRefreshAll}
            className="p-2 text-neutral-500 dark:text-neutral-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
            title="Refresh all panels"
          >
            <RefreshCw className={cn('w-4 h-4', (outlook.isFetching || overview.isFetching) && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* ====== TOMORROW'S OUTLOOK (HERO) ====== */}
      {outlook.isLoading ? (
        <div className="card animate-pulse h-36" />
      ) : outlook.error ? (
        <div className="card border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20">
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-sm">
            <AlertTriangle className="w-4 h-4" />
            <span>Failed to load tomorrow's outlook</span>
            <button onClick={() => outlook.refetch()} className="ml-auto text-xs text-red-600 dark:text-red-400 hover:underline">Retry</button>
          </div>
        </div>
      ) : outlook.data ? (
        <div className={cn('rounded-xl p-6 text-white bg-gradient-to-r', outlookGradient(outlook.data.market_sentiment.label))}>
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            {/* Left: Date + Sentiment */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-white/80 text-sm">
                <Calendar className="w-4 h-4" />
                <span>Outlook for {outlook.data.outlook_date}</span>
              </div>
              <div className="flex items-center gap-4">
                <div>
                  <div className="text-4xl font-bold">{outlook.data.market_sentiment.label}</div>
                  <div className="text-white/70 text-sm mt-1">
                    Sentiment Score: {formatNumber(outlook.data.market_sentiment.score, 2)}
                  </div>
                </div>
                {/* Gauge */}
                <div className="hidden md:flex flex-col items-center">
                  <div className="relative w-20 h-10 overflow-hidden">
                    <div className="absolute inset-0 border-t-4 border-l-4 border-r-4 border-white/30 dark:border-white/40 rounded-t-full" />
                    <div
                      className="absolute bottom-0 left-1/2 w-1 h-8 bg-white dark:bg-white origin-bottom rounded-t"
                      style={{
                        transform: `rotate(${(outlook.data.market_sentiment.score - 0.5) * 180}deg)`,
                      }}
                    />
                  </div>
                  <span className="text-[10px] text-white/60 dark:text-white/70 mt-0.5">0 — 1</span>
                </div>
              </div>
            </div>

            {/* Center: Recommendation */}
            <div className="lg:text-center">
              <div className="text-xs uppercase tracking-wider text-white/60 mb-1">Recommendation</div>
              <div className="text-lg font-semibold">{outlook.data.recommendation.text}</div>
              <div className="text-xs text-white/60 mt-1">
                Confidence: {outlook.data.recommendation.confidence}
              </div>
            </div>

            {/* Right: Key Factors */}
            <div className="space-y-1">
              <div className="text-xs uppercase tracking-wider text-white/60 mb-1">Key Factors</div>
              {outlook.data.recommendation.key_factors.map((f, i) => (
                <div key={i} className="flex items-center gap-1.5 text-sm text-white/90">
                  <ChevronRight className="w-3 h-3 text-white/50" />
                  {f}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {/* ====== MARKET PULSE STRIP ====== */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <PulseCard
          label="Stocks Tracked"
          value={systemHealth?.stocks_tracked ?? '—'}
          subtitle={systemHealth?.status ?? 'Loading...'}
          icon={<Target className="w-4 h-4" />}
          color="bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400"
          isLoading={overview.isLoading}
        />
        <PulseCard
          label="Active Signals"
          value={systemHealth?.active_signals ?? '—'}
          subtitle="All tickers"
          icon={<Activity className="w-4 h-4" />}
          color="bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400"
          isLoading={overview.isLoading}
        />
        <PulseCard
          label="Alerts (24h)"
          value={alertCount}
          subtitle={`${alerts.data?.alerts?.filter((a: Alert) => a.severity === 'high' || a.severity === 'critical').length ?? 0} high priority`}
          icon={<Zap className="w-4 h-4" />}
          color="bg-orange-50 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400"
          isLoading={alerts.isLoading}
        />
        <PulseCard
          label="Sentiment"
          value={overallSentiment ? formatNumber(overallSentiment.score, 2) : '—'}
          subtitle={overallSentiment ? `${overallSentiment.label} (${overallSentiment.confidence})` : 'Loading...'}
          icon={<TrendingUp className="w-4 h-4" />}
          color={cn(
            overallSentiment && overallSentiment.score > 0.6 ? 'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400' :
            overallSentiment && overallSentiment.score < 0.4 ? 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400' :
            'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
          )}
          isLoading={sentiment.isLoading}
        />
      </div>

      {/* ====== MAIN GRID ====== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ---------- LEFT COLUMN (8/12) ---------- */}
        <div className="lg:col-span-8 space-y-6">

          {/* -- STOCK INTELLIGENCE TABLE -- */}
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between px-1 mb-4">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
                <Target className="w-5 h-5 text-blue-600" />
                Stock Intelligence
              </h2>
              <div className="flex items-center gap-2">
                {morningBrief.data?.generated_at && (
                  <span className="flex items-center gap-1 text-xs text-neutral-400 dark:text-neutral-500">
                    <Clock className="w-3 h-3" />
                    {new Date(morningBrief.data.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
                <span className="text-xs text-neutral-500 dark:text-neutral-400">
                  {enrichedStocks.length} stocks
                </span>
              </div>
            </div>

            {/* Market summary banner (LLM-generated, if available) */}
            {morningBrief.data?.market_summary && (
              <div className="mx-1 mb-4 px-3 py-2 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 rounded-lg text-xs text-neutral-700 dark:text-neutral-300 italic">
                <Brain className="w-3 h-3 inline-block mr-1.5 text-purple-500 shrink-0 relative top-[-1px]" />
                {morningBrief.data.market_summary}
              </div>
            )}

            {overview.isLoading ? (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-10 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
                ))}
              </div>
            ) : overview.error ? (
              <div className="text-center py-8">
                <AlertTriangle className="w-8 h-8 text-red-400 dark:text-red-500 mx-auto mb-2" />
                <p className="text-neutral-600 dark:text-neutral-400 text-sm">Failed to load stock data</p>
                <button onClick={() => overview.refetch()} className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline">Retry</button>
              </div>
            ) : enrichedStocks.length === 0 ? (
              <div className="text-center py-12">
                <Brain className="w-10 h-10 text-neutral-300 dark:text-neutral-600 mx-auto mb-2" />
                <p className="text-neutral-500 dark:text-neutral-400">No stock data available</p>
                <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">Data will appear when feature calculations run</p>
              </div>
            ) : (
              <div className="overflow-x-auto -mx-6">
                <table className="w-full text-sm" style={{ minWidth: '400px' }}>
                  <thead>
                    <tr className="border-b border-neutral-200 dark:border-neutral-700 text-left text-xs text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                      <th className="px-6 py-2">Ticker</th>
                      <th className="px-3 py-2">Sentiment</th>
                      <th className="px-3 py-2">5d Return</th>
                      <th className="px-3 py-2">Vol Z</th>
                      <th className="px-3 py-2">Articles</th>
                      <th className="px-3 py-2 hidden md:table-cell">Insight</th>
                      <th className="px-3 py-2 hidden sm:table-cell">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700">
                    {enrichedStocks.map(s => {
                      const arrow = s.sentiment_trend_direction === 'improving' ? '↑'
                        : s.sentiment_trend_direction === 'declining' ? '↓' : null;
                      const arrowColor = s.sentiment_trend_direction === 'improving'
                        ? 'text-green-600 dark:text-green-400'
                        : 'text-red-600 dark:text-red-400';
                      const insightText = s.top_event || (s.narrative ? s.narrative.slice(0, 60) + (s.narrative.length > 60 ? '…' : '') : null);
                      return (
                        <tr key={s.ticker} className="hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors">
                          <td className="px-6 py-2.5">
                            <Link to={`/stocks/${s.ticker}`} className="font-bold text-neutral-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400">
                              {s.ticker}
                            </Link>
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-1.5 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                                <div
                                  className={cn('h-full rounded-full bg-gradient-to-r', sentimentBarColor(s.sentiment))}
                                  style={{ width: `${Math.max(s.sentiment * 100, 5)}%` }}
                                />
                              </div>
                              <span className={cn('text-xs font-medium', getSentimentColor(s.sentiment))}>
                                {formatNumber(s.sentiment, 2)}
                              </span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className={cn('flex items-center gap-0.5 font-medium text-xs', getReturnColor(s.returns))}>
                              {s.returns > 0 ? <ArrowUpRight className="w-3 h-3" /> : s.returns < 0 ? <ArrowDownRight className="w-3 h-3" /> : null}
                              {formatPercent(s.returns, 1)}
                            </span>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className={cn(
                              'text-xs font-medium',
                              s.vol_z !== null && Math.abs(s.vol_z) > 2 ? 'text-red-600 dark:text-red-400' :
                              s.vol_z !== null && Math.abs(s.vol_z) > 1 ? 'text-yellow-600 dark:text-yellow-400' :
                              'text-neutral-600 dark:text-neutral-400',
                            )}>
                              {s.vol_z !== null ? formatNumber(s.vol_z, 1) : '—'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-neutral-600 dark:text-neutral-400 text-xs">{s.article_count_7d}</td>
                          <td className="px-3 py-2.5 hidden md:table-cell max-w-[180px]">
                            {(arrow || insightText) ? (
                              <div className="flex items-start gap-1">
                                {arrow && <span className={cn('font-bold text-sm shrink-0', arrowColor)}>{arrow}</span>}
                                {insightText && (
                                  <span className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-tight line-clamp-2">{insightText}</span>
                                )}
                              </div>
                            ) : (
                              <span className="text-neutral-300 dark:text-neutral-600 text-xs">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5 text-neutral-400 dark:text-neutral-500 text-xs hidden sm:table-cell">{s.date}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* -- DAILY RECOMMENDATIONS -- */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
                <Shield className="w-5 h-5 text-green-600" />
                Daily Recommendations
              </h2>
              {recommendations.data && (
                <span className="text-xs text-neutral-400 dark:text-neutral-500">
                  Model {recommendations.data.model_version}
                </span>
              )}
            </div>

            {recommendations.isLoading ? (
              <SkeletonCard lines={4} />
            ) : recommendations.error ? (
              <div className="text-center py-8">
                <AlertTriangle className="w-6 h-6 text-red-400 dark:text-red-500 mx-auto mb-2" />
                <p className="text-neutral-600 dark:text-neutral-400 text-sm">Failed to load recommendations</p>
                <button onClick={() => recommendations.refetch()} className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline">Retry</button>
              </div>
            ) : !recommendations.data?.recommendations?.length ? (
              <div className="text-center py-8">
                <Shield className="w-8 h-8 text-neutral-300 dark:text-neutral-600 mx-auto mb-2" />
                <p className="text-neutral-500 dark:text-neutral-400 text-sm">No recommendations available</p>
              </div>
            ) : (
              <div className="space-y-3">
                {recommendations.data.recommendations.map((rec: Recommendation) => (
                  <div
                    key={rec.symbol}
                    className="p-4 rounded-lg border border-neutral-100 bg-neutral-50 dark:bg-neutral-800 dark:border-neutral-700 hover:border-neutral-200 dark:hover:border-neutral-600 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <Link to={`/stocks/${rec.symbol}`} className="font-bold text-neutral-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 text-sm">
                          ${rec.symbol}
                        </Link>
                        <ActionBadge action={rec.action} />
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-20 h-1.5 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                          <div
                            className={cn(
                              'h-full rounded-full',
                              rec.score >= 0.7 ? 'bg-green-500' : rec.score >= 0.4 ? 'bg-yellow-500' : 'bg-red-500',
                            )}
                            style={{ width: `${rec.score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">{formatNumber(rec.score, 2)}</span>
                      </div>
                    </div>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-2">{rec.rationale.notes}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {rec.rationale.top_signals.map((sig, i) => (
                        <span key={i} className="px-2 py-0.5 bg-white dark:bg-neutral-700 border border-neutral-200 dark:border-neutral-600 rounded text-[10px] text-neutral-600 dark:text-neutral-400">
                          {sig.signal.replace(/_/g, ' ')} ({formatPercent(sig.contribution, 0)})
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
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
                        <Link to={`/stocks/${a.ticker}`} className="font-bold text-xs text-neutral-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400">
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
                      <Link to={`/stocks/${a.ticker}`} className="font-bold text-xs text-neutral-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400">
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

          {/* -- AI SYSTEM HEALTH -- */}
          <div className="card">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-1.5">
              <Brain className="w-4 h-4 text-purple-500" />
              AI System Health
            </h2>

            {pressureTest.isLoading ? (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <div key={i} className="h-6 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : pressureTest.error ? (
              <p className="text-xs text-red-500 dark:text-red-400 py-2 text-center">Failed to load</p>
            ) : pressureTest.data ? (
              <div className="space-y-3">
                {/* Test Results */}
                <div>
                  <div className="text-[10px] font-medium text-neutral-400 dark:text-neutral-500 uppercase tracking-wider mb-1.5">System Tests</div>
                  <div className="space-y-1.5">
                    {Object.entries(pressureTest.data.test_results).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between">
                        <span className="text-xs text-neutral-600 dark:text-neutral-400 capitalize">{key.replace(/_/g, ' ')}</span>
                        <StatusDot status={value} />
                      </div>
                    ))}
                  </div>
                </div>

                {/* AI Capabilities */}
                <div className="border-t border-neutral-100 dark:border-neutral-700 pt-3">
                  <div className="text-[10px] font-medium text-neutral-400 dark:text-neutral-500 uppercase tracking-wider mb-1.5">AI Capabilities</div>
                  <div className="space-y-1.5">
                    {Object.entries(pressureTest.data.ai_capabilities).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between">
                        <span className="text-xs text-neutral-600 dark:text-neutral-400 capitalize">{key.replace(/_/g, ' ')}</span>
                        <StatusDot status={value} />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Overall */}
                <div className="border-t border-neutral-100 dark:border-neutral-700 pt-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    <span className="text-xs font-medium text-neutral-700 dark:text-neutral-300">{pressureTest.data.overall_status}</span>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          {/* -- COVERAGE STATS -- */}
          {sentiment.data?.statistics && (
            <div className="card">
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-indigo-500" />
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
        AI Intelligence powered by local LLM, feature calculations, and multi-source data
        {outlook.data?.generated_at && (
          <span> · Generated {formatRelativeTime(outlook.data.generated_at)}</span>
        )}
      </div>
    </div>
  );
};

export default MarketIntelligence;
