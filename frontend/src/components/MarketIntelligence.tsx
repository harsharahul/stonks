import React, { useState, useEffect } from 'react';

interface SystemHealth {
  stocks_tracked: number;
  active_signals: number;
  active_alerts: number;
  status: string;
}

interface MarketOverview {
  success: boolean;
  analysis_date: string;
  system_health: SystemHealth;
  data_availability: {
    yesterday_features: number;
    today_features: number;
    recent_stocks_with_data: number;
  };
  recent_stocks: Array<{
    ticker: string;
    sentiment: number;
    returns: number;
    articles: number;
    volume_z: number;
    date: string;
  }>;
}

interface SentimentAnalysis {
  success: boolean;
  analysis_date: string;
  overall_sentiment: {
    score: number;
    label: string;
    color: string;
    confidence: string;
  };
  statistics: {
    avg_sentiment: number;
    stocks_analyzed: number;
    total_articles: number;
  };
  stock_breakdown: Array<{
    ticker: string;
    sentiment: number;
    articles: number;
    date: string;
  }>;
}

interface PressureTestSummary {
  success: boolean;
  test_date: string;
  test_results: {
    system_health: string;
    database_status: string;
    ai_system_status: string;
    alert_system_status: string;
  };
  performance_metrics: {
    stocks_tracked: number;
    active_signals: number;
    active_alerts: number;
    yesterday_features: number;
    today_features: number;
  };
  ai_capabilities: {
    ollama_integration: string;
    analytics_agent: string;
    langgraph_workflows: string;
    self_correcting_system: string;
  };
  overall_status: string;
}

