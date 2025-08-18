import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { feedApi } from '../api/client';
import { useParams } from 'react-router-dom';
import { useDailyFeatures, useFeatureHistory, useCalculateFeatures, useEnhancedAnalytics } from '../hooks/useFeatures';
import FeatureCard from './FeatureCard';
import FeatureChart from './FeatureChart';
import { cn, formatDate, formatRelativeTime, prepareChartData } from '../utils/format';

// Hook to fetch WSB trending data for a specific ticker
const useWSBTrendingData = (ticker: string) => {
  return useQuery({
    queryKey: ['wsb-trending', ticker],
    queryFn: async () => {
      const response = await fetch(`http://localhost:8080/api/v1/feed/wsb/trending?days=7&limit=50`);
      const data = await response.json();
      return data.trending_tickers?.find((t: any) => t.ticker === ticker) || null;
    },
    enabled: !!ticker,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
};

const StockDetail: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>();
  const ticker = symbol?.toUpperCase() || '';

  // Fetch current features and history
  const { data: features, isLoading: featuresLoading, error: featuresError } = useDailyFeatures(ticker);
  const { data: history, isLoading: historyLoading } = useFeatureHistory(ticker, 30);
  const calculateFeatures = useCalculateFeatures();
  const { data: enhanced, isLoading: enhancedLoading } = useEnhancedAnalytics(ticker);
  
  // Fetch WSB trending data as fallback
  const { data: wsbTrending, isLoading: wsbLoading } = useWSBTrendingData(ticker);

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
          <div className="text-red-500 text-xl mb-4">⚠️ Error Loading Stock Data</div>
          <p className="text-neutral-600 mb-4">
            Could not load features for {ticker}. This might be because:
          </p>
          <ul className="text-left text-sm text-neutral-500 max-w-md mx-auto mb-6">
            <li>• Stock symbol not found in our database</li>
            <li>• No recent data available for this ticker</li>
            <li>• Network connectivity issues</li>
          </ul>
          <button
            onClick={handleRefreshFeatures}
            disabled={calculateFeatures.isLoading}
            className="btn-primary"
          >
            {calculateFeatures.isLoading ? 'Calculating...' : 'Try Calculate Features'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900">{ticker}</h1>
          <p className="text-neutral-600 mt-1">Stock Analytics Dashboard</p>
        </div>
        <div className="flex items-center space-x-4">
          {features && (
            <div className="text-right">
              <p className="text-sm text-neutral-500">Last Updated</p>
              <p className="text-sm font-medium">
                {formatRelativeTime(features.created_at)}
              </p>
            </div>
          )}
          <button
            onClick={handleRefreshFeatures}
            disabled={calculateFeatures.isLoading}
            className="btn-primary"
          >
            {calculateFeatures.isLoading ? 'Calculating...' : 'Refresh Features'}
          </button>
        </div>
      </div>

      {/* Data Coverage Strip */}
      {features && (
        <div className="card mb-8">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
            <div className="flex items-center justify-between sm:justify-start sm:space-x-2">
              <span className="text-neutral-600">Articles (7d)</span>
              <span className="font-semibold text-neutral-900">{features.context?.article_count_7d || 0}</span>
            </div>
            <div className="flex items-center justify-between sm:justify-start sm:space-x-2">
              <span className="text-neutral-600">Feature Version</span>
              <span className="font-semibold text-neutral-900">{features.feature_version}</span>
            </div>
            <div className="flex items-center justify-between sm:justify-start sm:space-x-2">
              <span className="text-neutral-600">WSB Sentiment</span>
              <span className="font-semibold text-neutral-900">
                {getWSBData('wsb_sentiment_7d') ? getWSBData('wsb_sentiment_7d').toFixed(3) : 'N/A'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* WSB Sentiment Section */}
      <div className="card mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-neutral-900">🦍 WSB Sentiment Analysis</h2>
          <div className="flex items-center space-x-2">
            <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-medium rounded-full">
              LIVE DATA
            </span>
            {wsbLoading && (
              <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-medium rounded-full">
                🔄 Loading Trending Data
              </span>
            )}
            {wsbTrending && !features?.retail_sentiment?.wsb_mention_count_7d && (
              <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-medium rounded-full">
                📊 From Trending Data
              </span>
            )}
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 bg-gradient-to-r from-red-50 to-red-100 rounded-lg border border-red-200">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-red-600">📊</span>
              <span className="text-sm font-medium text-red-700">WSB Mentions</span>
            </div>
            <div className="text-2xl font-bold text-red-900">
              {getWSBData('wsb_mention_count_7d')}
            </div>
            <div className="text-xs text-red-600 mt-1">Last 7 days</div>
          </div>

          <div className="p-4 bg-gradient-to-r from-blue-50 to-blue-100 rounded-lg border border-blue-200">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-blue-600">💬</span>
              <span className="text-sm font-medium text-blue-700">Sentiment (7d)</span>
            </div>
            <div className="text-2xl font-bold text-blue-900">
              {getWSBData('wsb_sentiment_7d') ? getWSBData('wsb_sentiment_7d').toFixed(3) : 'N/A'}
            </div>
            <div className="text-xs text-blue-600 mt-1">
              {getWSBData('wsb_sentiment_7d') && getWSBData('wsb_sentiment_7d') > 0.5 ? 'Bullish' : 
               getWSBData('wsb_sentiment_7d') && getWSBData('wsb_sentiment_7d') < 0.5 ? 'Bearish' : 'Neutral'}
            </div>
          </div>

          <div className="p-4 bg-gradient-to-r from-green-50 to-green-100 rounded-lg border border-green-200">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-green-600">🚀</span>
              <span className="text-sm font-medium text-green-700">Engagement</span>
            </div>
            <div className="text-2xl font-bold text-green-900">
              {getWSBData('wsb_engagement_score') ? getWSBData('wsb_engagement_score').toFixed(3) : 'N/A'}
            </div>
            <div className="text-xs text-green-600 mt-1">Reddit activity</div>
          </div>

          <div className="p-4 bg-gradient-to-r from-purple-50 to-purple-100 rounded-lg border border-purple-200">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-purple-600">🎭</span>
              <span className="text-sm font-medium text-purple-700">Meme Potential</span>
            </div>
            <div className="text-2xl font-bold text-purple-900">
              {getWSBData('meme_stock_indicator') ? getWSBData('meme_stock_indicator').toFixed(3) : 'N/A'}
            </div>
            <div className="text-xs text-purple-600 mt-1">WSB meme score</div>
          </div>
        </div>

        {/* Sentiment Visualization */}
        {getWSBData('wsb_sentiment_7d') && (
          <div className="mt-6">
            <div className="flex items-center justify-between text-sm text-neutral-600 mb-2">
              <span>Sentiment Distribution</span>
              <span className="font-medium">
                {getWSBData('wsb_sentiment_7d') > 0.6 ? 'Very Bullish' :
                 getWSBData('wsb_sentiment_7d') > 0.4 ? 'Moderately Bullish' :
                 getWSBData('wsb_sentiment_7d') > 0.2 ? 'Slightly Bearish' : 'Very Bearish'}
              </span>
            </div>
            <div className="w-full bg-neutral-200 rounded-full h-3">
              <div
                className="bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 h-3 rounded-full transition-all duration-500"
                style={{ width: `${getWSBData('wsb_sentiment_7d') * 100}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-xs text-neutral-500 mt-1">
              <span>Bearish</span>
              <span>Neutral</span>
              <span>Bullish</span>
            </div>
          </div>
        )}
      </div>

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

      {/* AI Insights */}
      <div className="card mb-8">
        <h2 className="text-xl font-semibold text-neutral-900 mb-4">AI Insights</h2>
        {enhancedLoading ? (
          <div className="space-y-2 animate-pulse">
            <div className="h-4 bg-neutral-200 rounded w-1/3" />
            <div className="h-4 bg-neutral-200 rounded w-2/3" />
            <div className="h-24 bg-neutral-200 rounded" />
          </div>
        ) : enhanced ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-3 bg-neutral-50 rounded border border-neutral-200">
                <div className="text-xs text-neutral-500">Risk Level</div>
                <div className="text-lg font-semibold capitalize">{enhanced.llm_enhancement.summary.risk_level}</div>
              </div>
              <div className="p-3 bg-neutral-50 rounded border border-neutral-200">
                <div className="text-xs text-neutral-500">Confidence</div>
                <div className="text-lg font-semibold capitalize">{enhanced.llm_enhancement.summary.recommendation_confidence}</div>
              </div>
              <div className="p-3 bg-neutral-50 rounded border border-neutral-200">
                <div className="text-xs text-neutral-500">Article Coverage</div>
                <div className="text-lg font-semibold">{enhanced.llm_enhancement.analysis.article_coverage}</div>
              </div>
            </div>
            {enhanced.llm_enhancement.llm_enhancements.article_synthesis && (
              <div>
                <h3 className="text-lg font-medium text-neutral-900 mb-2">Article Synthesis</h3>
                <p className="text-sm text-neutral-700 whitespace-pre-line">{enhanced.llm_enhancement.llm_enhancements.article_synthesis}</p>
              </div>
            )}
            {enhanced.llm_enhancement.llm_enhancements.recommendations && (
              <div>
                <h3 className="text-lg font-medium text-neutral-900 mb-2">Recommendations</h3>
                <p className="text-sm text-neutral-700 whitespace-pre-line">{enhanced.llm_enhancement.llm_enhancements.recommendations}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-neutral-500">No AI insights available.</div>
        )}
      </div>

      {/* Top Articles (7d) */}
      <ArticlesSection ticker={ticker} />

      {/* Feature Details */}
      {features && (
        <div className="card">
          <h2 className="text-xl font-semibold text-neutral-900 mb-4">Feature Details</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <h3 className="text-lg font-medium text-neutral-800 mb-3">Sentiment Analysis</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-neutral-600">3-Day Average:</span>
                  <span className="font-medium">{features.sentiment?.mean_3d?.toFixed(3) || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">7-Day Average:</span>
                  <span className="font-medium">{features.sentiment?.mean_7d?.toFixed(3) || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">10-Day Average:</span>
                  <span className="font-medium">{features.sentiment?.mean_10d?.toFixed(3) || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Volume Weighted:</span>
                  <span className="font-medium">{features.sentiment?.volume_weighted?.toFixed(3) || '—'}</span>
                </div>
              </div>
            </div>
            <div>
              <h3 className="text-lg font-medium text-neutral-800 mb-3">Market Metrics</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-neutral-600">Feature Version:</span>
                  <span className="font-medium">{features.feature_version}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Model Version:</span>
                  <span className="font-medium">{features.metadata?.model_version || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Articles (7d):</span>
                  <span className="font-medium">{features.context?.article_count_7d || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Last Calculated:</span>
                  <span className="font-medium">{formatDate(features.metadata?.created_at)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
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
      <h2 className="text-xl font-semibold text-neutral-900 mb-4">Top Articles (7d)</h2>
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-16 bg-neutral-200 rounded animate-pulse" />
          ))}
        </div>
      ) : data && data.items && data.items.length > 0 ? (
        <ul className="divide-y divide-neutral-200">
          {data.items.map((a) => (
            <li key={a.id} className="py-3">
              <div className="flex items-start justify-between">
                <div className="pr-4">
                  <a href={a.url} target="_blank" rel="noreferrer" className="font-medium text-blue-700 hover:underline">
                    {a.title || a.url}
                  </a>
                  <div className="text-xs text-neutral-500 mt-1">
                    {a.published_at ? formatDate(a.published_at) : '—'}
                    {a.author ? ` • ${a.author}` : ''}
                  </div>
                </div>
                <div className="shrink-0">
                  <span className={cn(
                    'px-2 py-0.5 rounded text-xs font-medium',
                    a.sentiment === null || a.sentiment === undefined
                      ? 'bg-neutral-50 text-neutral-700'
                      : a.sentiment > 0
                      ? 'bg-success-50 text-success-700'
                      : 'bg-danger-50 text-danger-700'
                  )}>
                    {a.sentiment === null || a.sentiment === undefined ? '—' : a.sentiment.toFixed(2)}
                  </span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-sm text-neutral-500">No recent articles found</div>
      )}
    </div>
  );
};
