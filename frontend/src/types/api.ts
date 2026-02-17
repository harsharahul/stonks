// API Type Definitions for Stonks Frontend
// Based on our FastAPI backend schemas

export interface Stock {
  id: string;
  symbol: string;
  company_name: string;
  sector: string | null;
  exchange: string | null;
  is_active: boolean;
}

export interface Article {
  id: string;
  source_id: string | null;
  url: string;
  title: string | null;
  author: string | null;
  published_at: string | null;
  raw_content: string | null;
  tickers: string[] | null;
  sentiment: number | null;
  language: string | null;
}

export interface DailyFeatures {
  ticker: string;
  date: string;
  feature_version: string;
  
  // Sentiment features
  sent_mean_3d: number | null;
  sent_mean_7d: number | null;
  sent_mean_10d: number | null;
  sent_shock: number | null;
  sent_volume_weighted: number | null;
  
  // Momentum features
  ret_1d: number | null;
  ret_5d: number | null;
  ret_20d: number | null;
  momentum_14d: number | null;
  vol_z: number | null;
  
  // Context features
  earnings_d: number | null;
  conflict_score: number | null;
  novelty_mean_3d: number | null;
  article_count_7d: number;
  
  // References
  top_doc_ids: string[];
  model_version: string | null;
  created_at: string;
}

export interface FeaturesSummary {
  date: string;
  feature_version: string;
  count: number;
  features: {
    ticker: string;
    sent_mean_7d: number | null;
    ret_5d: number | null;
    vol_z: number | null;
    novelty_mean_3d: number | null;
    conflict_score: number | null;
    article_count_7d: number;
  }[];
}

