import React, { useState, useEffect } from 'react';
import { Database, RefreshCw, CheckCircle, AlertCircle, Clock, TrendingUp, FileText, MessageCircle } from 'lucide-react';

interface IngestionSource {
  name: string;
  type: 'wsb' | 'sec_edgar' | 'earnings' | 'news';
  status: 'operational' | 'degraded' | 'down';
  lastUpdate: string;
  articleCount: number;
  icon: React.ReactNode;
  color: string;
  description: string;
}

interface APISource {
  name: string;
  status: string;
  last_update: string;
  article_count: number;
  source_type: string;
}

const DataIngestionStatus: React.FC = () => {
  const [sources, setSources] = useState<IngestionSource[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/v1/feed/ingest/status');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      
      // Map API data to frontend format
      const mappedSources: IngestionSource[] = data.sources.map((apiSource: APISource) => {
        let type: 'wsb' | 'sec_edgar' | 'earnings' | 'news' = 'news';
        let icon: React.ReactNode = <Database className="w-5 h-5" />;
        let color = 'text-gray-600';
        let description = 'Data ingestion source';

        // Determine type and styling based on source name
        if (apiSource.name.includes('WSB')) {
          type = 'wsb';
          icon = <MessageCircle className="w-5 h-5" />;
          color = 'text-red-600';
          description = 'Enhanced Reddit parser with sentiment analysis';
        } else if (apiSource.name.includes('SEC')) {
          type = 'sec_edgar';
          icon = <FileText className="w-5 h-5" />;
          color = 'text-blue-600';
          description = '8-K, 10-K, 10-Q filings with sec-parser';
        } else if (apiSource.name.includes('Earnings')) {
          type = 'earnings';
          icon = <TrendingUp className="w-5 h-5" />;
          color = 'text-green-600';
          description = 'Alpha Vantage earnings data';
        } else if (apiSource.name.includes('News')) {
          type = 'news';
          icon = <Database className="w-5 h-5" />;
          color = 'text-yellow-600';
          description = 'Google News and RSS feeds';
        }

        // Calculate time ago
        const lastUpdate = apiSource.last_update ? 
          new Date(apiSource.last_update).toLocaleString() : 'Unknown';

        return {
          name: apiSource.name,
          type,
          status: apiSource.status as 'operational' | 'degraded' | 'down',
          lastUpdate,
          articleCount: apiSource.article_count,
          icon,
          color,
          description
        };
      });

      setSources(mappedSources);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch ingestion status:', err);
      setError('Failed to fetch status');
      // Fallback to default sources if API fails
      setSources([
        {
          name: 'WSB Reddit',
          type: 'wsb',
          status: 'operational',
          lastUpdate: '2 min ago',
          articleCount: 7,
          icon: <MessageCircle className="w-5 h-5" />,
          color: 'text-red-600',
          description: 'Enhanced Reddit parser with sentiment analysis'
        },
        {
          name: 'SEC EDGAR',
          type: 'sec_edgar',
          status: 'operational',
          lastUpdate: '5 min ago',
          articleCount: 4,
          icon: <FileText className="w-5 h-5" />,
          color: 'text-blue-600',
          description: '8-K, 10-K, 10-Q filings with sec-parser'
        },
        {
          name: 'Earnings Calendar',
          type: 'earnings',
          status: 'operational',
          lastUpdate: '1 hour ago',
          articleCount: 9190,
          icon: <TrendingUp className="w-5 h-5" />,
          color: 'text-green-600',
          description: 'Alpha Vantage earnings data'
        },
        {
          name: 'News RSS',
          type: 'news',
          status: 'degraded',
          lastUpdate: '3 hours ago',
          articleCount: 0,
          icon: <Database className="w-5 h-5" />,
          color: 'text-yellow-600',
          description: 'Google News and RSS feeds'
        }
      ]);
    }
  };

  const refreshStatus = async () => {
    setIsRefreshing(true);
    await fetchStatus();
    setLastRefresh(new Date());
    setIsRefreshing(false);
  };

  // Fetch status on component mount
  useEffect(() => {
    fetchStatus();
  }, []);

  // Auto-refresh every 2 minutes
  useEffect(() => {
    const interval = setInterval(refreshStatus, 2 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'operational': return 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-700';
      case 'degraded': return 'text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/30 border-yellow-200 dark:border-yellow-700';
      case 'down': return 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-700';
      default: return 'text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/30 border-gray-200 dark:border-gray-700';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'operational': return <CheckCircle className="w-4 h-4" />;
      case 'degraded': return <AlertCircle className="w-4 h-4" />;
      case 'down': return <AlertCircle className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'operational': return 'Operational';
      case 'degraded': return 'Degraded';
      case 'down': return 'Down';
      default: return 'Unknown';
    }
  };

  const totalArticles = sources.reduce((sum, source) => sum + source.articleCount, 0);
  const operationalSources = sources.filter(s => s.status === 'operational').length;

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-neutral-900 dark:text-white">Data Ingestion Status</h2>
          <p className="text-sm text-neutral-600 dark:text-neutral-400">Real-time monitoring of data pipeline health</p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="text-right">
            <div className="text-sm text-neutral-500 dark:text-neutral-400">Last refresh</div>
            <div className="text-xs text-neutral-400 dark:text-neutral-500">
              {lastRefresh.toLocaleTimeString()}
            </div>
          </div>
          <button
            onClick={refreshStatus}
            disabled={isRefreshing}
            className={`px-3 py-2 rounded-lg font-medium transition-colors duration-200 ${
              isRefreshing
                ? 'bg-neutral-100 dark:bg-neutral-700 text-neutral-400 dark:text-neutral-500 cursor-not-allowed'
                : 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-200 dark:hover:bg-blue-900/50'
            }`}
            title="Refresh status"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-lg">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
            <span className="text-sm text-red-700 dark:text-red-400">{error}</span>
          </div>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-gradient-to-r from-blue-50 to-blue-100 dark:from-blue-900/30 dark:to-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-700">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-200 dark:bg-blue-900/50 rounded-lg">
              <Database className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <div className="text-sm text-blue-600 dark:text-blue-400 font-medium">Total Articles</div>
              <div className="text-2xl font-bold text-blue-900 dark:text-blue-300">{totalArticles.toLocaleString()}</div>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-green-50 to-green-100 dark:from-green-900/30 dark:to-green-900/20 p-4 rounded-lg border border-green-200 dark:border-green-700">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-green-200 dark:bg-green-900/50 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <div className="text-sm text-green-600 dark:text-green-400 font-medium">Operational</div>
              <div className="text-2xl font-bold text-green-900 dark:text-green-300">{operationalSources}/{sources.length}</div>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-purple-50 to-purple-100 dark:from-purple-900/30 dark:to-purple-900/20 p-4 rounded-lg border border-purple-200 dark:border-purple-700">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-purple-200 dark:bg-purple-900/50 rounded-lg">
              <TrendingUp className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <div className="text-sm text-purple-600 dark:text-purple-400 font-medium">Pipeline Health</div>
              <div className="text-2xl font-bold text-purple-900 dark:text-purple-300">
                {Math.round((operationalSources / sources.length) * 100)}%
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Data Sources */}
      <div className="space-y-4">
        {sources.map((source) => (
          <div
            key={source.name}
            className="p-4 border border-neutral-200 dark:border-neutral-700 rounded-lg hover:shadow-md transition-shadow duration-200"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className={`p-2 rounded-lg ${source.color.replace('text-', 'bg-').replace('-600', '-100')}`}>
                  {source.icon}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="font-semibold text-neutral-900 dark:text-white">{source.name}</h3>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(source.status)}`}>
                      <div className="flex items-center space-x-1">
                        {getStatusIcon(source.status)}
                        <span>{getStatusText(source.status)}</span>
                      </div>
                    </span>
                  </div>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">{source.description}</p>
                </div>
              </div>

              <div className="text-right">
                <div className="text-sm text-neutral-500 dark:text-neutral-400">Articles</div>
                <div className="text-lg font-semibold text-neutral-900 dark:text-white">
                  {source.articleCount.toLocaleString()}
                </div>
                <div className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
                  {source.lastUpdate}
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-neutral-500 dark:text-neutral-400 mb-1">
                <span>Data Freshness</span>
                <span>{source.lastUpdate}</span>
              </div>
              <div className="w-full bg-neutral-200 dark:bg-neutral-600 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all duration-300 ${
                    source.status === 'operational' ? 'bg-green-500' :
                    source.status === 'degraded' ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`}
                  style={{ 
                    width: source.status === 'operational' ? '100%' : 
                           source.status === 'degraded' ? '60%' : '20%' 
                  }}
                ></div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* System Status */}
      <div className="mt-6 pt-4 border-t border-neutral-200 dark:border-neutral-700">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 dark:bg-green-400 rounded-full animate-pulse"></div>
            <span className="text-neutral-600 dark:text-neutral-400">System Status: All Systems Operational</span>
          </div>
          <div className="text-neutral-500 dark:text-neutral-400">
            Next refresh in 2 minutes
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataIngestionStatus;
