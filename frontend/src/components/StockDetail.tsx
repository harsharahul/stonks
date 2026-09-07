import React, { useState, useCallback, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient, { feedApi } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useParams, Link } from 'react-router-dom';
import { BarChart3, Zap, RefreshCw, Star, Brain, Clock, ExternalLink, TrendingUp } from 'lucide-react';
import TradeTicket from './broker/TradeTicket';
import { LineChart, Line, Tooltip, ResponsiveContainer, XAxis, YAxis } from 'recharts';
import { useDailyFeatures, useFeatureHistory, useCalculateFeatures, useEnhancedAnalytics } from '../hooks/useFeatures';
import { useWSBTrending } from '../hooks/useWSBDashboard';
import { useStockKnowledge } from '../hooks/useMarketIntelligence';
import { useToast } from '../hooks/useToast';
import ToastManager from './ToastManager';
import FeatureCard from './FeatureCard';
import FeatureChart from './FeatureChart';
import PriceChart from './PriceChart';
import PatternSummaryPanel from './PatternSummaryPanel';
import LatestCandleInsight from './LatestCandleInsight';
import { cn, formatDate, formatRelativeTime, prepareChartData } from '../utils/format';
import type { DetectedPattern, LatestCandleData } from '../utils/candlestickPatterns';

