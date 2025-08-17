import axios, { AxiosResponse } from 'axios';
import { 
  Stock, 
  Article, 
  DailyFeatures, 
  FeaturesSummary, 
  FeatureStats,
  PaginatedResponse 
} from '../types/api';
import type { EnhancedFeaturesResponse } from '../types/api';

// API Client Configuration
const API_BASE_URL = 'http://localhost:8080/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging in development
if (import.meta.env.DEV) {
  apiClient.interceptors.request.use((config) => {
    console.log(`🔄 API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  });

  apiClient.interceptors.response.use(
    (response) => {
      console.log(`✅ API Response: ${response.status} ${response.config.url}`);
      return response;
    },
    (error) => {
      console.error(`❌ API Error: ${error.response?.status} ${error.config?.url}`, error.response?.data);
      throw error;
    }
  );
}

// API Functions

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
  }
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
  }
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
