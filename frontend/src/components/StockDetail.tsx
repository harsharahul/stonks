import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { feedApi } from '../api/client';
import { useParams } from 'react-router-dom';
import { useDailyFeatures, useFeatureHistory, useCalculateFeatures, useEnhancedAnalytics } from '../hooks/useFeatures';
import FeatureCard from './FeatureCard';
import FeatureChart from './FeatureChart';
import { cn, formatDate, formatRelativeTime, prepareChartData } from '../utils/format';

const StockDetail: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>();
  const ticker = symbol?.toUpperCase() || '';

  // Fetch current features and history
  const { data: features, isLoading: featuresLoading, error: featuresError } = useDailyFeatures(ticker);
  const { data: history, isLoading: historyLoading } = useFeatureHistory(ticker, 30);
  const calculateFeatures = useCalculateFeatures();
  const { data: enhanced, isLoading: enhancedLoading } = useEnhancedAnalytics(ticker);

  // Prepare chart data
  const sentimentData = history?.features ? prepareChartData(
    history.features,
    'date',
    'sent_mean_7d'
  ) : [];

  const returnsData = history?.features ? prepareChartData(
    history.features,
    'date', 
    'ret_5d'
  ) : [];

  const handleRefreshFeatures = () => {
    calculateFeatures.mutate({ ticker });
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
              <span className="font-semibold text-neutral-900">{features.article_count_7d}</span>
            </div>
            <div className="flex items-center justify-between sm:justify-start sm:space-x-2">
              <span className="text-neutral-600">Feature Version</span>
              <span className="font-semibold text-neutral-900">{features.feature_version}</span>
            </div>
            <div className="flex items-center justify-between sm:justify-start sm:space-x-2">
              <span className="text-neutral-600">Last Calculated</span>
              <span className="font-semibold text-neutral-900">{formatDate(features.created_at)}</span>
            </div>
          </div>
        </div>
      )}

      {/* Feature Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <FeatureCard
          title="7-Day Sentiment"
          value={features?.sent_mean_7d}
          format="sentiment"
          subtitle={`${features?.article_count_7d || 0} articles analyzed`}
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="5-Day Return"
          value={features?.ret_5d}
          format="return"
          subtitle="Price performance"
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="1-Day Return"
          value={features?.ret_1d}
          format="return"
          subtitle="Latest session"
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="20-Day Return"
          value={features?.ret_20d}
          format="return"
          subtitle="Monthly trend"
          isLoading={featuresLoading}
        />
      </div>

      {/* Advanced Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <FeatureCard
          title="Sentiment Shock"
          value={features?.sent_shock}
          format="number"
          subtitle="vs 90-day baseline"
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="Volume Z-Score"
          value={features?.vol_z}
          format="number"
          subtitle="Volume deviation"
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="14-Day Momentum"
          value={features?.momentum_14d}
          format="return"
          subtitle="Avg daily return"
          isLoading={featuresLoading}
        />
        <FeatureCard
          title="Novelty Score"
          value={features?.novelty_mean_3d}
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
                  <span className="font-medium">{features.sent_mean_3d?.toFixed(3) || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">7-Day Average:</span>
                  <span className="font-medium">{features.sent_mean_7d?.toFixed(3) || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">10-Day Average:</span>
                  <span className="font-medium">{features.sent_mean_10d?.toFixed(3) || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Volume Weighted:</span>
                  <span className="font-medium">{features.sent_volume_weighted?.toFixed(3) || '—'}</span>
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
                  <span className="font-medium">{features.model_version || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Articles (7d):</span>
                  <span className="font-medium">{features.article_count_7d}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Last Calculated:</span>
                  <span className="font-medium">{formatDate(features.created_at)}</span>
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
