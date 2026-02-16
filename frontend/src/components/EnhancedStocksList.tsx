import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { TrendingUp, Plus, RefreshCw, AlertCircle, Brain, Search, X, Star, ChevronUp, ChevronDown, BarChart3 } from 'lucide-react';
import { useToast } from '../hooks/useToast';
import ToastManager from './ToastManager';
import ScreenerFiltersPanel from './ScreenerFilters';
import StockComparisonDrawer, { ComparisonStock } from './StockComparisonDrawer';
import { stocksApi } from '../api/client';
import { useSentimentAnalysis } from '../hooks/useWSBDashboard';
import { ScreenerFilters, DEFAULT_SCREENER_FILTERS, passesScreenerFilters, isScreenerActive } from '../hooks/useStockScreener';
import { cn, formatNumber, formatPercent, getSentimentColor, getReturnColor } from '../utils/format';

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

// Search result from stocksApi
interface SearchResult {
  symbol: string;
  company_name?: string;
}

type SortColumn = 'symbol' | 'name' | 'priority' | 'sentiment' | 'returns_5d' | 'volume_z' | 'articles' | 'activity';
type SortDirection = 'asc' | 'desc';

const ThSortable: React.FC<{
  col: SortColumn;
  label: string;
  sortColumn: SortColumn;
  sortDirection: SortDirection;
  onSort: (col: SortColumn) => void;
  className?: string;
}> = ({ col, label, sortColumn, sortDirection, onSort, className }) => (
  <th
    className={cn(
      'px-3 py-2 text-left text-xs font-medium text-neutral-400 uppercase tracking-wider cursor-pointer select-none hover:text-neutral-200 transition-colors',
      className
    )}
    onClick={() => onSort(col)}
  >
    <span className="inline-flex items-center gap-1">
      {label}
      {sortColumn === col && (
        sortDirection === 'asc'
          ? <ChevronUp className="w-3 h-3" />
          : <ChevronDown className="w-3 h-3" />
      )}
    </span>
  </th>
);

