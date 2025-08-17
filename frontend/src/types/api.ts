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
