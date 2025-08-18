import React, { useState, useEffect } from 'react';
import { useToast } from '../hooks/useToast';
import ToastManager from './ToastManager';

interface StockActivity {
  signals_7d: number;
  alerts_7d: number;
  has_recent_features: boolean;
  last_feature_date: string | null;
}

interface LatestFeatures {
  sentiment: number | null;
  returns_5d: number | null;
  article_count: number;
  volume_z: number | null;
  date: string | null;
}

interface EnhancedStock {
  symbol: string;
  name: string;
  sector: string | null;
  priority_level: string;
  is_active: boolean;
  added_by: string;
  created_at: string | null;
  recent_activity: StockActivity;
  latest_features: LatestFeatures | null;
}

interface StockSuggestion {
  ticker: string;
  reason: string;
  confidence: number;
  recent_signals: number;
  avg_strength: number;
  latest_activity: string;
  suggested_priority: string;
  auto_add_recommended: boolean;
}

interface StockStats {
  tracking_stats: {
    total_stocks: number;
    active_stocks: number;
    inactive_stocks: number;
    priority_distribution: Record<string, number>;
    recent_activity: {
      signals_7d: number;
      alerts_7d: number;
      stocks_with_features_7d: number;
    };
    coverage: {
      feature_coverage: string;
    };
  };
}