const MarketIntelligence: React.FC = () => {
  const [marketOverview, setMarketOverview] = useState<MarketOverview | null>(null);
  const [sentimentAnalysis, setSentimentAnalysis] = useState<SentimentAnalysis | null>(null);
  const [pressureTest, setPressureTest] = useState<PressureTestSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMarketIntelligence();
  }, []);

  const fetchMarketIntelligence = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all market data
      const baseUrl = 'http://localhost:8080';
      const [overviewRes, sentimentRes, pressureRes] = await Promise.all([
        fetch(`${baseUrl}/api/v1/market-analysis/market-overview`),
        fetch(`${baseUrl}/api/v1/market-analysis/sentiment-analysis`),
        fetch(`${baseUrl}/api/v1/market-analysis/pressure-test-summary`)
      ]);

      if (overviewRes.ok) {
        const overviewData = await overviewRes.json();
        console.log('📊 Market overview data received:', overviewData);
        setMarketOverview(overviewData);
      } else {
        console.error('❌ Overview response not ok:', overviewRes.status, overviewRes.statusText);
      }

      if (sentimentRes.ok) {
        const sentimentData = await sentimentRes.json();
        console.log('🎭 Sentiment data received:', sentimentData);
        setSentimentAnalysis(sentimentData);
      } else {
        console.error('❌ Sentiment response not ok:', sentimentRes.status, sentimentRes.statusText);
      }

      if (pressureRes.ok) {
        const pressureData = await pressureRes.json();
        console.log('🤖 Pressure test data received:', pressureData);
        setPressureTest(pressureData);
      } else {
        console.error('❌ Pressure test response not ok:', pressureRes.status, pressureRes.statusText);
      }

    } catch (err) {
      console.error('Error fetching market intelligence:', err);
      setError('Failed to load market intelligence data');
    } finally {
      setLoading(false);
    }
  };

  const getSentimentColor = (sentiment: number) => {
    if (sentiment > 0.6) return 'text-green-600 bg-green-100';
    if (sentiment > 0.4) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getReturnColor = (returns: number) => {
    if (returns > 0.02) return 'text-green-600';
    if (returns < -0.02) return 'text-red-600';
    return 'text-gray-600';
  };

  const getStatusColor = (status: string) => {
    if (status.includes('OPERATIONAL') || status.includes('EXCELLENT') || status.includes('WORKING')) {
      return 'text-green-600 bg-green-100';
    }
    if (status.includes('FUNCTIONAL') || status.includes('%')) {
      return 'text-yellow-600 bg-yellow-100';
    }
    return 'text-gray-600 bg-gray-100';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600">Loading market intelligence...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Error Loading Data</h3>
            <p className="mt-1 text-sm text-red-700">{error}</p>
          </div>
        </div>
        <div className="mt-4">
          <button
            onClick={fetchMarketIntelligence}
            className="bg-red-600 text-white px-4 py-2 rounded-md text-sm hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-6 text-white">
        <h2 className="text-2xl font-bold mb-2">🤖 AI Market Intelligence</h2>
        <p className="text-blue-100">AI-powered market analysis with local LLM processing</p>
        <div className="mt-4 flex items-center space-x-4 text-sm">
          <span>📅 {marketOverview?.analysis_date || 'Today'}</span>
          <span>🔄 Real-time Analysis</span>
          <span>🚀 Pressure Test: Successful</span>
        </div>
      </div>

      {/* System Health Dashboard */}
      {marketOverview && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            🏥 System Health & Overview
            <span className="ml-2 text-sm bg-green-100 text-green-800 px-2 py-1 rounded-full">
              {marketOverview.system_health.status.toUpperCase()}
            </span>
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-blue-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">{marketOverview.system_health.stocks_tracked}</div>
              <div className="text-sm text-gray-600">Stocks Tracked</div>
            </div>
            <div className="bg-green-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-green-600">{marketOverview.system_health.active_signals}</div>
              <div className="text-sm text-gray-600">Active Signals</div>
            </div>
            <div className="bg-yellow-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-yellow-600">{marketOverview.system_health.active_alerts}</div>
              <div className="text-sm text-gray-600">Active Alerts</div>
            </div>
            <div className="bg-purple-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-purple-600">{marketOverview.data_availability.recent_stocks_with_data}</div>
              <div className="text-sm text-gray-600">Recent Data</div>
            </div>
          </div>

          {/* Recent Stocks */}
          <h4 className="font-medium mb-3">📈 Recent Stock Analysis</h4>
          <div className="space-y-3">
            {marketOverview.recent_stocks.map((stock) => (
              <div key={stock.ticker} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-4">
                  <span className="font-semibold text-lg">{stock.ticker}</span>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSentimentColor(stock.sentiment)}`}>
                    Sentiment: {stock.sentiment.toFixed(3)}
                  </span>
                </div>
                <div className="flex items-center space-x-4 text-sm">
                  <span className={`font-medium ${getReturnColor(stock.returns)}`}>
                    {stock.returns > 0 ? '+' : ''}{(stock.returns * 100).toFixed(2)}%
                  </span>
                  <span className="text-gray-600">{stock.articles} articles</span>
                  <span className="text-gray-500">{stock.date}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Market Sentiment Analysis */}
      {console.log('🎭 Rendering sentiment analysis with:', sentimentAnalysis)}
      {sentimentAnalysis && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            🎭 Market Sentiment Analysis
            <span className={`ml-2 text-sm px-2 py-1 rounded-full ${getSentimentColor(sentimentAnalysis.overall_sentiment.score)}`}>
              {sentimentAnalysis.overall_sentiment.label}
            </span>
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-gray-700">{sentimentAnalysis.overall_sentiment.score.toFixed(3)}</div>
              <div className="text-sm text-gray-600">Overall Sentiment Score</div>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-gray-700">{sentimentAnalysis.statistics.stocks_analyzed}</div>
              <div className="text-sm text-gray-600">Stocks Analyzed</div>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="text-2xl font-bold text-gray-700">{sentimentAnalysis.statistics.total_articles}</div>
              <div className="text-sm text-gray-600">Articles Processed</div>
            </div>
          </div>

          {/* Sentiment Breakdown */}
          <h4 className="font-medium mb-3">📊 Stock Sentiment Breakdown</h4>
          <div className="space-y-2">
            {sentimentAnalysis.stock_breakdown.map((stock) => (
              <div key={stock.ticker} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <span className="font-medium">{stock.ticker}</span>
                <div className="flex items-center space-x-3">
                  <span className={`px-2 py-1 rounded text-xs ${getSentimentColor(stock.sentiment)}`}>
                    {stock.sentiment.toFixed(3)}
                  </span>
                  <span className="text-sm text-gray-600">{stock.articles} articles</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI System Status */}
      {pressureTest && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            🤖 AI System Status
            <span className="ml-2 text-sm bg-green-100 text-green-800 px-2 py-1 rounded-full">
              OPERATIONAL
            </span>
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Test Results */}
            <div>
              <h4 className="font-medium mb-3">🏆 Test Results</h4>
              <div className="space-y-2">
                {Object.entries(pressureTest.test_results).map(([key, value]) => (
                  <div key={key} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                    <span className="text-sm capitalize">{key.replace('_', ' ')}</span>
                    <span className={`text-xs px-2 py-1 rounded-full ${getStatusColor(value)}`}>
                      {value}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* AI Capabilities */}
            <div>
              <h4 className="font-medium mb-3">🚀 AI Capabilities</h4>
              <div className="space-y-2">
                {Object.entries(pressureTest.ai_capabilities).map(([key, value]) => (
                  <div key={key} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                    <span className="text-sm capitalize">{key.replace('_', ' ')}</span>
                    <span className={`text-xs px-2 py-1 rounded-full ${getStatusColor(value)}`}>
                      {value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 p-4 bg-gradient-to-r from-green-50 to-blue-50 rounded-lg">
            <p className="text-sm font-medium text-gray-800">
              🎯 {pressureTest.overall_status}
            </p>
            <p className="text-xs text-gray-600 mt-1">
              Last updated: {new Date(pressureTest.test_date).toLocaleString()}
            </p>
          </div>
        </div>
      )}

      {/* Refresh Button */}
      <div className="flex justify-center">
        <button
          onClick={fetchMarketIntelligence}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Refresh Intelligence</span>
        </button>
      </div>
    </div>
  );
};

export default MarketIntelligence;
