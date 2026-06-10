import axios, { AxiosResponse } from 'axios';
import {
  Stock,
  Article,
  DailyFeatures,
  FeaturesSummary,
  FeatureStats,
  PaginatedResponse,
  WSBTrendingResponse,
  AlertsResponse,
  MarketAnomaliesResponse,
  AllAnomaliesResponse,
  TickerAnomaliesResponse,
  PriceAnomaliesResponse,
  SentimentAnomaliesResponse,
  PatternAnomaliesResponse,
  IngestionStatusResponse,
  SentimentAnalysisResponse,
  MarketOverviewAnalysis,
  MarketSignalsOverview,
  TomorrowOutlookResponse,
  DailyRecommendationsResponse,
  PressureTestSummary,
  PriceHistoryResponse,
  PricePeriod,
  SignalsResponse,
  TickerSignalsResponse,
  SignalTypesResponse,
  AlertStatsResponse,
  TaskCatalogResponse,
  JobHistoryResponse,
  TriggerTaskResponse,
} from '../types/api';
import type { EnhancedFeaturesResponse } from '../types/api';

// API Client Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ---------------------------------------------------------------------------
// Auth interceptor — attaches Bearer token when available
// ---------------------------------------------------------------------------
let _accessTokenGetter: (() => string | null) | null = null;

/** Called by AuthProvider on mount to wire up the token source. */
export function setAccessTokenGetter(getter: () => string | null) {
  _accessTokenGetter = getter;
}

/**
 * Current OIDC access token (or null). The ONLY sanctioned way for API
 * clients to obtain the token — it reads the live react-oidc-context user
 * via the bridge, never browser storage (oidc-client-ts keeps the user in
 * sessionStorage, and renewed tokens only flow through the context).
 */
export function getAccessToken(): string | null {
  return _accessTokenGetter ? _accessTokenGetter() : null;
}