export interface FeatureStats {
  date_range: {
    start_date: string;
    end_date: string;
    days: number;
  };
  coverage: {
    total_feature_records: number;
    unique_tickers_with_features: number;
    total_active_tickers: number;
    coverage_rate: number;
  };
  latest: {
    latest_feature_date: string | null;
    latest_ticker: string | null;
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

// API Response wrappers
export interface ApiResponse<T> {
  data: T;
  status: 'success' | 'error';
  message?: string;
}

// Chart data interfaces
export interface ChartDataPoint {
  date: string;
  value: number;
  label?: string;
}

export interface SentimentTrend extends ChartDataPoint {
  article_count: number;
  shock?: number;
}

export interface PriceTrend extends ChartDataPoint {
  volume?: number;
  volatility?: number;
}

// Price History API Response Types
export interface PriceDataPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PriceSummary {
  current_price: number;
  previous_close: number;
  change: number;
  change_percent: number;
  period_high: number;
  period_low: number;
  avg_volume: number;
}

export interface PriceHistoryResponse {
  ticker: string;
  period: string;
  count: number;
  latest: (PriceDataPoint & { adjusted_close: number | null }) | null;
  summary: PriceSummary | null;
  prices: PriceDataPoint[];
}

export type PricePeriod = '1W' | '1M' | '3M' | '6M' | '1Y' | 'ALL';

// LLM Enhanced Analytics
export interface LlmEnhancement {
  ticker: string;
  timestamp: string | null;
  summary: {
    key_insights: string[];
    risk_level: 'low' | 'medium' | 'high' | string;
    recommendation_confidence: 'low' | 'medium' | 'high' | string;
  };
  analysis: {
    feature_quality: string;
    article_coverage: number;
    sentiment_trend: number | null;
    performance_trend: number | null;
  };
  llm_enhancements: {
    article_synthesis: string;
    recommendations: string;
    risk_factors: string[];
  };
}

export interface EnhancedFeaturesResponse {
  ticker: string;
  base_features: any; // keep flexible; UI primarily consumes llm_enhancement
  llm_enhancement: LlmEnhancement;
}

// WSB Trending types
export interface WSBTrendingTicker {
  ticker: string;
  mention_count: number;
  avg_sentiment: number;
  avg_reddit_score: number;
  avg_comments: number;
  trending_score: number;
}

export interface WSBTrendingResponse {
  trending_tickers: WSBTrendingTicker[];
  days: number;
  total_found: number;
  generated_at: string;
}

// Alert type (matches backend Alert.to_dict())
export interface Alert {
  id: string;
  user_id: string | null;
  ticker: string;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  triggered_at: string;
  acknowledged_at: string | null;
  signal_id: string | null;
  metadata: Record<string, any>;
  age_minutes: number;
}

export interface AlertsResponse {
  alerts: Alert[];
  count: number;
  filters: Record<string, any>;
}

// Signal type (matches backend Signal.to_dict())
export interface Signal {
  id: string;
  ticker: string;
  signal_type: string;
  strength: number;
  confidence: number;
  direction: 'bullish' | 'bearish' | 'neutral';
  timeframe: string;
  generated_at: string;
  expires_at: string | null;
  metadata: Record<string, any>;
  features_snapshot: Record<string, any>;
  model_version: string | null;
}

// Anomaly types
export interface Anomaly {
  ticker: string;
  anomaly_type: string;
  severity: number;
  z_score: number;
  current_value: number;
  expected_value: number;
  confidence: number;
  detected_at: string;
  metadata: Record<string, any>;
}

export interface MarketAnomaliesResponse {
  market_anomalies: Anomaly[];
  total_detected: number;
  parameters: { lookback_days: number; correlation_threshold: number };
  analysis_types: string[];
  generated_at: string;
}

export interface AllAnomaliesResponse {
  anomalies: Anomaly[];
  total_detected: number;
  filtered_count: number;
  filters: {
    ticker: string | null;
    include_market_wide: boolean;
    min_severity: number;
  };
  generated_at: string;
}

export interface TickerAnomaliesResponse {
  ticker: string;
  anomalies: Anomaly[];
  total_detected: number;
  parameters: { lookback_days: number; z_threshold: number };
  analysis_types: string[];
  generated_at: string;
}

export interface PriceAnomaliesResponse {
  ticker: string;
  price_anomalies: Anomaly[];
  parameters: { lookback_days: number; z_threshold: number };
  generated_at: string;
}

export interface SentimentAnomaliesResponse {
  ticker: string;
  sentiment_anomalies: Anomaly[];
  parameters: { lookback_days: number; z_threshold: number };
  generated_at: string;
}

export interface PatternAnomaliesResponse {
  ticker: string;
  pattern_anomalies: Anomaly[];
  parameters: { lookback_days: number };
  analysis_types: string[];
  generated_at: string;
}

// Ingestion Status types
export interface IngestionSource {
  name: string;
  status: 'operational' | 'degraded' | 'down';
  last_update: string | null;
  article_count: number;
  freshness_minutes: number | null;
  source_type: string;
}

export interface IngestionStatusResponse {
  system_health: string;
  operational_sources: number;
  total_sources: number;
  sources: IngestionSource[];
  generated_at: string;
}

// Market Analysis types
export interface SentimentAnalysisResponse {
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

export interface MarketOverviewAnalysis {
  success: boolean;
  analysis_date: string;
  system_health: {
    stocks_tracked: number;
    active_signals: number;
    active_alerts: number;
    status: string;
  };
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

// Tomorrow's Outlook
export interface TomorrowOutlookResponse {
  success: boolean;
  outlook_date: string;
  generated_at: string;
  system_status: {
    stocks_tracked: number;
    active_signals: number;
    active_alerts: number;
  };
  market_sentiment: {
    score: number;
    label: string;
    color: string;
  };
  alerts: {
    total: number;
    high_priority: number;
    recent_alerts: Array<{
      ticker: string;
      type: string;
      severity: string;
      message: string;
      triggered_at: string | null;
    }>;
  };
  recommendation: {
    text: string;
    confidence: string;
    key_factors: string[];
  };
}

// Daily Recommendations
export interface Recommendation {
  symbol: string;
  score: number;
  action: 'buy' | 'sell' | 'hold';
  rationale: {
    top_signals: Array<{ signal: string; contribution: number }>;
    evidence: Record<string, any>;
    notes: string;
  };
  model_version: string;
}

export interface DailyRecommendationsResponse {
  date: string;
  recommendations: Recommendation[];
  total: number;
  model_version: string;
}

// Pressure Test Summary
export interface PressureTestSummary {
  success: boolean;
  test_date: string;
  test_results: Record<string, string>;
  performance_metrics: Record<string, number>;
  ai_capabilities: Record<string, string>;
  overall_status: string;
  next_update: string;
}

// Market Signals Overview
export interface MarketSignalsOverview {
  market_overview: {
    top_signals: Signal[];
    recent_alerts: Alert[];
    alert_stats: Record<string, any>;
    generated_at: string;
  };
}

// Signals Explorer response types
export interface SignalsResponse {
  signals: Signal[];
  count: number;
  filters: Record<string, any>;
}

export interface TickerSignalsResponse {
  ticker: string;
  summary: {
    signal_count: number;
    bullish_signals: number;
    bearish_signals: number;
    neutral_signals: number;
    max_strength: number;
    avg_confidence: number;
  };
  signals: Signal[];
}

export interface SignalTypesResponse {
  signal_types: Record<string, {
    description: string;
    timeframe: string;
    expires_hours: number;
    min_confidence: number;
  }>;
  count: number;
}

export interface AlertStatsResponse {
  period_days: number;
  total_alerts: number;
  acknowledgment_rate: number;
  severity_breakdown: Record<string, number>;
  top_alert_types: Array<{ type: string; count: number }>;
  unacknowledged_count: number;
}

// Admin types
export interface TaskCatalogEntry {
  task: string;
  queue: string;
  description: string;
  schedule: string;
}

export interface TaskCatalogResponse {
  tasks: Record<string, TaskCatalogEntry>;
}

export interface ETLJobRun {
  id: string;
  job_name: string;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  items_processed: number | null;
  details: Record<string, any> | null;
}

export interface JobHistoryResponse {
  jobs: ETLJobRun[];
  total: number;
}

export interface TriggerTaskResponse {
  enqueued: boolean;
  job_id: string;
  job_name: string;
  celery_task_id: string;
  queue: string;
  message: string;
}
