import React from 'react';
import { Link } from 'react-router-dom';
import {
  TrendingUp, TrendingDown, Target, Activity, Zap, RefreshCw,
  AlertTriangle, Calendar, ChevronRight, Shield, Newspaper, Brain, Clock,
} from 'lucide-react';
import { useDashboard } from '../hooks/useDashboard';
import FreshnessIndicator from './FreshnessIndicator';
import ConsolidatedRankings from './ConsolidatedRankings';
import {
  cn, formatNumber, formatPercent, formatRelativeTime, getSentimentColor,
} from '../utils/format';
import type { Alert, Anomaly, Recommendation, WSBTrendingTicker, Article } from '../types/api';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const SkeletonLines: React.FC<{ lines?: number }> = ({ lines = 3 }) => (
  <div className="animate-pulse space-y-2">
    {[...Array(lines)].map((_, i) => (
      <div key={i} className="h-3 bg-neutral-200 dark:bg-neutral-600 rounded" style={{ width: `${90 - i * 15}%` }} />
    ))}
  </div>
);

const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
  const styles: Record<string, string> = {
    critical: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-700',
    high: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 border-orange-200 dark:border-orange-700',
    medium: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 border-yellow-200 dark:border-yellow-700',
    low: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-700',
  };
  return (
    <span className={cn('px-1.5 py-0.5 text-[10px] font-semibold rounded border uppercase', styles[severity] || styles.low)}>
      {severity}
    </span>
  );
};

const ActionBadge: React.FC<{ action: string }> = ({ action }) => {
  const styles: Record<string, string> = {
    buy: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 border-green-200 dark:border-green-700',
    sell: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-700',
    hold: 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-400 border-neutral-200 dark:border-neutral-700',
  };
  return (
    <span className={cn('px-2 py-0.5 text-xs font-bold rounded border uppercase', styles[action] || styles.hold)}>
      {action}
    </span>
  );
};

const alertTypeIcon = (type: string) => {
  if (type.includes('sentiment')) return '\u{1F4AD}';
  if (type.includes('momentum') || type.includes('breakout')) return '\u{1F4C8}';
  if (type.includes('volume')) return '\u{1F4CA}';
  if (type.includes('wsb') || type.includes('viral')) return '\u{1F680}';
  if (type.includes('price')) return '\u{1F4B0}';
  return '\u26A1';
};