apiClient.interceptors.request.use((config) => {
  if (_accessTokenGetter) {
    const token = _accessTokenGetter();
    // H3: Only attach Bearer token for relative URLs (our own API)
    if (token && config.url && !config.url.startsWith('http')) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// ---------------------------------------------------------------------------
// Dev logging
// ---------------------------------------------------------------------------
if (import.meta.env.DEV) {
  apiClient.interceptors.request.use((config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  });

  apiClient.interceptors.response.use(
    (response) => {
      console.log(`API Response: ${response.status} ${response.config.url}`);
      return response;
    },
    (error) => {
      console.error(`API Error: ${error.response?.status} ${error.config?.url}`, error.response?.data);
      throw error;
    }
  );
}

// API Functions

// Types for stock knowledge and morning brief (not in shared types file)
export interface StockKnowledge {
  ticker: string;
  narrative: string | null;
  key_events: { events: Array<{ date: string; title: string; sentiment: number; url: string }> } | null;
  sentiment_trend: { weekly: Array<{ week: string; avg_sentiment: number; count: number }> } | null;
  article_count_processed: number;
  last_updated: string | null;
  created_at: string | null;
}

export interface MorningBriefStock {
  ticker: string;
  narrative: string | null;
  sentiment_current: number | null;
  sentiment_trend_direction: 'improving' | 'declining' | 'flat';
  recent_event_count: number;
  top_event: string | null;
  last_updated: string | null;
}

export interface MorningBriefResponse {
  generated_at: string;
  market_summary: string | null;
  stocks: MorningBriefStock[];
}

// Stocks API
export const stocksApi = {
  async getStocks(params?: {
    page?: number;
    page_size?: number;
    q?: string;
    sector?: string;
    exchange?: string;
  }): Promise<PaginatedResponse<Stock>> {
    const response: AxiosResponse<PaginatedResponse<Stock>> = await apiClient.get('/stocks/', { params });
    return response.data;
  },

  async getStock(symbol: string): Promise<Stock> {
    const response: AxiosResponse<Stock> = await apiClient.get(`/stocks/${symbol}`);
    return response.data;
  },

  async getStockKnowledge(symbol: string): Promise<StockKnowledge> {
    const response: AxiosResponse<StockKnowledge> = await apiClient.get(`/stocks/${symbol}/knowledge`);
    return response.data;
  },
};

// Prices API
export const pricesApi = {
  async getPriceHistory(ticker: string, period: PricePeriod = '1M'): Promise<PriceHistoryResponse> {
    const response: AxiosResponse<PriceHistoryResponse> = await apiClient.get(
      `/prices/${ticker}/history`,
      { params: { period } }
    );
    return response.data;
  },
};

// Features API
export const featuresApi = {
  async getDailyFeatures(ticker: string, date?: string): Promise<DailyFeatures> {
    const params = date ? { target_date: date } : {};
    const response: AxiosResponse<DailyFeatures> = await apiClient.get(`/features/daily/${ticker}`, { params });
    return response.data;
  },

  async getFeatureHistory(ticker: string, days: number = 30): Promise<{
    ticker: string;
    feature_version: string;
    start_date: string;
    end_date: string;
    count: number;
    features: DailyFeatures[];
  }> {
    const response = await apiClient.get(`/features/daily/${ticker}/history`, { 
      params: { days }
    });
    return response.data;
  },

  async getFeaturesSummary(date?: string, limit: number = 20): Promise<FeaturesSummary> {
    const params: any = { limit };
    if (date) params.target_date = date;
    
    const response: AxiosResponse<FeaturesSummary> = await apiClient.get('/features/summary', { params });
    return response.data;
  },

  async getFeatureStats(days: number = 7): Promise<FeatureStats> {
    const response: AxiosResponse<FeatureStats> = await apiClient.get('/features/stats', { 
      params: { days }
    });
    return response.data;
  },

  async calculateFeaturesImmediate(ticker: string, date?: string): Promise<{
    message: string;
    ticker: string;
    date: string;
    features: DailyFeatures;
  }> {
    const params = date ? { target_date: date } : {};
    const response = await apiClient.get(`/features/calculate/immediate/${ticker}`, { params });
    return response.data;
  },

  async getEnhancedFeatures(ticker: string): Promise<EnhancedFeaturesResponse> {
    const response: AxiosResponse<EnhancedFeaturesResponse> = await apiClient.get(`/features/${ticker}/enhanced`);
    return response.data;
  }
};

// Feed API
export const feedApi = {
  async getArticles(params?: {
    page?: number;
    page_size?: number;
    ticker?: string;
    days?: number;
  }): Promise<PaginatedResponse<Article>> {
    const response: AxiosResponse<PaginatedResponse<Article>> = await apiClient.get('/feed/', { params });
    return response.data;
  },

  async getWSBTrending(params?: { days?: number; limit?: number }): Promise<WSBTrendingResponse> {
    const response: AxiosResponse<WSBTrendingResponse> = await apiClient.get('/feed/wsb/trending', { params });
    return response.data;
  },

  async getIngestionStatus(): Promise<IngestionStatusResponse> {
    const response: AxiosResponse<IngestionStatusResponse> = await apiClient.get('/feed/ingest/status');
    return response.data;
  },
};

// Signals & Alerts API
export const signalsApi = {
  async getAlerts(params?: {
    ticker?: string;
    alert_type?: string;
    severity?: string;
    hours?: number;
    acknowledged?: boolean;
    limit?: number;
  }): Promise<AlertsResponse> {
    const response: AxiosResponse<AlertsResponse> = await apiClient.get('/signals/alerts', { params });
    return response.data;
  },

  async getMarketOverview(params?: { limit?: number }): Promise<MarketSignalsOverview> {
    const response: AxiosResponse<MarketSignalsOverview> = await apiClient.get('/signals/market/overview', { params });
    return response.data;
  },

  async getSignals(params?: {
    ticker?: string;
    signal_type?: string;
    direction?: string;
    min_strength?: number;
    min_confidence?: number;
    active_only?: boolean;
    limit?: number;
  }): Promise<SignalsResponse> {
    const response: AxiosResponse<SignalsResponse> = await apiClient.get('/signals/', { params });
    return response.data;
  },

  async getTickerSignals(ticker: string, params?: {
    active_only?: boolean;
    limit?: number;
  }): Promise<TickerSignalsResponse> {
    const response: AxiosResponse<TickerSignalsResponse> = await apiClient.get(`/signals/ticker/${ticker}`, { params });
    return response.data;
  },

  async getSignalTypes(): Promise<SignalTypesResponse> {
    const response: AxiosResponse<SignalTypesResponse> = await apiClient.get('/signals/types');
    return response.data;
  },

  async getAlertStats(days?: number): Promise<AlertStatsResponse> {
    const response: AxiosResponse<AlertStatsResponse> = await apiClient.get('/signals/alerts/stats', {
      params: days ? { days } : undefined,
    });
    return response.data;
  },

  async acknowledgeAlert(alertId: string): Promise<{ message: string; alert_id: string; acknowledged_at: string }> {
    const response = await apiClient.post(`/signals/alerts/${alertId}/acknowledge`);
    return response.data;
  },
};

// Anomalies API
export const anomaliesApi = {
  async getMarketAnomalies(params?: {
    lookback_days?: number;
    correlation_threshold?: number;
  }): Promise<MarketAnomaliesResponse> {
    const response: AxiosResponse<MarketAnomaliesResponse> = await apiClient.get('/anomalies/market', { params });
    return response.data;
  },

  async getAllAnomalies(params?: {
    ticker?: string;
    include_market_wide?: boolean;
    min_severity?: number;
    limit?: number;
  }): Promise<AllAnomaliesResponse> {
    const response: AxiosResponse<AllAnomaliesResponse> = await apiClient.get('/anomalies/', { params });
    return response.data;
  },

  async getTickerAnomalies(ticker: string, params?: {
    lookback_days?: number;
    z_threshold?: number;
  }): Promise<TickerAnomaliesResponse> {
    const response: AxiosResponse<TickerAnomaliesResponse> = await apiClient.get(`/anomalies/ticker/${ticker}`, { params });
    return response.data;
  },

  async getPriceAnomalies(ticker: string, params?: {
    lookback_days?: number;
    z_threshold?: number;
  }): Promise<PriceAnomaliesResponse> {
    const response: AxiosResponse<PriceAnomaliesResponse> = await apiClient.get(`/anomalies/price/${ticker}`, { params });
    return response.data;
  },

  async getSentimentAnomalies(ticker: string, params?: {
    lookback_days?: number;
    z_threshold?: number;
  }): Promise<SentimentAnomaliesResponse> {
    const response: AxiosResponse<SentimentAnomaliesResponse> = await apiClient.get(`/anomalies/sentiment/${ticker}`, { params });
    return response.data;
  },

  async getPatternAnomalies(ticker: string, params?: {
    lookback_days?: number;
  }): Promise<PatternAnomaliesResponse> {
    const response: AxiosResponse<PatternAnomaliesResponse> = await apiClient.get(`/anomalies/patterns/${ticker}`, { params });
    return response.data;
  },
};

// Market Analysis API
export const marketAnalysisApi = {
  async getMarketOverview(): Promise<MarketOverviewAnalysis> {
    const response: AxiosResponse<MarketOverviewAnalysis> = await apiClient.get('/market-analysis/market-overview');
    return response.data;
  },

  async getSentimentAnalysis(): Promise<SentimentAnalysisResponse> {
    const response: AxiosResponse<SentimentAnalysisResponse> = await apiClient.get('/market-analysis/sentiment-analysis');
    return response.data;
  },

  async getTomorrowOutlook(): Promise<TomorrowOutlookResponse> {
    const response: AxiosResponse<TomorrowOutlookResponse> = await apiClient.get('/market-analysis/tomorrow-outlook');
    return response.data;
  },

  async getPressureTestSummary(): Promise<PressureTestSummary> {
    const response: AxiosResponse<PressureTestSummary> = await apiClient.get('/market-analysis/pressure-test-summary');
    return response.data;
  },

  async getMorningBrief(): Promise<MorningBriefResponse> {
    const response: AxiosResponse<MorningBriefResponse> = await apiClient.get('/market-analysis/morning-brief');
    return response.data;
  },
};

// Recommendations API
export const recommendationsApi = {
  async getDailyRecommendations(params?: {
    date?: string;
    limit?: number;
  }): Promise<DailyRecommendationsResponse> {
    const response: AxiosResponse<DailyRecommendationsResponse> = await apiClient.get('/recommendations/daily', { params });
    return response.data;
  },
};

// Signal plugin SDK (admin)
export interface SignalSourceInfo {
  source_id: string;
  name: string;
  description: string;
  source_type: string;
  signal_types: string[];
  update_frequency_seconds: number;
  required_config: string[];
  enabled: boolean;
  state: {
    last_run_at: string | null;
    last_status: string | null;
    last_error: string | null;
    signals_emitted_total: number;
  } | null;
}

export interface SignalSourcesResponse {
  sources: SignalSourceInfo[];
  total: number;
}

// Admin API
export const adminApi = {
  async getTaskCatalog(): Promise<TaskCatalogResponse> {
    const response: AxiosResponse<TaskCatalogResponse> = await apiClient.get('/admin/task-catalog');
    return response.data;
  },

  async getSignalSources(): Promise<SignalSourcesResponse> {
    const response: AxiosResponse<SignalSourcesResponse> = await apiClient.get('/admin/signal-sources');
    return response.data;
  },

  async toggleSignalSource(sourceId: string): Promise<{ source_id: string; enabled: boolean }> {
    const response: AxiosResponse<{ source_id: string; enabled: boolean }> = await apiClient.post(
      `/admin/signal-sources/${sourceId}/toggle`
    );
    return response.data;
  },

  async triggerTask(jobName: string, params?: Record<string, unknown>): Promise<TriggerTaskResponse> {
    const response: AxiosResponse<TriggerTaskResponse> = await apiClient.post('/admin/reindex', {
      job_name: jobName,
      ...(params && Object.keys(params).length > 0 ? { params } : {}),
    });
    return response.data;
  },

  async getJobHistory(params?: {
    job_name?: string;
    status?: string;
    limit?: number;
  }): Promise<JobHistoryResponse> {
    const response: AxiosResponse<JobHistoryResponse> = await apiClient.get('/admin/jobs', { params });
    return response.data;
  },
};

// Auth API
export interface UserProfile {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  role: 'user' | 'admin';
  preferences: Record<string, any>;
  created_at: string | null;
  last_login_at: string | null;
}

export const authApi = {
  async getMe(): Promise<UserProfile> {
    const response: AxiosResponse<UserProfile> = await apiClient.get('/auth/me');
    return response.data;
  },

  async updateMe(data: { name?: string; preferences?: Record<string, any> }): Promise<UserProfile> {
    const response: AxiosResponse<UserProfile> = await apiClient.put('/auth/me', data);
    return response.data;
  },
};

// Watchlist API
export interface WatchlistItem {
  id: string;
  user_id: string;
  stock_id: string;
  notes: string | null;
  added_at: string | null;
  symbol: string | null;
  company_name: string | null;
}

export interface WatchlistResponse {
  watchlist: WatchlistItem[];
  count: number;
}

export const watchlistApi = {
  async getWatchlist(): Promise<WatchlistResponse> {
    const response: AxiosResponse<WatchlistResponse> = await apiClient.get('/users/me/watchlist');
    return response.data;
  },

  async addToWatchlist(symbol: string, notes?: string): Promise<WatchlistItem> {
    const response: AxiosResponse<WatchlistItem> = await apiClient.post('/users/me/watchlist', { symbol, notes });
    return response.data;
  },

  async removeFromWatchlist(symbol: string): Promise<{ removed: boolean; symbol: string }> {
    const response = await apiClient.delete(`/users/me/watchlist/${symbol}`);
    return response.data;
  },

  async updateNotes(symbol: string, notes: string | null): Promise<WatchlistItem> {
    const response: AxiosResponse<WatchlistItem> = await apiClient.patch(`/users/me/watchlist/${symbol}`, { notes });
    return response.data;
  },
};

// Utility functions
export const formatApiError = (error: any): string => {
  if (error.response?.data?.message) {
    return error.response.data.message;
  }
  if (error.response?.data?.detail) {
    return error.response.data.detail;
  }
  if (error.message) {
    return error.message;
  }
  return 'An unexpected error occurred';
};

export const isApiError = (error: any): boolean => {
  return error.response && error.response.status >= 400;
};

export default apiClient;
