import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import StockDetail from './components/StockDetail';
import { useFeaturesSummary, useFeatureStats } from './hooks/useFeatures';
import { cn } from './utils/format';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

const Navigation: React.FC = () => {
  const location = useLocation();
  
  return (
    <nav className="bg-white border-b border-neutral-200">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link to="/" className="flex items-center space-x-2">
              <span className="text-2xl">📈</span>
              <h1 className="text-xl font-bold text-neutral-900">Stonks</h1>
            </Link>
          </div>
          <div className="flex items-center space-x-8">
            <Link
              to="/"
              className={cn(
                'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                location.pathname === '/'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
              )}
            >
              Dashboard
            </Link>
            <Link
              to="/stocks"
              className={cn(
                'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                location.pathname.startsWith('/stocks')
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
              )}
            >
              Stocks
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};

const Dashboard: React.FC = () => {
  const { data: summary, isLoading } = useFeaturesSummary();
  const { data: stats } = useFeatureStats(7);

  const topGainers = summary?.features
    ?.filter((s) => s.ret_5d !== null)
    .sort((a, b) => (b.ret_5d || 0) - (a.ret_5d || 0))
    .slice(0, 5) || [];

  const topLosers = summary?.features
    ?.filter((s) => s.ret_5d !== null)
    .sort((a, b) => (a.ret_5d || 0) - (b.ret_5d || 0))
    .slice(0, 5) || [];

  const sentimentLeaders = summary?.features
    ?.filter((s) => s.sent_mean_7d !== null)
    .sort((a, b) => (b.sent_mean_7d || 0) - (a.sent_mean_7d || 0))
    .slice(0, 5) || [];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-neutral-900 mb-2">Analytics Dashboard</h1>
        <p className="text-neutral-600">Real-time stock analytics powered by news sentiment and market data</p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="card">
          <div className="flex items-center">
            <div className="p-2 bg-blue-100 rounded-lg">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-neutral-600">Stocks Tracked</p>
              <p className="text-2xl font-bold text-neutral-900">{summary?.count || '—'}</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="p-2 bg-green-100 rounded-lg">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
              </svg>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-neutral-600">Features Date</p>
              <p className="text-lg font-bold text-neutral-900">{summary?.date || '—'}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-2 bg-purple-100 rounded-lg">
              <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-neutral-600">Version</p>
              <p className="text-lg font-bold text-neutral-900">{summary?.feature_version || '—'}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-2 bg-orange-100 rounded-lg">
              <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-neutral-600">Status</p>
              <p className="text-lg font-bold text-green-600">Live</p>
            </div>
          </div>
        </div>
      </div>

      {/* Analytics Sections */}
      {/* Data Health */}
      <div className="card mb-8">
        <h2 className="text-xl font-semibold text-neutral-900 mb-4">Data Health</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <p className="text-sm text-neutral-600">Coverage</p>
            <p className="text-2xl font-bold text-neutral-900">
              {stats ? `${Math.round((stats.coverage.coverage_rate || 0) * 100)}%` : '—'}
            </p>
            <p className="text-xs text-neutral-500">{stats ? `${stats.coverage.unique_tickers_with_features}/${stats.coverage.total_active_tickers} tickers with features` : '—'}</p>
          </div>
          <div>
            <p className="text-sm text-neutral-600">Latest Feature Date</p>
            <p className="text-lg font-semibold text-neutral-900">{stats?.latest.latest_feature_date || '—'}</p>
            <p className="text-xs text-neutral-500">Range: {stats ? `${stats.date_range.start_date} → ${stats.date_range.end_date}` : '—'}</p>
          </div>
          <div>
            <p className="text-sm text-neutral-600">Most Recent Ticker</p>
            <p className="text-lg font-semibold text-neutral-900">{stats?.latest.latest_ticker || '—'}</p>
            <p className="text-xs text-neutral-500">Last update recency reflects pipeline freshness</p>
          </div>
        </div>
      </div>

      {/* Analytics Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="card">
          <h2 className="text-xl font-semibold text-neutral-900 mb-4">Top Gainers (5d)</h2>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-6 bg-neutral-200 rounded w-full animate-pulse" />
              ))}
            </div>
          ) : (
            <ul className="divide-y divide-neutral-200">
              {topGainers.map((s) => (
                <li key={s.ticker} className="py-2 flex items-center justify-between">
                  <Link to={`/stocks/${s.ticker}`} className="font-medium text-neutral-900 hover:underline">
                    {s.ticker}
                  </Link>
                  <span className="text-success-600 font-semibold">{s.ret_5d ? `${(s.ret_5d * 100).toFixed(1)}%` : '—'}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <h2 className="text-xl font-semibold text-neutral-900 mb-4">Top Losers (5d)</h2>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-6 bg-neutral-200 rounded w-full animate-pulse" />
              ))}
            </div>
          ) : (
            <ul className="divide-y divide-neutral-200">
              {topLosers.map((s) => (
                <li key={s.ticker} className="py-2 flex items-center justify-between">
                  <Link to={`/stocks/${s.ticker}`} className="font-medium text-neutral-900 hover:underline">
                    {s.ticker}
                  </Link>
                  <span className="text-danger-600 font-semibold">{s.ret_5d ? `${(s.ret_5d * 100).toFixed(1)}%` : '—'}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <h2 className="text-xl font-semibold text-neutral-900 mb-4">Sentiment Leaders (7d)</h2>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-6 bg-neutral-200 rounded w-full animate-pulse" />
              ))}
            </div>
          ) : (
            <ul className="divide-y divide-neutral-200">
              {sentimentLeaders.map((s) => (
                <li key={s.ticker} className="py-2 flex items-center justify-between">
                  <Link to={`/stocks/${s.ticker}`} className="font-medium text-neutral-900 hover:underline">
                    {s.ticker}
                  </Link>
                  <span className="text-neutral-700">{s.sent_mean_7d?.toFixed(2) || '—'}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Stock Grid */}
      <div className="card">
        <h2 className="text-xl font-semibold text-neutral-900 mb-6">Featured Stocks</h2>
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="h-24 bg-neutral-200 rounded"></div>
              </div>
            ))}
          </div>
        ) : summary?.features ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {summary.features.slice(0, 6).map((stock) => (
              <Link
                key={stock.ticker}
                to={`/stocks/${stock.ticker}`}
                className="p-4 border border-neutral-200 rounded-lg hover:border-blue-300 hover:shadow-md transition-all duration-200"
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-lg font-semibold text-neutral-900">{stock.ticker}</h3>
                  <span className={cn(
                    'px-2 py-1 rounded text-xs font-medium',
                    stock.ret_5d && stock.ret_5d > 0 
                      ? 'bg-success-50 text-success-700'
                      : stock.ret_5d && stock.ret_5d < 0
                      ? 'bg-danger-50 text-danger-700'
                      : 'bg-neutral-50 text-neutral-700'
                  )}>
                    {stock.ret_5d ? `${(stock.ret_5d * 100).toFixed(1)}%` : '—'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-neutral-500">Sentiment (7d)</p>
                    <p className="font-medium">{stock.sent_mean_7d?.toFixed(2) || '—'}</p>
                  </div>
                  <div>
                    <p className="text-neutral-500">Articles (7d)</p>
                    <p className="font-medium">{stock.article_count_7d}</p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-neutral-500">No featured stocks available</p>
          </div>
        )}
      </div>
    </div>
  );
};