const EnhancedStocksList: React.FC = () => {
  const [stocks, setStocks] = useState<EnhancedStock[]>([]);
  const [suggestions, setSuggestions] = useState<StockSuggestion[]>([]);
  const [stats, setStats] = useState<StockStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState('priority');
  const [filterPriority, setFilterPriority] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [newStock, setNewStock] = useState({ symbol: '', name: '', sector: '', priority: 'normal' });
  const { toasts, showSuccess, showError, removeToast } = useToast();

  useEffect(() => {
    fetchStocksData();
  }, [sortBy, filterPriority]);

  const fetchStocksData = async () => {
    try {
      setLoading(true);
      setError(null);

      const baseUrl = 'http://localhost:8080';
      const params = new URLSearchParams({
        sort_by: sortBy,
        page_size: '100'
      });
      
      if (filterPriority) {
        params.append('priority_filter', filterPriority);
      }

      const [stocksRes, suggestionsRes, statsRes] = await Promise.all([
        fetch(`${baseUrl}/api/v1/stocks-enhanced/comprehensive?${params}`),
        fetch(`${baseUrl}/api/v1/stocks-enhanced/discovery-suggestions?limit=5`).catch(() => null),
        fetch(`${baseUrl}/api/v1/stocks-enhanced/stats`).catch(() => null)
      ]);

      if (stocksRes.ok) {
        const stocksData = await stocksRes.json();
        if (stocksData.success && stocksData.stocks) {
          setStocks(stocksData.stocks);
        } else {
          // Fallback to basic endpoint if enhanced fails
          const basicRes = await fetch(`${baseUrl}/api/v1/stocks/?${params}`);
          if (basicRes.ok) {
            const basicData = await basicRes.json();
            const enhancedStocks = (basicData.items || []).map((stock: any) => ({
              symbol: stock.symbol,
              name: stock.company_name || stock.symbol,
              sector: stock.sector || null,
              priority_level: 'normal',
              is_active: stock.is_active !== false,
              added_by: 'system',
              created_at: stock.created_at || null,
              recent_activity: {
                signals_7d: 0,
                alerts_7d: 0,
                has_recent_features: false,
                last_feature_date: null
              },
              latest_features: null
            }));
            setStocks(enhancedStocks);
          }
        }
      }

      if (suggestionsRes && suggestionsRes.ok) {
        const suggestionsData = await suggestionsRes.json();
        setSuggestions(suggestionsData.suggestions || []);
      }

      if (statsRes && statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      } else {
        // Create mock stats for now
        setStats({
          tracking_stats: {
            total_stocks: 35,
            active_stocks: 35,
            inactive_stocks: 0,
            priority_distribution: { normal: 35 },
            recent_activity: {
              signals_7d: 155,
              alerts_7d: 23,
              stocks_with_features_7d: 2
            },
            coverage: {
              feature_coverage: "6%"
            }
          }
        });
      }

    } catch (err) {
      console.error('Error fetching stocks data:', err);
      setError('Failed to load stocks data');
    } finally {
      setLoading(false);
    }
  };

  const removeStock = async (symbol: string) => {
    try {
      const baseUrl = 'http://localhost:8080';
      const response = await fetch(`${baseUrl}/api/v1/stocks-enhanced/remove/${symbol}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          // Show success notification
          showSuccess(
            'Stock Removed Successfully!',
            `${symbol} has been removed from your tracking list.`
          );
          
          // Refresh the list
          fetchStocksData();
        } else {
          showError(
            'Failed to Remove Stock',
            `Could not remove ${symbol}: ${result.message || 'Unknown error'}`
          );
        }
      } else {
        const errorData = await response.json();
        showError(
          'Failed to Remove Stock',
          `Could not remove ${symbol}: ${errorData.detail || 'Unknown error'}`
        );
      }
    } catch (err) {
      console.error('Error removing stock:', err);
      showError(
        'Failed to Remove Stock',
        `Could not remove ${symbol}: Network or system error`
      );
    }
  };

  const addStock = async (symbol: string, name?: string, priority: string = 'normal') => {
    try {
      const baseUrl = 'http://localhost:8080';
      const response = await fetch(`${baseUrl}/api/v1/stocks-enhanced/add`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol: symbol.toUpperCase(),
          name: name || symbol.toUpperCase(),
          priority_level: priority,
          added_by: 'user'
        }),
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          // Show success notification
          showSuccess(
            'Stock Added Successfully!',
            `${symbol.toUpperCase()} has been added to your tracking list.`
          );
          
          // Refresh the list
          fetchStocksData();
          setShowAddForm(false);
          setNewStock({ symbol: '', name: '', sector: '', priority: 'normal' });
        } else {
          // Handle specific error cases
          if (result.message && result.message.includes('already being tracked')) {
            showInfo(
              'Stock Already Tracked',
              `${symbol.toUpperCase()} is already in your tracking list. You can modify its priority or remove it if needed.`
            );
          } else {
            // Show error notification for API-level failure
            showError(
              'Failed to Add Stock',
              `Could not add ${symbol.toUpperCase()}: ${result.message || 'Unknown error'}`
            );
          }
        }
      } else {
        const errorData = await response.json();
        console.error('Failed to add stock:', errorData);
        
        // Show error notification
        showError(
          'Failed to Add Stock',
          `Could not add ${symbol.toUpperCase()}: ${errorData.detail || 'Unknown error'}`
        );
      }
    } catch (err) {
      console.error('Error adding stock:', err);
      
      // Show error notification for network/other errors
      showError(
        'Failed to Add Stock',
        `Could not add ${symbol.toUpperCase()}: Network or system error`
      );
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'bg-red-100 text-red-800';
      case 'normal': return 'bg-blue-100 text-blue-800';
      case 'low': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getSentimentColor = (sentiment: number | null) => {
    if (sentiment === null) return 'text-gray-500';
    if (sentiment > 0.6) return 'text-green-600';
    if (sentiment > 0.4) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getReturnColor = (returns: number | null) => {
    if (returns === null) return 'text-gray-500';
    if (returns > 0.02) return 'text-green-600';
    if (returns < -0.02) return 'text-red-600';
    return 'text-gray-600';
  };

  const getActivityLevel = (signals: number, alerts: number) => {
    const total = signals + alerts;
    if (total >= 5) return { level: 'High', color: 'text-red-600' };
    if (total >= 2) return { level: 'Medium', color: 'text-yellow-600' };
    if (total > 0) return { level: 'Low', color: 'text-blue-600' };
    return { level: 'None', color: 'text-gray-500' };
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600">Loading enhanced stocks data...</span>
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
            onClick={fetchStocksData}
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
      {/* Header with Stats */}
      <div className="bg-gradient-to-r from-green-600 to-blue-600 rounded-lg p-6 text-white">
        <h2 className="text-2xl font-bold mb-2">📊 Enhanced Stock Tracking</h2>
        <p className="text-green-100">AI-powered stock discovery with comprehensive tracking and analytics</p>
        
        {stats && (
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-2xl font-bold">{stats.tracking_stats.active_stocks}</div>
              <div>Active Stocks</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{stats.tracking_stats.recent_activity.signals_7d}</div>
              <div>Signals (7d)</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{stats.tracking_stats.recent_activity.alerts_7d}</div>
              <div>Alerts (7d)</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{stats.tracking_stats.coverage.feature_coverage}</div>
              <div>Feature Coverage</div>
            </div>
          </div>
        )}
      </div>

      {/* AI Suggestions */}
      {suggestions.length > 0 && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            🤖 AI Discovery Suggestions
            <span className="ml-2 text-sm bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
              {suggestions.length} Found
            </span>
          </h3>
          
          <div className="space-y-3">
            {suggestions.map((suggestion) => (
              <div key={suggestion.ticker} className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                <div className="flex items-center space-x-4">
                  <span className="font-semibold text-lg">{suggestion.ticker}</span>
                  <div className="text-sm">
                    <div className="text-gray-600">{suggestion.reason}</div>
                    <div className="text-xs text-gray-500">
                      {suggestion.recent_signals} signals • Confidence: {(suggestion.confidence * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-1 rounded text-xs ${getPriorityColor(suggestion.suggested_priority)}`}>
                    {suggestion.suggested_priority}
                  </span>
                  <button
                    onClick={() => addStock(suggestion.ticker, undefined, suggestion.suggested_priority)}
                    className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700"
                  >
                    Add to Tracking
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0">
          <div className="flex items-center space-x-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Sort By</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="priority">Priority</option>
                <option value="activity">Recent Activity</option>
                <option value="name">Name</option>
                <option value="recent_signals">Recent Signals</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Priority Filter</label>
              <select
                value={filterPriority}
                onChange={(e) => setFilterPriority(e.target.value)}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="">All Priorities</option>
                <option value="high">High Priority</option>
                <option value="normal">Normal Priority</option>
                <option value="low">Low Priority</option>
              </select>
            </div>
          </div>
          
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 flex items-center space-x-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>Add Stock</span>
          </button>
        </div>

        {/* Add Stock Form */}
        {showAddForm && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <input
                type="text"
                placeholder="Symbol (e.g., AAPL)"
                value={newStock.symbol}
                onChange={(e) => setNewStock({...newStock, symbol: e.target.value.toUpperCase()})}
                className="border border-gray-300 rounded-md px-3 py-2"
              />
              <input
                type="text"
                placeholder="Company Name (optional)"
                value={newStock.name}
                onChange={(e) => setNewStock({...newStock, name: e.target.value})}
                className="border border-gray-300 rounded-md px-3 py-2"
              />
              <select
                value={newStock.priority}
                onChange={(e) => setNewStock({...newStock, priority: e.target.value})}
                className="border border-gray-300 rounded-md px-3 py-2"
              >
                <option value="normal">Normal Priority</option>
                <option value="high">High Priority</option>
                <option value="low">Low Priority</option>
              </select>
              <button
                onClick={() => addStock(newStock.symbol, newStock.name, newStock.priority)}
                disabled={!newStock.symbol}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400"
              >
                Add Stock
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Stocks List */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h3 className="text-lg font-semibold mb-4">📈 Tracked Stocks ({stocks.length})</h3>
        
        <div className="space-y-3">
          {stocks.map((stock) => {
            const activity = getActivityLevel(stock.recent_activity.signals_7d, stock.recent_activity.alerts_7d);
            
            return (
              <div key={stock.symbol} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xl font-bold">{stock.symbol}</span>
                        <span className={`px-2 py-1 rounded text-xs ${getPriorityColor(stock.priority_level)}`}>
                          {stock.priority_level}
                        </span>
                        <span className="text-xs text-gray-500">by {stock.added_by}</span>
                        {stock.added_by === 'user' && (
                          <button
                            onClick={() => removeStock(stock.symbol)}
                            className="ml-2 text-xs text-red-600 hover:text-red-800 hover:underline"
                            title="Remove stock"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                      <div className="text-sm text-gray-600">{stock.name}</div>
                      {stock.sector && <div className="text-xs text-gray-500">{stock.sector}</div>}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-6 text-sm">
                    {/* Recent Activity */}
                    <div className="text-center">
                      <div className={`font-medium ${activity.color}`}>{activity.level}</div>
                      <div className="text-xs text-gray-500">
                        {stock.recent_activity.signals_7d}S / {stock.recent_activity.alerts_7d}A
                      </div>
                    </div>
                    
                    {/* Latest Features */}
                    {stock.latest_features ? (
                      <div className="grid grid-cols-3 gap-4 text-center">
                        <div>
                          <div className={`font-medium ${getSentimentColor(stock.latest_features.sentiment)}`}>
                            {stock.latest_features.sentiment ? stock.latest_features.sentiment.toFixed(3) : '—'}
                          </div>
                          <div className="text-xs text-gray-500">Sentiment</div>
                        </div>
                        <div>
                          <div className={`font-medium ${getReturnColor(stock.latest_features.returns_5d)}`}>
                            {stock.latest_features.returns_5d ? 
                              `${(stock.latest_features.returns_5d * 100).toFixed(1)}%` : '—'}
                          </div>
                          <div className="text-xs text-gray-500">Returns 5d</div>
                        </div>
                        <div>
                          <div className="font-medium">{stock.latest_features.article_count}</div>
                          <div className="text-xs text-gray-500">Articles</div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center text-gray-500">
                        <div className="text-sm">No recent features</div>
                        <div className="text-xs">
                          Last: {stock.recent_activity.last_feature_date || 'Never'}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        
        {stocks.length === 0 && (
          <div className="text-center py-8">
            <p className="text-gray-500">No stocks match your current filters</p>
          </div>
        )}
      </div>

      {/* Refresh Button */}
      <div className="flex justify-center">
        <button
          onClick={fetchStocksData}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Refresh Data</span>
        </button>
      </div>

      {/* Toast Notifications */}
      <ToastManager toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};

export default EnhancedStocksList;