const EnhancedStocksList: React.FC = () => {
  const [stocks, setStocks] = useState<EnhancedStock[]>([]);
  const [suggestions, setSuggestions] = useState<StockSuggestion[]>([]);
  const [stats, setStats] = useState<StockStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortColumn, setSortColumn] = useState<SortColumn>('symbol');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [filterPriority, setFilterPriority] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Screener & comparison state
  const [screenerFilters, setScreenerFilters] = useState<ScreenerFilters>({ ...DEFAULT_SCREENER_FILTERS });
  const [selectedSymbols, setSelectedSymbols] = useState<Set<string>>(new Set());
  const { data: sentimentData, isLoading: sentimentLoading } = useSentimentAnalysis();

  // Quick Add state
  const [quickAddQuery, setQuickAddQuery] = useState('');
  const [quickAddResults, setQuickAddResults] = useState<SearchResult[]>([]);
  const [quickAddLoading, setQuickAddLoading] = useState(false);

  const { toasts, showSuccess, showError: showErrorToast, showInfo, removeToast } = useToast();

  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';

  useEffect(() => {
    fetchStocksData();
  }, []);

  // Quick Add search with debounce
  useEffect(() => {
    if (!quickAddQuery || quickAddQuery.length < 1) {
      setQuickAddResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        setQuickAddLoading(true);
        const data = await stocksApi.getStocks({ q: quickAddQuery.toUpperCase(), page_size: 8 });
        setQuickAddResults(
          (data.items || []).map((s: any) => ({
            symbol: s.symbol,
            company_name: s.company_name || s.name || s.symbol,
          }))
        );
      } catch {
        setQuickAddResults([]);
      } finally {
        setQuickAddLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [quickAddQuery]);

  const fetchStocksData = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({ sort_by: 'priority', page_size: '100' });

      const [stocksRes, suggestionsRes, statsRes] = await Promise.all([
        fetch(`${baseUrl}/stocks-enhanced/comprehensive?${params}`),
        fetch(`${baseUrl}/stocks-enhanced/discovery-suggestions?limit=5`).catch(() => null),
        fetch(`${baseUrl}/stocks-enhanced/stats`).catch(() => null),
      ]);

      if (stocksRes.ok) {
        const stocksData = await stocksRes.json();
        if (stocksData.success && stocksData.stocks) {
          setStocks(stocksData.stocks);
        }
      }

      if (suggestionsRes && suggestionsRes.ok) {
        const suggestionsData = await suggestionsRes.json();
        setSuggestions(suggestionsData.suggestions || []);
      }

      if (statsRes && statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
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
      const response = await fetch(`${baseUrl}/stocks-enhanced/remove/${symbol}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      });
      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          showSuccess('Stock Removed', `${symbol} removed from tracking.`);
          fetchStocksData();
        } else {
          showErrorToast('Remove Failed', result.message || 'Unknown error');
        }
      } else {
        const errorData = await response.json();
        showErrorToast('Remove Failed', errorData.detail || 'Unknown error');
      }
    } catch {
      showErrorToast('Remove Failed', `Could not remove ${symbol}`);
    }
  };

  const addStock = async (symbol: string, name?: string, priority: string = 'normal') => {
    try {
      const response = await fetch(`${baseUrl}/stocks-enhanced/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: symbol.toUpperCase(),
          name: name || symbol.toUpperCase(),
          priority_level: priority,
          added_by: 'user',
        }),
      });
      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          showSuccess('Stock Added', `${symbol.toUpperCase()} added to tracking.`);
          fetchStocksData();
          setQuickAddQuery('');
          setQuickAddResults([]);
        } else if (result.message?.includes('already being tracked')) {
          showInfo('Already Tracked', `${symbol.toUpperCase()} is already in your list.`);
        } else {
          showErrorToast('Add Failed', result.message || 'Unknown error');
        }
      } else {
        const errorData = await response.json();
        showErrorToast('Add Failed', errorData.detail || 'Unknown error');
      }
    } catch {
      showErrorToast('Add Failed', `Could not add ${symbol.toUpperCase()}`);
    }
  };

  const handleSort = (col: SortColumn) => {
    if (sortColumn === col) {
      setSortDirection(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortColumn(col);
      setSortDirection('asc');
    }
  };

  const getActivityLevel = (signals: number, alerts: number) => {
    const total = signals + alerts;
    if (total >= 5) return { level: 'High', color: 'text-red-700 bg-red-50' };
    if (total >= 2) return { level: 'Med', color: 'text-amber-700 bg-amber-50' };
    if (total > 0) return { level: 'Low', color: 'text-blue-700 bg-blue-50' };
    return { level: '—', color: 'text-neutral-500 bg-neutral-100' };
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'high': return 'text-red-700 bg-red-50 border-red-200';
      case 'normal': return 'text-neutral-600 bg-neutral-100 border-neutral-200';
      case 'low': return 'text-neutral-500 bg-neutral-50 border-neutral-200';
      default: return 'text-neutral-500 bg-neutral-50 border-neutral-200';
    }
  };

  // Compute average sentiment from stocks
  const avgSentiment = useMemo(() => {
    const vals = stocks
      .map(s => s.latest_features?.sentiment)
      .filter((v): v is number => v !== null && v !== undefined);
    return vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  }, [stocks]);

  // Filter and sort stocks
  const filteredStocks = useMemo(() => {
    let result = [...stocks];

    // Priority filter
    if (filterPriority) {
      result = result.filter(s => s.priority_level === filterPriority);
    }

    // Search filter
    if (searchQuery) {
      const q = searchQuery.toUpperCase();
      result = result.filter(
        s => s.symbol.includes(q) || s.name.toUpperCase().includes(q)
      );
    }

    // Screener filters
    if (isScreenerActive(screenerFilters)) {
      result = result.filter(s => {
        const act = getActivityLevel(s.recent_activity.signals_7d, s.recent_activity.alerts_7d);
        return passesScreenerFilters(s, screenerFilters, act.level);
      });
    }

    // Sort
    result.sort((a, b) => {
      const dir = sortDirection === 'asc' ? 1 : -1;
      switch (sortColumn) {
        case 'symbol': return dir * a.symbol.localeCompare(b.symbol);
        case 'name': return dir * a.name.localeCompare(b.name);
        case 'priority': {
          const order: Record<string, number> = { high: 0, normal: 1, low: 2 };
          return dir * ((order[a.priority_level] ?? 3) - (order[b.priority_level] ?? 3));
        }
        case 'sentiment': {
          const aVal = a.latest_features?.sentiment ?? -999;
          const bVal = b.latest_features?.sentiment ?? -999;
          return dir * (aVal - bVal);
        }
        case 'returns_5d': {
          const aVal = a.latest_features?.returns_5d ?? -999;
          const bVal = b.latest_features?.returns_5d ?? -999;
          return dir * (aVal - bVal);
        }
        case 'volume_z': {
          const aVal = a.latest_features?.volume_z ?? -999;
          const bVal = b.latest_features?.volume_z ?? -999;
          return dir * (aVal - bVal);
        }
        case 'articles': {
          const aVal = a.latest_features?.article_count ?? 0;
          const bVal = b.latest_features?.article_count ?? 0;
          return dir * (aVal - bVal);
        }
        case 'activity': {
          const aVal = (a.recent_activity.signals_7d + a.recent_activity.alerts_7d);
          const bVal = (b.recent_activity.signals_7d + b.recent_activity.alerts_7d);
          return dir * (aVal - bVal);
        }
        default: return 0;
      }
    });

    return result;
  }, [stocks, filterPriority, searchQuery, sortColumn, sortDirection, screenerFilters]);

  // Track which symbols are already tracked (for Quick Add)
  const trackedSymbols = useMemo(() => new Set(stocks.map(s => s.symbol)), [stocks]);

  // Comparison helpers
  const toggleSelection = (symbol: string) => {
    setSelectedSymbols(prev => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  };

  const clearSelection = () => setSelectedSymbols(new Set());

  const allFilteredSelected = filteredStocks.length > 0 && filteredStocks.every(s => selectedSymbols.has(s.symbol));

  const toggleSelectAll = () => {
    if (allFilteredSelected) {
      clearSelection();
    } else {
      setSelectedSymbols(new Set(filteredStocks.map(s => s.symbol)));
    }
  };

  const comparisonStocks: ComparisonStock[] = useMemo(
    () => stocks
      .filter(s => selectedSymbols.has(s.symbol))
      .map(s => ({
        symbol: s.symbol,
        name: s.name,
        sentiment: s.latest_features?.sentiment ?? null,
        returns_5d: s.latest_features?.returns_5d ?? null,
        volume_z: s.latest_features?.volume_z ?? null,
        article_count: s.latest_features?.article_count ?? 0,
        signals_7d: s.recent_activity.signals_7d,
        alerts_7d: s.recent_activity.alerts_7d,
      })),
    [stocks, selectedSymbols],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        <span className="ml-3 text-neutral-400">Loading watchlist...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto mt-12 bg-red-50 border border-red-200 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 shrink-0" />
          <div>
            <h3 className="text-sm font-medium text-red-800">Error Loading Data</h3>
            <p className="mt-1 text-sm text-red-600">{error}</p>
          </div>
        </div>
        <button
          onClick={fetchStocksData}
          className="mt-4 bg-red-600 text-white px-4 py-2 rounded-md text-sm hover:bg-red-700 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-6 space-y-6">
      {/* Dark Header with KPI Strip */}
      <div className="bg-neutral-900 rounded-xl p-6 border border-neutral-800">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <TrendingUp className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Stock Watchlist</h1>
              <p className="text-sm text-neutral-400">
                {stocks.length} tracked stocks
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchStocksData}
              className="px-3 py-2 text-sm bg-neutral-800 text-neutral-300 rounded-lg hover:bg-neutral-700 border border-neutral-700 transition-colors inline-flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-neutral-800/60 rounded-lg p-3 border border-neutral-700/50">
            <div className="text-xs text-neutral-400 mb-1">Tracked</div>
            <div className="text-2xl font-bold text-white">
              {stats?.tracking_stats.active_stocks ?? stocks.length}
            </div>
          </div>
          <div className="bg-neutral-800/60 rounded-lg p-3 border border-neutral-700/50">
            <div className="text-xs text-neutral-400 mb-1">Avg Sentiment</div>
            <div className={cn('text-2xl font-bold', avgSentiment !== null ? getSentimentColor(avgSentiment) : 'text-neutral-500')}>
              {avgSentiment !== null ? formatNumber(avgSentiment, 3) : '—'}
            </div>
          </div>
          <div className="bg-neutral-800/60 rounded-lg p-3 border border-neutral-700/50">
            <div className="text-xs text-neutral-400 mb-1">Signals (7d)</div>
            <div className="text-2xl font-bold text-white">
              {stats?.tracking_stats.recent_activity.signals_7d ?? 0}
            </div>
          </div>
          <div className="bg-neutral-800/60 rounded-lg p-3 border border-neutral-700/50">
            <div className="text-xs text-neutral-400 mb-1">Coverage</div>
            <div className="text-2xl font-bold text-white">
              {stats?.tracking_stats.coverage.feature_coverage ?? '—'}
            </div>
          </div>
        </div>
      </div>

      {/* Market Sentiment Strip */}
      {(sentimentLoading || sentimentData) && (
        <div className={cn(
          'rounded-xl px-4 py-3 border',
          sentimentLoading ? 'bg-neutral-50 border-neutral-200' :
          sentimentData?.overall_sentiment.label === 'BULLISH' ? 'bg-emerald-50 border-emerald-200' :
          sentimentData?.overall_sentiment.label === 'BEARISH' ? 'bg-red-50 border-red-200' :
          'bg-amber-50 border-amber-200'
        )}>
          {sentimentLoading ? (
            <div className="flex items-center gap-3">
              <div className="h-4 w-20 bg-neutral-200 rounded animate-pulse" />
              <div className="h-3 w-32 bg-neutral-200 rounded animate-pulse" />
            </div>
          ) : sentimentData ? (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              <span className={cn(
                'font-bold text-sm',
                sentimentData.overall_sentiment.label === 'BULLISH' ? 'text-emerald-700' :
                sentimentData.overall_sentiment.label === 'BEARISH' ? 'text-red-700' :
                'text-amber-700'
              )}>
                {sentimentData.overall_sentiment.label}
              </span>
              <span className="text-neutral-600">
                Score: <span className="font-mono font-medium">{formatNumber(sentimentData.overall_sentiment.score, 3)}</span>
              </span>
              <span className="text-neutral-500">
                {sentimentData.overall_sentiment.confidence} confidence
              </span>
              <span className="text-neutral-400 hidden sm:inline">|</span>
              <span className="text-neutral-500">
                {sentimentData.statistics.stocks_analyzed} stocks analyzed
              </span>
              <span className="text-neutral-500">
                {sentimentData.statistics.total_articles} articles
              </span>
            </div>
          ) : null}
        </div>
      )}

      {/* Screener Filters */}
      <ScreenerFiltersPanel
        filters={screenerFilters}
        onChange={setScreenerFilters}
        filteredCount={filteredStocks.length}
        totalCount={stocks.length}
      />

      {/* Control Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
            className="bg-white border border-neutral-200 rounded-lg px-3 py-2 text-sm text-neutral-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">All Priorities</option>
            <option value="high">High</option>
            <option value="normal">Normal</option>
            <option value="low">Low</option>
          </select>
        </div>
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
          <input
            type="text"
            placeholder="Search ticker or name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-8 py-2 bg-white border border-neutral-200 rounded-lg text-sm text-neutral-700 placeholder:text-neutral-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="text-sm text-neutral-500">
          {filteredStocks.length} of {stocks.length} stocks
        </div>
        {selectedSymbols.size >= 2 && (
          <button
            onClick={() => {
              const el = document.getElementById('comparison-drawer');
              el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            <BarChart3 className="w-3.5 h-3.5" />
            Compare ({selectedSymbols.size})
          </button>
        )}
        {selectedSymbols.size > 0 && (
          <button
            onClick={clearSelection}
            className="text-xs text-neutral-500 hover:text-neutral-700 transition-colors"
          >
            Clear selection
          </button>
        )}
      </div>

      {/* Main Content: Table + Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Stock Table */}
        <div className="lg:col-span-8 bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ minWidth: '700px' }}>
              <thead>
                <tr className="bg-neutral-900 text-left">
                  <th className="px-2 py-2 w-8">
                    <input
                      type="checkbox"
                      checked={allFilteredSelected && filteredStocks.length > 0}
                      onChange={toggleSelectAll}
                      className="w-3.5 h-3.5 rounded border-neutral-500 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                  </th>
                  <ThSortable col="symbol" label="Ticker" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                  <ThSortable col="name" label="Company" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} className="hidden md:table-cell" />
                  <ThSortable col="priority" label="Priority" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                  <ThSortable col="sentiment" label="Sentiment" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                  <ThSortable col="returns_5d" label="5d Ret" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} />
                  <ThSortable col="volume_z" label="Vol Z" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} className="hidden sm:table-cell" />
                  <ThSortable col="articles" label="Articles" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} className="hidden sm:table-cell" />
                  <ThSortable col="activity" label="Activity" sortColumn={sortColumn} sortDirection={sortDirection} onSort={handleSort} className="hidden md:table-cell" />
                  <th className="px-3 py-2 w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {filteredStocks.map((stock) => {
                  const activity = getActivityLevel(stock.recent_activity.signals_7d, stock.recent_activity.alerts_7d);
                  const sentiment = stock.latest_features?.sentiment ?? null;
                  const ret5d = stock.latest_features?.returns_5d ?? null;
                  const volZ = stock.latest_features?.volume_z ?? null;
                  const articles = stock.latest_features?.article_count ?? 0;

                  const isSelected = selectedSymbols.has(stock.symbol);

                  return (
                    <tr key={stock.symbol} className={cn('hover:bg-neutral-50 transition-colors group', isSelected && 'bg-blue-50/50')}>
                      <td className="px-2 py-2.5">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelection(stock.symbol)}
                          className="w-3.5 h-3.5 rounded border-neutral-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                        />
                      </td>
                      <td className="px-3 py-2.5">
                        <Link
                          to={`/stocks/${stock.symbol}`}
                          className="font-semibold text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          {stock.symbol}
                        </Link>
                      </td>
                      <td className="px-3 py-2.5 text-neutral-600 hidden md:table-cell">
                        <span className="truncate block max-w-[180px]">{stock.name}</span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={cn(
                          'px-2 py-0.5 rounded text-xs font-medium border',
                          getPriorityBadge(stock.priority_level)
                        )}>
                          {stock.priority_level}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        {sentiment !== null ? (
                          <div className="flex items-center gap-2">
                            <div className="w-12 bg-neutral-200 rounded-full h-1.5">
                              <div
                                className={cn(
                                  'h-1.5 rounded-full',
                                  sentiment > 0.6 ? 'bg-emerald-500' : sentiment > 0.4 ? 'bg-yellow-500' : 'bg-red-500'
                                )}
                                style={{ width: `${Math.min(sentiment * 100, 100)}%` }}
                              />
                            </div>
                            <span className={cn('text-xs font-medium', getSentimentColor(sentiment))}>
                              {formatNumber(sentiment, 3)}
                            </span>
                          </div>
                        ) : (
                          <span className="text-neutral-400 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={cn('text-xs font-medium', getReturnColor(ret5d))}>
                          {ret5d !== null ? formatPercent(ret5d, 1) : '—'}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-neutral-700 text-xs hidden sm:table-cell">
                        {volZ !== null ? formatNumber(volZ, 2) : '—'}
                      </td>
                      <td className="px-3 py-2.5 text-neutral-700 text-xs hidden sm:table-cell">
                        {articles}
                      </td>
                      <td className="px-3 py-2.5 hidden md:table-cell">
                        <span className={cn('px-2 py-0.5 rounded text-xs font-medium', activity.color)}>
                          {activity.level}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <button
                          onClick={() => removeStock(stock.symbol)}
                          className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-red-500 transition-all"
                          title={`Remove ${stock.symbol}`}
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Empty state */}
          {filteredStocks.length === 0 && (
            <div className="text-center py-12 px-6">
              <Star className="w-10 h-10 text-neutral-300 mx-auto mb-3" />
              <h3 className="text-sm font-medium text-neutral-900 mb-1">
                {searchQuery || filterPriority ? 'No stocks match your filters' : 'Start building your watchlist'}
              </h3>
              <p className="text-xs text-neutral-500">
                {searchQuery || filterPriority
                  ? 'Try adjusting your search or filter.'
                  : 'Use Quick Add to search and add stocks to track.'}
              </p>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-4 space-y-6">
          {/* Quick Add Panel */}
          <div className="bg-white rounded-xl border border-neutral-200 shadow-sm p-4">
            <h3 className="text-sm font-semibold text-neutral-900 mb-3 flex items-center gap-2">
              <Plus className="w-4 h-4 text-emerald-600" />
              Quick Add
            </h3>
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
              <input
                type="text"
                placeholder="Search by ticker..."
                value={quickAddQuery}
                onChange={(e) => setQuickAddQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-neutral-50 border border-neutral-200 rounded-lg text-sm placeholder:text-neutral-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {quickAddLoading && (
              <div className="text-xs text-neutral-400 py-2">Searching...</div>
            )}

            {quickAddResults.length > 0 && (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {quickAddResults.map((r) => {
                  const isTracked = trackedSymbols.has(r.symbol);
                  return (
                    <div
                      key={r.symbol}
                      className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-neutral-50 transition-colors"
                    >
                      <div className="min-w-0">
                        <span className="font-semibold text-sm text-neutral-900">{r.symbol}</span>
                        <span className="text-xs text-neutral-500 ml-2 truncate">
                          {r.company_name}
                        </span>
                      </div>
                      {isTracked ? (
                        <span className="text-xs text-emerald-600 font-medium shrink-0">Tracked</span>
                      ) : (
                        <button
                          onClick={() => addStock(r.symbol, r.company_name)}
                          className="text-xs bg-blue-600 text-white px-2.5 py-1 rounded hover:bg-blue-700 transition-colors shrink-0"
                        >
                          + Add
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {quickAddQuery && !quickAddLoading && quickAddResults.length === 0 && (
              <div className="text-xs text-neutral-400 py-2">
                No results for "{quickAddQuery}". You can add it manually:
                <button
                  onClick={() => addStock(quickAddQuery)}
                  className="ml-1 text-blue-600 hover:underline font-medium"
                >
                  Add {quickAddQuery.toUpperCase()}
                </button>
              </div>
            )}
          </div>

          {/* AI Suggestions Panel */}
          {suggestions.length > 0 && (
            <div className="bg-white rounded-xl border border-neutral-200 shadow-sm p-4">
              <h3 className="text-sm font-semibold text-neutral-900 mb-3 flex items-center gap-2">
                <Brain className="w-4 h-4 text-purple-600" />
                AI Suggestions
                <span className="ml-auto text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">
                  {suggestions.length}
                </span>
              </h3>
              <div className="space-y-2">
                {suggestions.map((s) => (
                  <div
                    key={s.ticker}
                    className="flex items-center justify-between py-2 px-2 bg-neutral-50 rounded-lg"
                  >
                    <div className="min-w-0">
                      <div className="font-semibold text-sm text-neutral-900">{s.ticker}</div>
                      <div className="text-xs text-neutral-500 truncate">{s.reason}</div>
                      <div className="text-xs text-neutral-400">
                        {s.recent_signals} signals &middot; {(s.confidence * 100).toFixed(0)}% conf
                      </div>
                    </div>
                    <button
                      onClick={() => addStock(s.ticker, undefined, s.suggested_priority)}
                      className="text-xs bg-purple-600 text-white px-2.5 py-1 rounded hover:bg-purple-700 transition-colors shrink-0 ml-2"
                    >
                      + Add
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Stock Comparison Drawer */}
      {comparisonStocks.length >= 2 && (
        <div id="comparison-drawer">
          <StockComparisonDrawer
            stocks={comparisonStocks}
            onRemove={(symbol) => toggleSelection(symbol)}
            onClose={clearSelection}
          />
        </div>
      )}

      <ToastManager toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};

export default EnhancedStocksList;
