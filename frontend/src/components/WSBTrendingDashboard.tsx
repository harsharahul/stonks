import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { TrendingUp, TrendingDown, Activity, Users, MessageCircle, Rocket } from 'lucide-react';

interface WSBTrendingTicker {
  ticker: string;
  mention_count: number;
  avg_sentiment: number;
  avg_reddit_score: number;
  avg_comments: number;
  trending_score: number;
}

interface WSBTrendingResponse {
  trending_tickers: WSBTrendingTicker[];
  days: number;
  total_found: number;
  generated_at: string;
}

const WSBTrendingDashboard: React.FC = () => {
  const [trendingData, setTrendingData] = useState<WSBTrendingResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchTrendingData = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('http://localhost:8080/api/v1/feed/wsb/trending');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data: WSBTrendingResponse = await response.json();
      setTrendingData(data);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch trending data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTrendingData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchTrendingData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const getSentimentColor = (sentiment: number) => {
    if (sentiment >= 0.6) return 'text-green-600 bg-green-50';
    if (sentiment >= 0.4) return 'text-blue-600 bg-blue-50';
    if (sentiment >= 0.2) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const getSentimentIcon = (sentiment: number) => {
    if (sentiment >= 0.6) return <TrendingUp className="w-4 h-4" />;
    if (sentiment >= 0.4) return <Activity className="w-4 h-4" />;
    if (sentiment >= 0.2) return <TrendingDown className="w-4 h-4" />;
    return <TrendingDown className="w-4 h-4" />;
  };

  const getTrendingScoreColor = (score: number) => {
    if (score >= 0.7) return 'text-purple-600 bg-purple-50 border-purple-200';
    if (score >= 0.5) return 'text-blue-600 bg-blue-50 border-blue-200';
    if (score >= 0.3) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-gray-600 bg-gray-50 border-gray-200';
  };

  if (isLoading) {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-neutral-900">🦍 WSB Trending</h2>
          <div className="h-4 w-4 bg-neutral-200 rounded-full animate-pulse"></div>
        </div>
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-neutral-200 rounded animate-pulse"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-neutral-900">🦍 WSB Trending</h2>
          <button
            onClick={fetchTrendingData}
            className="text-sm text-blue-600 hover:text-blue-800 underline"
          >
            Retry
          </button>
        </div>
        <div className="text-center py-8">
          <div className="text-red-500 mb-2">⚠️ Failed to load trending data</div>
          <div className="text-sm text-neutral-500">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <h2 className="text-xl font-semibold text-neutral-900">🦍 WSB Trending</h2>
          <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-medium rounded-full">
            LIVE
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={fetchTrendingData}
            className="p-2 text-neutral-500 hover:text-neutral-700 hover:bg-neutral-100 rounded-lg transition-colors"
            title="Refresh data"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          {lastUpdated && (
            <span className="text-xs text-neutral-500">
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {trendingData?.trending_tickers && trendingData.trending_tickers.length > 0 ? (
        <div className="space-y-4">
          {trendingData.trending_tickers.map((ticker, index) => (
            <div
              key={ticker.ticker}
              className={`p-4 rounded-lg border-2 transition-all duration-200 hover:shadow-md ${
                index === 0 ? 'bg-gradient-to-r from-yellow-50 to-orange-50 border-yellow-200' :
                index === 1 ? 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200' :
                'bg-white border-neutral-200'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-3">
                  {index === 0 && <span className="text-2xl">🥇</span>}
                  {index === 1 && <span className="text-2xl">🥈</span>}
                  {index === 2 && <span className="text-2xl">🥉</span>}
                  <Link
                    to={`/stocks/${ticker.ticker}`}
                    className="text-xl font-bold text-neutral-900 hover:text-blue-600 transition-colors"
                  >
                    ${ticker.ticker}
                  </Link>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getTrendingScoreColor(ticker.trending_score)}`}>
                    {ticker.trending_score.toFixed(3)}
                  </span>
                </div>
                <div className="flex items-center space-x-1 text-neutral-500">
                  <Rocket className="w-4 h-4" />
                  <span className="text-sm font-medium">#{index + 1}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="flex items-center space-x-2">
                  <Users className="w-4 h-4 text-blue-500" />
                  <div>
                    <div className="text-sm text-neutral-500">Mentions</div>
                    <div className="font-semibold text-neutral-900">{ticker.mention_count}</div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <div className={`w-4 h-4 ${getSentimentColor(ticker.avg_sentiment).split(' ')[0]}`}>
                    {getSentimentIcon(ticker.avg_sentiment)}
                  </div>
                  <div>
                    <div className="text-sm text-neutral-500">Sentiment</div>
                    <div className={`font-semibold ${getSentimentColor(ticker.avg_sentiment).split(' ')[0]}`}>
                      {ticker.avg_sentiment.toFixed(3)}
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <TrendingUp className="w-4 h-4 text-green-500" />
                  <div>
                    <div className="text-sm text-neutral-500">Reddit Score</div>
                    <div className="font-semibold text-neutral-900">
                      {ticker.avg_reddit_score.toFixed(0)}
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <MessageCircle className="w-4 h-4 text-purple-500" />
                  <div>
                    <div className="text-sm text-neutral-500">Comments</div>
                    <div className="font-semibold text-neutral-900">
                      {ticker.avg_comments.toFixed(0)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Sentiment Bar */}
              <div className="mt-3">
                <div className="flex items-center justify-between text-xs text-neutral-500 mb-1">
                  <span>Bearish</span>
                  <span>Neutral</span>
                  <span>Bullish</span>
                </div>
                <div className="w-full bg-neutral-200 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${ticker.avg_sentiment * 100}%` }}
                  ></div>
                </div>
              </div>
            </div>
          ))}

          <div className="text-center pt-4 border-t border-neutral-200">
            <div className="text-sm text-neutral-500">
              📊 {trendingData.total_found} trending tickers • 
              📅 Last {trendingData.days} days • 
              🕐 Updated {new Date(trendingData.generated_at).toLocaleTimeString()}
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-8">
          <div className="text-neutral-400 mb-2">🦍</div>
          <div className="text-neutral-500">No trending tickers found</div>
          <div className="text-sm text-neutral-400 mt-1">
            WSB sentiment data will appear here when available
          </div>
        </div>
      )}
    </div>
  );
};

export default WSBTrendingDashboard;