const StockList: React.FC = () => {
  const { data: summary, isLoading } = useFeaturesSummary(undefined, 50);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-neutral-900 mb-2">All Stocks</h1>
        <p className="text-neutral-600">Complete list of tracked stocks with live analytics</p>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="animate-pulse">
              <div className="h-16 bg-neutral-200 rounded"></div>
            </div>
          ))}
        </div>
      ) : summary?.features ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {summary.features.map((stock) => (
            <Link
              key={stock.ticker}
              to={`/stocks/${stock.ticker}`}
              className="card hover:shadow-lg transition-shadow duration-200"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xl font-bold text-neutral-900">{stock.ticker}</h3>
                <span className={cn(
                  'px-2 py-1 rounded text-sm font-medium',
                  stock.ret_5d && stock.ret_5d > 0 
                    ? 'bg-success-50 text-success-700'
                    : stock.ret_5d && stock.ret_5d < 0
                    ? 'bg-danger-50 text-danger-700'
                    : 'bg-neutral-50 text-neutral-700'
                )}>
                  {stock.ret_5d ? `${(stock.ret_5d * 100).toFixed(1)}%` : '—'}
                </span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-neutral-600">Sentiment (7d):</span>
                  <span className="font-medium">{stock.sent_mean_7d?.toFixed(2) || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Articles:</span>
                  <span className="font-medium">{stock.article_count_7d}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Novelty:</span>
                  <span className="font-medium">{stock.novelty_mean_3d?.toFixed(2) || '—'}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <p className="text-neutral-500">No stocks available</p>
        </div>
      )}
    </div>
  );
};

const AppContent: React.FC = () => {
  return (
    <div className="min-h-screen bg-neutral-50">
      <Navigation />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/stocks" element={<StockList />} />
        <Route path="/stocks/:symbol" element={<StockDetail />} />
      </Routes>
    </div>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <AppContent />
      </Router>
    </QueryClientProvider>
  );
}

export default App;