const anomalyTypeLabel = (t: string) => t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const Dashboard: React.FC = () => {
  const {
    featuresSummary, featureStats, outlook, recommendations, alerts,
    anomalies, wsbTrending, sentiment, articles, morningBrief,
    topGainers, topLosers, refreshAll,
  } = useDashboard();

  const overallSentiment = sentiment.data?.overall_sentiment;
  const alertCount = alerts.data?.count ?? 0;
  const coverageRate = featureStats.data
    ? Math.round((featureStats.data.coverage.coverage_rate || 0) * 100)
    : null;

  const outlookGradient = (label: string) => {
    if (label === 'OPTIMISTIC') return 'from-green-600 to-emerald-700';
    if (label === 'DEFENSIVE') return 'from-red-600 to-rose-700';
    return 'from-blue-600 to-indigo-700';
  };

  const isFetching = outlook.isFetching || featuresSummary.isFetching;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">

      {/* ====== MARKET PULSE HEADER ====== */}
      <div className="bg-neutral-900 rounded-xl p-4 text-white">
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-lg font-bold flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-400" />
            Market Pulse
          </h1>
          <div className="flex items-center gap-3">
            <FreshnessIndicator
              dataUpdatedAt={outlook.dataUpdatedAt}
              expectedIntervalMinutes={5}
              label="Data"
              className="text-neutral-400"
            />
            <button
              onClick={refreshAll}
              className="p-1.5 text-neutral-400 hover:text-white hover:bg-neutral-700 rounded-lg transition-colors"
              title="Refresh all panels"
            >
              <RefreshCw className={cn('w-4 h-4', isFetching && 'animate-spin')} />
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Sentiment */}
          <div className="bg-neutral-800 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-neutral-400 uppercase tracking-wider">Sentiment</span>
              <TrendingUp className="w-3.5 h-3.5 text-blue-400" />
            </div>
            {sentiment.isLoading ? (
              <div className="h-7 bg-neutral-700 rounded animate-pulse" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {overallSentiment ? formatNumber(overallSentiment.score, 2) : '\u2014'}
                </div>
                <div className="text-[10px] text-neutral-400">
                  {overallSentiment ? `${overallSentiment.label} (${overallSentiment.confidence})` : 'Loading...'}
                </div>
              </>
            )}
          </div>
          {/* Stocks */}
          <div className="bg-neutral-800 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-neutral-400 uppercase tracking-wider">Stocks</span>
              <Target className="w-3.5 h-3.5 text-purple-400" />
            </div>
            {featuresSummary.isLoading ? (
              <div className="h-7 bg-neutral-700 rounded animate-pulse" />
            ) : (
              <>
                <div className="text-2xl font-bold">{featuresSummary.data?.count ?? '\u2014'}</div>
                {/* Counts tickers with CURRENT feature rows, not all tracked
                    stocks \u2014 labeled honestly so it can't contradict Coverage. */}
                <div className="text-[10px] text-neutral-400">With fresh data</div>
              </>
            )}
          </div>
          {/* Alerts */}
          <div className="bg-neutral-800 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-neutral-400 uppercase tracking-wider">Alerts</span>
              <Zap className="w-3.5 h-3.5 text-orange-400" />
            </div>
            {alerts.isLoading ? (
              <div className="h-7 bg-neutral-700 rounded animate-pulse" />
            ) : (
              <>
                <div className="text-2xl font-bold">{alertCount}</div>
                <div className="text-[10px] text-neutral-400">
                  {alerts.data?.alerts?.filter((a: Alert) => a.severity === 'high' || a.severity === 'critical').length ?? 0} high priority
                </div>
              </>
            )}
          </div>
          {/* Coverage */}
          <div className="bg-neutral-800 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-neutral-400 uppercase tracking-wider">Coverage</span>
              <Activity className="w-3.5 h-3.5 text-green-400" />
            </div>
            {featureStats.isLoading ? (
              <div className="h-7 bg-neutral-700 rounded animate-pulse" />
            ) : (
              <>
                <div className="text-2xl font-bold">{coverageRate !== null ? `${coverageRate}%` : '\u2014'}</div>
                <div className="text-[10px] text-neutral-400">
                  {featureStats.data ? `${featureStats.data.coverage.unique_tickers_with_features}/${featureStats.data.coverage.total_active_tickers}` : '\u2014'}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ====== TOMORROW'S OUTLOOK HERO ====== */}
      {outlook.isLoading ? (
        <div className="card animate-pulse h-32" />
      ) : outlook.error ? (
        <div className="card border-red-200 dark:border-red-700 bg-red-50 dark:bg-red-900/30">
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-sm">
            <AlertTriangle className="w-4 h-4" />
            <span>Failed to load tomorrow's outlook</span>
            <button onClick={() => outlook.refetch()} className="ml-auto text-xs text-red-600 dark:text-red-400 hover:underline">Retry</button>
          </div>
        </div>
      ) : outlook.data ? (
        <div className={cn('rounded-xl p-5 text-white bg-gradient-to-r', outlookGradient(outlook.data.market_sentiment.label))}>
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-white/80 text-sm">
                <Calendar className="w-4 h-4" />
                <span>Outlook for {outlook.data.outlook_date}</span>
              </div>
              <div className="text-3xl font-bold">{outlook.data.market_sentiment.label}</div>
              <div className="text-white/70 text-sm">
                Score: {formatNumber(outlook.data.market_sentiment.score, 2)}
              </div>
            </div>
            <div className="lg:text-center">
              <div className="text-xs uppercase tracking-wider text-white/60 mb-1">Recommendation</div>
              <div className="text-base font-semibold">{outlook.data.recommendation.text}</div>
              <div className="text-xs text-white/60 mt-1">Confidence: {outlook.data.recommendation.confidence}</div>
            </div>
            <div className="space-y-1">
              <div className="text-xs uppercase tracking-wider text-white/60 mb-1">Key Factors</div>
              {outlook.data.recommendation.key_factors.slice(0, 3).map((f, i) => (
                <div key={i} className="flex items-center gap-1.5 text-sm text-white/90">
                  <ChevronRight className="w-3 h-3 text-white/50" />
                  {f}
                </div>
              ))}
            </div>
          </div>
          <div className="mt-3 text-right">
            <Link to="/intelligence" className="text-xs text-white/70 hover:text-white underline">
              Full Analysis &rarr;
            </Link>
          </div>
        </div>
      ) : null}

      {/* ====== MAIN GRID ====== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ---------- LEFT COLUMN (8/12) ---------- */}
        <div className="lg:col-span-8 space-y-6">

          {/* -- CONSOLIDATED RANKINGS (every brain, one list) -- */}
          <ConsolidatedRankings />

          {/* -- MORNING BRIEF -- */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
                <Brain className="w-5 h-5 text-purple-600" />
                Morning Brief
              </h2>
              {morningBrief.data?.generated_at && (
                <span className="flex items-center gap-1 text-xs text-neutral-500 dark:text-neutral-400">
                  <Clock className="w-3 h-3" />
                  {new Date(morningBrief.data.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>

            {morningBrief.isLoading ? (
              <SkeletonLines lines={4} />
            ) : morningBrief.error ? (
              <p className="text-xs text-neutral-500 dark:text-neutral-400">Intelligence gathering in progress: check back tomorrow</p>
            ) : !morningBrief.data?.stocks?.length ? (
              <div className="text-center py-6">
                <Brain className="w-8 h-8 text-purple-300 dark:text-purple-600 mx-auto mb-2" />
                <p className="text-sm text-neutral-500 dark:text-neutral-400">Intelligence gathering in progress: check back tomorrow</p>
              </div>
            ) : (
              <div className="space-y-3">
                {/* LLM market summary */}
                {morningBrief.data.market_summary && (
                  <div className="p-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 rounded-lg text-sm text-neutral-800 dark:text-neutral-200 italic">
                    &ldquo;{morningBrief.data.market_summary}&rdquo;
                  </div>
                )}
                {/* Per-stock bullets */}
                <div className="space-y-2">
                  {morningBrief.data.stocks.slice(0, 6).map((s) => {
                    const arrow = s.sentiment_trend_direction === 'improving' ? '↑' : s.sentiment_trend_direction === 'declining' ? '↓' : '→';
                    const arrowColor = s.sentiment_trend_direction === 'improving'
                      ? 'text-green-600 dark:text-green-400'
                      : s.sentiment_trend_direction === 'declining'
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-neutral-500 dark:text-neutral-400';
                    return (
                      <div key={s.ticker} className="flex items-start gap-2 text-sm">
                        <Link to={`/stocks/${s.ticker}`}
                          className="font-semibold text-blue-600 dark:text-blue-400 hover:underline shrink-0 w-12">
                          {s.ticker}
                        </Link>
                        <span className={cn('font-bold shrink-0', arrowColor)}>{arrow}</span>
                        <span className="text-neutral-600 dark:text-neutral-400 leading-snug line-clamp-2">
                          {s.top_event || s.narrative?.slice(0, 100) || 'No recent events'}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="text-right">
                  <Link to="/intelligence" className="text-xs text-blue-600 hover:underline">Full Brief &rarr;</Link>
                </div>
              </div>
            )}
          </div>

          {/* -- RECOMMENDATIONS -- */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
                <Shield className="w-5 h-5 text-green-600" />
                Today's Recommendations
              </h2>
              <Link to="/intelligence" className="text-xs text-blue-600 hover:underline">View All</Link>
            </div>

            {recommendations.isLoading ? (
              <SkeletonLines lines={4} />
            ) : recommendations.error ? (
              <div className="text-center py-6">
                <AlertTriangle className="w-6 h-6 text-red-400 mx-auto mb-2" />
                <p className="text-neutral-600 dark:text-neutral-400 text-sm">Failed to load recommendations</p>
                <button onClick={() => recommendations.refetch()} className="mt-2 text-sm text-blue-600 hover:underline">Retry</button>
              </div>
            ) : !recommendations.data?.recommendations?.length ? (
              <div className="text-center py-6">
                <Shield className="w-8 h-8 text-neutral-300 dark:text-neutral-600 mx-auto mb-2" />
                <p className="text-neutral-500 dark:text-neutral-400 text-sm">No recommendations available yet</p>
                <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">Recommendations are generated daily from feature calculations</p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {recommendations.data.recommendations.slice(0, 5).map((rec: Recommendation) => (
                  <div
                    key={rec.symbol}
                    className="p-3 rounded-lg border border-neutral-100 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800/50 hover:border-neutral-200 dark:hover:border-neutral-600 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-3">
                        <Link to={`/stocks/${rec.symbol}`} className="font-bold text-neutral-900 dark:text-white hover:text-blue-600 text-sm">
                          ${rec.symbol}
                        </Link>
                        <ActionBadge action={rec.action} />
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 bg-neutral-200 dark:bg-neutral-600 rounded-full overflow-hidden">
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
                    <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-1.5">{rec.rationale.notes}</p>
                    <div className="flex flex-wrap gap-1">
                      {rec.rationale.top_signals.slice(0, 3).map((sig, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-white dark:bg-neutral-700 border border-neutral-200 dark:border-neutral-600 rounded text-[10px] text-neutral-600 dark:text-neutral-300">
                          {sig.signal.replace(/_/g, ' ')} ({formatPercent(sig.contribution, 0)})
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* -- TOP MOVERS (GAINERS + LOSERS) -- */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="card">
              <h2 className="text-base font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-green-600" />
                Top Gainers (5d)
              </h2>
              {featuresSummary.isLoading ? (
                <SkeletonLines lines={5} />
              ) : topGainers.length === 0 ? (
                <p className="text-xs text-neutral-400 dark:text-neutral-500 py-4 text-center">No gainers data</p>
              ) : (
                <ul className="divide-y divide-neutral-100 dark:divide-neutral-700">
                  {topGainers.map((s) => (
                    <li key={s.ticker} className="py-2 flex items-center justify-between">
                      <Link to={`/stocks/${s.ticker}`} className="font-medium text-sm text-neutral-900 dark:text-white hover:text-blue-600">
                        {s.ticker}
                      </Link>
                      <span className="text-green-600 font-semibold text-sm">
                        {s.ret_5d ? `+${(s.ret_5d * 100).toFixed(1)}%` : '\u2014'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="card">
              <h2 className="text-base font-semibold text-neutral-900 dark:text-white mb-3 flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-red-600" />
                Top Losers (5d)
              </h2>
              {featuresSummary.isLoading ? (
                <SkeletonLines lines={5} />
              ) : topLosers.length === 0 ? (
                <p className="text-xs text-neutral-400 dark:text-neutral-500 py-4 text-center">No losers data</p>
              ) : (
                <ul className="divide-y divide-neutral-100 dark:divide-neutral-700">
                  {topLosers.map((s) => (
                    <li key={s.ticker} className="py-2 flex items-center justify-between">
                      <Link to={`/stocks/${s.ticker}`} className="font-medium text-sm text-neutral-900 dark:text-white hover:text-blue-600">
                        {s.ticker}
                      </Link>
                      <span className="text-red-600 font-semibold text-sm">
                        {s.ret_5d ? `${(s.ret_5d * 100).toFixed(1)}%` : '\u2014'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* -- WSB TRENDING COMPACT -- */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
                <span className="text-base">&#129421;</span>
                Trending on WSB
              </h2>
              <Link to="/wsb-trending" className="text-xs text-blue-600 hover:underline">View All</Link>
            </div>

            {wsbTrending.isLoading ? (
              <SkeletonLines lines={5} />
            ) : wsbTrending.error ? (
              <p className="text-xs text-red-500 dark:text-red-400 py-4 text-center">Failed to load WSB data</p>
            ) : !wsbTrending.data?.trending_tickers?.length ? (
              <p className="text-xs text-neutral-400 dark:text-neutral-500 py-6 text-center">No WSB trending data available</p>
            ) : (
              <div className="overflow-x-auto -mx-6">
                <table className="w-full text-sm" style={{ minWidth: '400px' }}>
                  <thead>
                    <tr className="border-b border-neutral-200 dark:border-neutral-700 text-left text-xs text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                      <th className="px-6 py-2 w-8 hidden sm:table-cell">#</th>
                      <th className="px-3 py-2">Ticker</th>
                      <th className="px-3 py-2 text-right">Score</th>
                      <th className="px-3 py-2 text-right">Mentions</th>
                      <th className="px-3 py-2 text-right">Sentiment</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700">
                    {wsbTrending.data.trending_tickers.slice(0, 5).map((t: WSBTrendingTicker, i: number) => (
                      <tr key={t.ticker} className="hover:bg-blue-50 dark:hover:bg-neutral-800 transition-colors">
                        <td className="px-6 py-2 text-neutral-400 dark:text-neutral-500 text-xs hidden sm:table-cell">{i + 1}</td>
                        <td className="px-3 py-2">
                          <Link to={`/stocks/${t.ticker}`} className="font-bold text-neutral-900 dark:text-white hover:text-blue-600">
                            ${t.ticker}
                          </Link>
                        </td>
                        <td className="px-3 py-2 text-right font-medium text-neutral-700 dark:text-neutral-300">{formatNumber(t.trending_score, 2)}</td>
                        <td className="px-3 py-2 text-right text-neutral-600 dark:text-neutral-400">{t.mention_count}</td>
                        <td className="px-3 py-2 text-right">
                          <span className={cn('font-medium text-xs', getSentimentColor(t.avg_sentiment))}>
                            {formatNumber(t.avg_sentiment, 2)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* ---------- RIGHT COLUMN (4/12) ---------- */}
        <div className="lg:col-span-4 space-y-6">

          {/* -- LIVE ALERTS -- */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-white flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-orange-500" />
                Live Alerts
              </h2>
              <span className="text-[10px] text-neutral-400 dark:text-neutral-500">{alertCount} recent</span>
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
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                {alerts.data!.alerts.map((a: Alert) => (
                  <div key={a.id} className="p-2.5 bg-neutral-50 dark:bg-neutral-800/50 rounded-lg border border-neutral-100 dark:border-neutral-700 hover:border-neutral-200 dark:hover:border-neutral-600 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">{alertTypeIcon(a.alert_type)}</span>
                        <Link to={`/stocks/${a.ticker}`} className="font-bold text-xs text-neutral-900 dark:text-white hover:text-blue-600">
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
                Market Anomalies
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
                {anomalies.data!.market_anomalies.slice(0, 8).map((a: Anomaly, i: number) => (
                  <div key={`${a.ticker}-${a.anomaly_type}-${i}`} className="p-2.5 rounded-lg border border-neutral-100 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800/50">
                    <div className="flex items-center justify-between mb-1">
                      <Link to={`/stocks/${a.ticker}`} className="font-bold text-xs text-neutral-900 dark:text-white hover:text-blue-600">
                        ${a.ticker}
                      </Link>
                      <span className={cn(
                        'text-[10px] font-semibold px-1.5 py-0.5 rounded',
                        a.severity >= 0.7 ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300' :
                        a.severity >= 0.4 ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' :
                        'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
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

          {/* -- RECENT ARTICLES -- */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-white flex items-center gap-1.5">
                <Newspaper className="w-4 h-4 text-blue-500" />
                Recent Articles
              </h2>
              <span className="text-[10px] text-neutral-400 dark:text-neutral-500">{articles.data?.total ?? 0} total</span>
            </div>

            {articles.isLoading ? (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <div key={i} className="h-10 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />)}
              </div>
            ) : articles.error ? (
              <p className="text-xs text-red-500 dark:text-red-400 py-4 text-center">Failed to load articles</p>
            ) : (articles.data?.items?.length ?? 0) === 0 ? (
              <p className="text-xs text-neutral-400 dark:text-neutral-500 py-6 text-center">No recent articles</p>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                {articles.data!.items.slice(0, 8).map((art: Article) => (
                  <div key={art.id} className="p-2.5 rounded-lg border border-neutral-100 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800/50 hover:border-neutral-200 dark:hover:border-neutral-600 transition-colors">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <p className="text-xs font-medium text-neutral-800 dark:text-neutral-200 line-clamp-2 flex-1">
                        {art.title || 'Untitled article'}
                      </p>
                      {art.sentiment !== null && (
                        <span className={cn(
                          'text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0',
                          art.sentiment >= 0.6 ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' :
                          art.sentiment >= 0.4 ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' :
                          'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
                        )}>
                          {formatNumber(art.sentiment, 2)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-neutral-400 dark:text-neutral-500">
                      {art.tickers && art.tickers.length > 0 && (
                        <div className="flex gap-1">
                          {art.tickers.slice(0, 3).map(t => (
                            <Link key={t} to={`/stocks/${t}`} className="text-blue-500 dark:text-blue-400 hover:underline font-medium">
                              ${t}
                            </Link>
                          ))}
                        </div>
                      )}
                      {art.published_at && (
                        <span>{formatRelativeTime(art.published_at)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ====== FOOTER ====== */}
      <div className="text-center text-xs text-neutral-400 pt-2 border-t border-neutral-200 dark:border-neutral-700">
        Stonks Command Center &middot; Powered by multi-source analytics
        {outlook.data?.generated_at && (
          <span> &middot; Generated {formatRelativeTime(outlook.data.generated_at)}</span>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
