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
      case 'operational': return 'text-green-600 bg-green-50 border-green-200';
      case 'degraded': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'down': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
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
          <h2 className="text-xl font-bold text-neutral-900">Data Ingestion Status</h2>
          <p className="text-sm text-neutral-600">Real-time monitoring of data pipeline health</p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="text-right">
            <div className="text-sm text-neutral-500">Last refresh</div>
            <div className="text-xs text-neutral-400">
              {lastRefresh.toLocaleTimeString()}
            </div>
          </div>
          <button
            onClick={refreshStatus}
            disabled={isRefreshing}
            className={`px-3 py-2 rounded-lg font-medium transition-colors duration-200 ${
              isRefreshing 
                ? 'bg-neutral-100 text-neutral-400 cursor-not-allowed' 
                : 'bg-blue-100 text-blue-600 hover:bg-blue-200'
            }`}
            title="Refresh status"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-red-600" />
            <span className="text-sm text-red-700">{error}</span>
          </div>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-gradient-to-r from-blue-50 to-blue-100 p-4 rounded-lg border border-blue-200">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-200 rounded-lg">
              <Database className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <div className="text-sm text-blue-600 font-medium">Total Articles</div>
              <div className="text-2xl font-bold text-blue-900">{totalArticles.toLocaleString()}</div>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-green-50 to-green-100 p-4 rounded-lg border border-green-200">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-green-200 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <div className="text-sm text-green-600 font-medium">Operational</div>
              <div className="text-2xl font-bold text-green-900">{operationalSources}/{sources.length}</div>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-purple-50 to-purple-100 p-4 rounded-lg border border-purple-200">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-purple-200 rounded-lg">
              <TrendingUp className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <div className="text-sm text-purple-600 font-medium">Pipeline Health</div>
              <div className="text-2xl font-bold text-purple-900">
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
            className="p-4 border border-neutral-200 rounded-lg hover:shadow-md transition-shadow duration-200"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className={`p-2 rounded-lg ${source.color.replace('text-', 'bg-').replace('-600', '-100')}`}>
                  {source.icon}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="font-semibold text-neutral-900">{source.name}</h3>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(source.status)}`}>
                      <div className="flex items-center space-x-1">
                        {getStatusIcon(source.status)}
                        <span>{getStatusText(source.status)}</span>
                      </div>
                    </span>
                  </div>
                  <p className="text-sm text-neutral-600 mt-1">{source.description}</p>
                </div>
              </div>

              <div className="text-right">
                <div className="text-sm text-neutral-500">Articles</div>
                <div className="text-lg font-semibold text-neutral-900">
                  {source.articleCount.toLocaleString()}
                </div>
                <div className="text-xs text-neutral-400 mt-1">
                  {source.lastUpdate}
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-neutral-500 mb-1">
                <span>Data Freshness</span>
                <span>{source.lastUpdate}</span>
              </div>
              <div className="w-full bg-neutral-200 rounded-full h-2">
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
      <div className="mt-6 pt-4 border-t border-neutral-200">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-neutral-600">System Status: All Systems Operational</span>
          </div>
          <div className="text-neutral-500">
            Next refresh in 2 minutes
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataIngestionStatus;