const StockDetail: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>();
  const ticker = symbol?.toUpperCase() || '';
  const queryClient = useQueryClient();
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';

  // Fetch current features and history
  const { data: features, isLoading: featuresLoading, error: featuresError } = useDailyFeatures(ticker);
  const { data: history, isLoading: historyLoading } = useFeatureHistory(ticker, 30);
  const calculateFeatures = useCalculateFeatures();
  const [generateInsights, setGenerateInsights] = useState(false);
  const { data: enhanced, isLoading: enhancedLoading } = useEnhancedAnalytics(ticker, generateInsights);
  const { data: knowledge } = useStockKnowledge(ticker);

  // Fetch WSB trending data as fallback (filter from shared hook)
  const { data: wsbTrendingAll, isLoading: wsbLoading } = useWSBTrending(7, 50);
  const wsbTrending = useMemo(
    () => wsbTrendingAll?.trending_tickers?.find((t: any) => t.ticker === ticker) ?? null,
    [wsbTrendingAll, ticker],
  );
  const { toasts, showSuccess, showError: showErrorToast, removeToast } = useToast();

  // The star is the USER's watchlist (per-account), not the legacy global
  // tracked-stocks list: the two were conflated before, so the star showed the wrong state.
  const { isAuthenticated } = useAuth();
  const watchlist = useQuery({
    queryKey: ['my-watchlist'],
    queryFn: async () => {
      const res = await apiClient.get('/users/me/watchlist');
      return (res.data.watchlist?.map((w: any) => w.symbol || w.stock?.symbol) as string[]) || [];
    },
    enabled: isAuthenticated,
    staleTime: 60_000,
  });
  const isTracked = watchlist.data?.includes(ticker) ?? false;
  const [starLoading, setStarLoading] = useState(false);
  const [tradeOpen, setTradeOpen] = useState(false);

  const toggleTracked = async () => {
    if (!isAuthenticated) {
      showErrorToast('Sign in required', 'Sign in to keep a personal watchlist.');
      return;
    }
    setStarLoading(true);
    try {
      if (isTracked) {
        await apiClient.delete(`/users/me/watchlist/${ticker}`);
      } else {
        await apiClient.post('/users/me/watchlist', { symbol: ticker });
      }
      queryClient.invalidateQueries({ queryKey: ['my-watchlist'] });
      showSuccess(isTracked ? 'Removed' : 'Added', `${ticker} ${isTracked ? 'removed from' : 'added to'} your watchlist.`);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || `Failed to update ${ticker}.`;
      showErrorToast('Watchlist Error', detail);
    } finally {
      setStarLoading(false);
    }
  };

  // Candlestick pattern detection results from PriceChart
  const [detectedPatterns, setDetectedPatterns] = useState<DetectedPattern[]>([]);
  const handlePatternsDetected = useCallback((patterns: DetectedPattern[]) => {
    setDetectedPatterns(patterns);
  }, []);

  // Latest candle enriched data from PriceChart
  const [latestCandleData, setLatestCandleData] = useState<LatestCandleData | null>(null);
  const handleLatestCandleData = useCallback((data: LatestCandleData | null) => {
    setLatestCandleData(data);
  }, []);

  // Prepare chart data
  const sentimentData = history?.features ? prepareChartData(
    history.features,
    'date',
    'sentiment.mean_7d'
  ) : [];

  const returnsData = history?.features ? prepareChartData(
    history.features,
    'date', 
    'returns.ret_5d'
  ) : [];

  const handleRefreshFeatures = () => {
    calculateFeatures.mutate({ ticker });
  };

  // Helper function to get the best available WSB data
  const getWSBData = (field: string) => {
    // First try to get from stored features
    const storedValue = features?.retail_sentiment?.[field];
    
    // If stored value exists and is not null/0, use it
    if (storedValue !== null && storedValue !== undefined && storedValue !== 0) {
      return storedValue;
    }
    
    // Fallback to trending data
    if (wsbTrending) {
      switch (field) {
        case 'wsb_mention_count_7d':
          return wsbTrending.mention_count || 0;
        case 'wsb_sentiment_7d':
          return wsbTrending.avg_sentiment || null;
        case 'wsb_engagement_score':
          return wsbTrending.avg_reddit_score || null;
        case 'meme_stock_indicator':
          return wsbTrending.trending_score || null;
        default:
          return storedValue;
      }
    }
    
    return storedValue;
  };

  if (featuresError) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full mb-4">
            <BarChart3 className="w-8 h-8 text-blue-600" />
          </div>
          <h2 className="text-2xl font-semibold text-neutral-900 dark:text-white mb-2">No Data Available Yet</h2>
          <p className="text-neutral-600 dark:text-neutral-400 mb-6 max-w-md mx-auto">
            Features haven't been calculated for <span className="font-semibold text-neutral-900 dark:text-white">{ticker}</span> yet.
            This data is calculated daily, or you can generate it now.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center items-center mb-8">
            <button
              onClick={handleRefreshFeatures}
              disabled={calculateFeatures.isLoading}
              className="btn-primary inline-flex items-center px-6 py-3"
            >
              {calculateFeatures.isLoading ? (
                <>
                  <RefreshCw className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" />
                  Calculating...
                </>
              ) : (
                <>
                  <Zap className="w-5 h-5 mr-2" />
                  Calculate Now
                </>
              )}
            </button>
            <a
              href="/stocks"
              className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white underline"
            >
              ← Back to Stocks
            </a>
          </div>
          {calculateFeatures.isError && (
            <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-lg p-4 max-w-md mx-auto">
              <p className="text-sm text-red-800 dark:text-red-200">
                <span className="font-semibold">Unable to calculate features.</span> This might require admin access or the calculation service may be unavailable.
              </p>
            </div>
          )}
          <div className="mt-8 pt-8 border-t border-neutral-200 dark:border-neutral-700">
            <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-2">Automatic calculation schedule:</p>
            <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Daily at 05:00 UTC</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-white">{ticker}</h1>
          <button
            onClick={toggleTracked}
            disabled={starLoading || watchlist.isLoading}
            className="p-1 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors disabled:opacity-50"
            title={isTracked ? 'Remove from watchlist' : 'Add to watchlist'}
          >
            <Star
              className={cn(
                'w-6 h-6 transition-colors',
                isTracked ? 'text-yellow-500 fill-yellow-400' : 'text-neutral-300 hover:text-yellow-400'
              )}
            />
          </button>
          <p className="text-neutral-600 dark:text-neutral-400 hidden sm:block">Stock Analytics Dashboard</p>
        </div>
        <div className="flex items-center space-x-4">
          {features && (
            <div className="text-right">
              <p className="text-sm text-neutral-500 dark:text-neutral-400">Last Updated</p>
              <p className="text-sm font-medium dark:text-neutral-300">
                {formatRelativeTime(features.created_at)}
              </p>
            </div>
          )}
          <button
            onClick={() => setTradeOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg font-bold text-sm uppercase tracking-wider bg-emerald-600 hover:bg-emerald-700 text-white transition-colors"
          >
            <TrendingUp className="w-4 h-4" /> Trade
          </button>
          <button
            onClick={handleRefreshFeatures}
            disabled={calculateFeatures.isLoading}
            className="btn-primary"
          >
            {calculateFeatures.isLoading ? 'Calculating...' : 'Refresh Features'}
          </button>
        </div>
      </div>

      {symbol && (
        <TradeTicket
          symbol={symbol.toUpperCase()}
          open={tradeOpen}
          onClose={() => setTradeOpen(false)}
        />
      )}

      {/* Data Coverage Strip */}
      {features && (
        <div className="card mb-8">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
            <div className="flex items-center justify-between sm:justify-start sm:space-x-2">
              <span className="text-neutral-600 dark:text-neutral-400">Articles (7d)</span>
              <span className="font-semibold text-neutral-900 dark:text-white">{features.context?.article_count_7d || 0}</span>
            </div>
            <div className="flex items-center justify-between sm:justify-start sm:space-x-2">
              <span className="text-neutral-600 dark:text-neutral-400">Feature Version</span>
              <span className="font-semibold text-neutral-900 dark:text-white">{features.feature_version}</span>
            </div>
            <div className="flex items-center justify-between sm:justify-start sm:space-x-2">
              <span className="text-neutral-600 dark:text-neutral-400">WSB Sentiment</span>
              <span className="font-semibold text-neutral-900 dark:text-white">
                {getWSBData('wsb_sentiment_7d') ? getWSBData('wsb_sentiment_7d').toFixed(3) : 'N/A'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Price Chart */}
      <div className="mb-8">
        <PriceChart
          ticker={ticker}
          onPatternsDetected={handlePatternsDetected}
          onLatestCandleData={handleLatestCandleData}
        />
      </div>

      {/* Latest Candle Insight */}
      {latestCandleData && (
        <LatestCandleInsight data={latestCandleData} ticker={ticker} className="mb-8" />
      )}

      {/* Pattern Summary Panel */}
      {detectedPatterns.length > 0 && (
        <PatternSummaryPanel patterns={detectedPatterns} className="mb-8" />
      )}

      {/* WSB Sentiment Section */}
      <div className="card mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-neutral-900 dark:text-white">WSB Sentiment Analysis</h2>
          <div className="flex items-center space-x-2">
            <span className="px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-xs font-medium rounded-full">
              LIVE DATA
            </span>
            {wsbLoading && (
              <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium rounded-full">
                🔄 Loading Trending Data
              </span>
            )}
            {wsbTrending && !features?.retail_sentiment?.wsb_mention_count_7d && (
              <span className="px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-xs font-medium rounded-full">
                📊 From Trending Data
              </span>
            )}
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 bg-gradient-to-r from-red-50 to-red-100 dark:from-red-900/30 dark:to-red-800/30 rounded-lg border border-red-200 dark:border-red-700">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-red-600 dark:text-red-400">📊</span>
              <span className="text-sm font-medium text-red-700 dark:text-red-300">WSB Mentions</span>
            </div>
            <div className="text-2xl font-bold text-red-900 dark:text-red-200">
              {getWSBData('wsb_mention_count_7d')}
            </div>
            <div className="text-xs text-red-600 dark:text-red-400 mt-1">Last 7 days</div>
          </div>

          <div className="p-4 bg-gradient-to-r from-blue-50 to-blue-100 dark:from-blue-900/30 dark:to-blue-800/30 rounded-lg border border-blue-200 dark:border-blue-700">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-blue-600 dark:text-blue-400">💬</span>
              <span className="text-sm font-medium text-blue-700 dark:text-blue-300">Sentiment (7d)</span>
            </div>
            <div className="text-2xl font-bold text-blue-900 dark:text-blue-200">
              {getWSBData('wsb_sentiment_7d') ? getWSBData('wsb_sentiment_7d').toFixed(3) : 'N/A'}
            </div>
            <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">
              {getWSBData('wsb_sentiment_7d') && getWSBData('wsb_sentiment_7d') > 0.5 ? 'Bullish' :
               getWSBData('wsb_sentiment_7d') && getWSBData('wsb_sentiment_7d') < 0.5 ? 'Bearish' : 'Neutral'}
            </div>
          </div>

          <div className="p-4 bg-gradient-to-r from-green-50 to-green-100 dark:from-green-900/30 dark:to-green-800/30 rounded-lg border border-green-200 dark:border-green-700">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-green-600 dark:text-green-400">🚀</span>
              <span className="text-sm font-medium text-green-700 dark:text-green-300">Engagement</span>
            </div>
            <div className="text-2xl font-bold text-green-900 dark:text-green-200">
              {getWSBData('wsb_engagement_score') ? getWSBData('wsb_engagement_score').toFixed(3) : 'N/A'}
            </div>
            <div className="text-xs text-green-600 dark:text-green-400 mt-1">Reddit activity</div>
          </div>

          <div className="p-4 bg-gradient-to-r from-purple-50 to-purple-100 dark:from-purple-900/30 dark:to-purple-800/30 rounded-lg border border-purple-200 dark:border-purple-700">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-purple-600 dark:text-purple-400">🎭</span>
              <span className="text-sm font-medium text-purple-700 dark:text-purple-300">Meme Potential</span>
            </div>
            <div className="text-2xl font-bold text-purple-900 dark:text-purple-200">
              {getWSBData('meme_stock_indicator') ? getWSBData('meme_stock_indicator').toFixed(3) : 'N/A'}
            </div>
            <div className="text-xs text-purple-600 dark:text-purple-400 mt-1">WSB meme score</div>
          </div>
        </div>

        {/* Sentiment Visualization */}
        {getWSBData('wsb_sentiment_7d') && (
          <div className="mt-6">
            <div className="flex items-center justify-between text-sm text-neutral-600 dark:text-neutral-400 mb-2">
              <span>Sentiment Distribution</span>
              <span className="font-medium">
                {getWSBData('wsb_sentiment_7d') > 0.6 ? 'Very Bullish' :
                 getWSBData('wsb_sentiment_7d') > 0.4 ? 'Moderately Bullish' :
                 getWSBData('wsb_sentiment_7d') > 0.2 ? 'Slightly Bearish' : 'Very Bearish'}
              </span>
            </div>
            <div className="w-full bg-neutral-200 dark:bg-neutral-700 rounded-full h-3">
              <div
                className="bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 h-3 rounded-full transition-all duration-500"
                style={{ width: `${getWSBData('wsb_sentiment_7d') * 100}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-xs text-neutral-500 dark:text-neutral-400 mt-1">
              <span>Bearish</span>
              <span>Neutral</span>
              <span>Bullish</span>
            </div>
          </div>
        )}
      </div>

      {/* Stock Intelligence Section: only render if knowledge data exists */}
      {knowledge && (
        <div className="card mb-8">
          <div className="flex items-center gap-2 mb-5">
            <Brain className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            <h2 className="text-xl font-semibold text-neutral-900 dark:text-white">Stock Intelligence</h2>
            {knowledge.last_updated && (
              <span className="ml-auto flex items-center gap-1 text-xs text-neutral-500 dark:text-neutral-400">
                <Clock className="w-3 h-3" />
                Updated {new Date(knowledge.last_updated).toLocaleDateString()}
              </span>
            )}
          </div>

          {/* Analyst Note */}
          <div className="mb-6 p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 rounded-xl">
            <div className="text-xs font-semibold text-purple-600 dark:text-purple-400 uppercase tracking-wider mb-2">
              Analyst Note &middot; {knowledge.article_count_processed} articles analyzed
            </div>
            {knowledge.narrative ? (
              <p className="text-sm text-neutral-800 dark:text-neutral-200 leading-relaxed italic">
                &ldquo;{knowledge.narrative}&rdquo;
              </p>
            ) : (
              <p className="text-sm text-neutral-500 dark:text-neutral-400 italic">
                Structured intelligence only: LLM narrative not configured
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Key Events Timeline */}
            {knowledge.key_events?.events && knowledge.key_events.events.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">Key Events</h3>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {knowledge.key_events.events.slice(-10).reverse().map((event, idx) => {
                    const s = event.sentiment ?? 0.5;
                    const sentColor = s > 0.6
                      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 border-green-200 dark:border-green-700'
                      : s < 0.4
                        ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border-red-200 dark:border-red-700'
                        : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 border-yellow-200 dark:border-yellow-700';
                    const sentLabel = s > 0.6 ? 'Pos' : s < 0.4 ? 'Neg' : 'Neu';
                    return (
                      <div key={idx} className="flex items-start gap-2 text-sm">
                        <span className="text-neutral-400 dark:text-neutral-500 text-xs mt-0.5 shrink-0 w-20">
                          {event.date || '--'}
                        </span>
                        <span className={cn('px-1.5 py-0.5 text-[10px] font-semibold rounded border shrink-0', sentColor)}>
                          {sentLabel}
                        </span>
                        {event.url ? (
                          <a href={event.url} target="_blank" rel="noopener noreferrer"
                            className="text-neutral-700 dark:text-neutral-300 hover:text-blue-600 dark:hover:text-blue-400 flex items-center gap-1 leading-snug">
                            {event.title}
                            <ExternalLink className="w-3 h-3 shrink-0 opacity-60" />
                          </a>
                        ) : (
                          <span className="text-neutral-700 dark:text-neutral-300 leading-snug">{event.title}</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Sentiment Trajectory Sparkline */}
            {knowledge.sentiment_trend?.weekly && knowledge.sentiment_trend.weekly.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">Sentiment Trajectory</h3>
                <ResponsiveContainer width="100%" height={120}>
                  <LineChart data={knowledge.sentiment_trend.weekly.slice(-12)}>
                    <XAxis dataKey="week" hide />
                    <YAxis domain={[0, 1]} hide />
                    <Tooltip
                      formatter={(val: number) => [val.toFixed(2), 'Sentiment']}
                      labelFormatter={(label) => `Week: ${label}`}
                      contentStyle={{
                        fontSize: '11px',
                        backgroundColor: 'var(--tooltip-bg, #1f2937)',
                        border: 'none',
                        borderRadius: '6px',
                        color: '#e5e7eb',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="avg_sentiment"
                      stroke="#7c3aed"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
                <div className="flex justify-between text-xs text-neutral-400 dark:text-neutral-500 mt-1">
                  <span>12 weeks ago</span>
                  <span>Now</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Feature Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <FeatureCard
          title="7-Day Sentiment"
          value={features?.sentiment?.mean_7d}
          format="sentiment"
          subtitle={`${features?.context?.article_count_7d || 0} articles analyzed`}
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="5-Day Return"
          value={features?.returns?.ret_5d}
          format="return"
          subtitle="Price performance"
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="1-Day Return"
          value={features?.returns?.ret_1d}
          format="return"
          subtitle="Latest session"
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="20-Day Return"
          value={features?.returns?.ret_20d}
          format="return"
          subtitle="Monthly trend"
          isLoading={featuresLoading}
        />
      </div>

      {/* Advanced Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <FeatureCard
          title="Sentiment Shock"
          value={features?.sentiment?.shock}
          format="number"
          subtitle="vs 90-day baseline"
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="Volume Z-Score"
          value={features?.context?.vol_z}
          format="number"
          subtitle="Volume deviation"
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="14-Day Momentum"
          value={features?.returns?.momentum_14d}
          format="return"
          subtitle="Avg daily return"
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="Novelty Score"
          value={features?.context?.novelty_mean_3d}
          format="number"
          subtitle="Content uniqueness"
          isLoading={featuresLoading}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
        <FeatureChart
          title="Sentiment Trend (7-Day Average)"
          data={sentimentData}
          format="number"
          color="#059669"
          isLoading={historyLoading}
        />
        <FeatureChart
          title="Returns Trend (5-Day)"
          data={returnsData}
          format="percent"
          color="#3b82f6"
          isLoading={historyLoading}
        />
      </div>

      {/* AI Insights: pre-computed by the AI Trading Desk; on-demand legacy generation */}
      <div className="card mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-neutral-900 dark:text-white">AI Insights</h2>
          <Link
            to={`/desk/${ticker}`}
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-600 hover:text-emerald-700"
          >
            <Brain className="w-4 h-4" /> Open AI Trading Desk →
          </Link>
        </div>
        {enhancedLoading ? (
          <div className="space-y-2 animate-pulse">
            <div className="h-4 bg-neutral-200 dark:bg-neutral-700 rounded w-1/3" />
            <div className="h-4 bg-neutral-200 dark:bg-neutral-700 rounded w-2/3" />
            <div className="h-24 bg-neutral-200 dark:bg-neutral-700 rounded" />
          </div>
        ) : enhanced ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-3 bg-neutral-50 dark:bg-neutral-800 rounded border border-neutral-200 dark:border-neutral-700">
                <div className="text-xs text-neutral-500 dark:text-neutral-400">Risk Level</div>
                <div className="text-lg font-semibold capitalize dark:text-neutral-100">{enhanced?.llm_enhancement?.summary?.risk_level || 'N/A'}</div>
              </div>
              <div className="p-3 bg-neutral-50 dark:bg-neutral-800 rounded border border-neutral-200 dark:border-neutral-700">
                <div className="text-xs text-neutral-500 dark:text-neutral-400">Confidence</div>
                <div className="text-lg font-semibold capitalize dark:text-neutral-100">{enhanced?.llm_enhancement?.summary?.recommendation_confidence || 'N/A'}</div>
              </div>
              <div className="p-3 bg-neutral-50 dark:bg-neutral-800 rounded border border-neutral-200 dark:border-neutral-700">
                <div className="text-xs text-neutral-500 dark:text-neutral-400">Article Coverage</div>
                <div className="text-lg font-semibold dark:text-neutral-100">{enhanced?.llm_enhancement?.analysis?.article_coverage || 'N/A'}</div>
              </div>
            </div>
            {enhanced?.llm_enhancement?.llm_enhancements?.article_synthesis && (
              <div>
                <h3 className="text-lg font-medium text-neutral-900 dark:text-white mb-2">Article Synthesis</h3>
                <p className="text-sm text-neutral-700 dark:text-neutral-300 whitespace-pre-line">{enhanced.llm_enhancement.llm_enhancements.article_synthesis}</p>
              </div>
            )}
            {enhanced?.llm_enhancement?.llm_enhancements?.recommendations && (
              <div>
                <h3 className="text-lg font-medium text-neutral-900 dark:text-white mb-2">Recommendations</h3>
                <p className="text-sm text-neutral-700 dark:text-neutral-300 whitespace-pre-line">{enhanced.llm_enhancement.llm_enhancements.recommendations}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <p className="text-sm text-neutral-500 dark:text-neutral-400">
              The AI Trading Desk pre-computes a full multi-agent analysis nightly, check the
              desk for {ticker}'s latest verdict, or generate a quick insight now (slow: ~60s).
            </p>
            <button
              onClick={() => setGenerateInsights(true)}
              disabled={generateInsights}
              className="text-sm px-3 py-1.5 rounded-lg border border-neutral-300 dark:border-neutral-600 hover:bg-neutral-50 dark:hover:bg-neutral-800 disabled:opacity-50"
            >
              {generateInsights ? 'Generating…' : 'Generate now'}
            </button>
          </div>
        )}
      </div>

      {/* Top Articles (7d) */}
      <ArticlesSection ticker={ticker} />

      {/* Feature Details */}
      {features && (
        <div className="card">
          <h2 className="text-xl font-semibold text-neutral-900 dark:text-white mb-4">Feature Details</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <h3 className="text-lg font-medium text-neutral-800 dark:text-neutral-200 mb-3">Sentiment Analysis</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-neutral-600 dark:text-neutral-400">3-Day Average:</span>
                  <span className="font-medium dark:text-neutral-200">{features.sentiment?.mean_3d?.toFixed(3) || '--'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600 dark:text-neutral-400">7-Day Average:</span>
                  <span className="font-medium dark:text-neutral-200">{features.sentiment?.mean_7d?.toFixed(3) || '--'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600 dark:text-neutral-400">10-Day Average:</span>
                  <span className="font-medium dark:text-neutral-200">{features.sentiment?.mean_10d?.toFixed(3) || '--'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600 dark:text-neutral-400">Volume Weighted:</span>
                  <span className="font-medium dark:text-neutral-200">{features.sentiment?.volume_weighted?.toFixed(3) || '--'}</span>
                </div>
              </div>
            </div>
            <div>
              <h3 className="text-lg font-medium text-neutral-800 dark:text-neutral-200 mb-3">Market Metrics</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-neutral-600 dark:text-neutral-400">Feature Version:</span>
                  <span className="font-medium dark:text-neutral-200">{features.feature_version}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600 dark:text-neutral-400">Model Version:</span>
                  <span className="font-medium dark:text-neutral-200">{features.metadata?.model_version || '--'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600 dark:text-neutral-400">Articles (7d):</span>
                  <span className="font-medium dark:text-neutral-200">{features.context?.article_count_7d || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600 dark:text-neutral-400">Last Calculated:</span>
                  <span className="font-medium dark:text-neutral-200">{formatDate(features.metadata?.created_at)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      <ToastManager toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};

export default StockDetail;

// Inline Articles section for simplicity
const ArticlesSection: React.FC<{ ticker: string }> = ({ ticker }) => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['articles', ticker, 7],
    queryFn: () => feedApi.getArticles({ ticker, days: 7, page: 1, page_size: 8 }),
    enabled: !!ticker,
    staleTime: 2 * 60 * 1000,
  });

  if (error) return null;

  return (
    <div className="card mb-8">
      <h2 className="text-xl font-semibold text-neutral-900 dark:text-white mb-4">Top Articles (7d)</h2>
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-16 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
          ))}
        </div>
      ) : data && data.items && data.items.length > 0 ? (
        <ul className="divide-y divide-neutral-200 dark:divide-neutral-700">
          {data.items.map((a) => (
            <li key={a.id} className="py-3">
              <div className="flex items-start justify-between">
                <div className="pr-4">
                  <a href={a.url} target="_blank" rel="noreferrer" className="font-medium text-blue-700 dark:text-blue-400 hover:underline">
                    {a.title || a.url}
                  </a>
                  <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                    {a.published_at ? formatDate(a.published_at) : '--'}
                    {a.author ? ` • ${a.author}` : ''}
                  </div>
                </div>
                <div className="shrink-0">
                  <span className={cn(
                    'px-2 py-0.5 rounded text-xs font-medium',
                    a.sentiment === null || a.sentiment === undefined
                      ? 'bg-neutral-50 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300'
                      : a.sentiment > 0
                      ? 'bg-success-50 dark:bg-success-900/30 text-success-700 dark:text-success-400'
                      : 'bg-danger-50 dark:bg-danger-900/30 text-danger-700 dark:text-danger-400'
                  )}>
                    {a.sentiment === null || a.sentiment === undefined ? '--' : a.sentiment.toFixed(2)}
                  </span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-sm text-neutral-500 dark:text-neutral-400">No recent articles found</div>
      )}
    </div>
  );
};
