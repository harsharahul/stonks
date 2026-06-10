import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { featuresApi, formatApiError } from '../api/client';
import type { EnhancedFeaturesResponse } from '../types/api';
import { DailyFeatures, FeaturesSummary, FeatureStats } from '../types/api';

// Query key factory for features
export const featuresKeys = {
  all: ['features'] as const,
  daily: (ticker: string, date?: string) => ['features', 'daily', ticker, date] as const,
  history: (ticker: string, days: number) => ['features', 'history', ticker, days] as const,
  summary: (date?: string, limit?: number) => ['features', 'summary', date, limit] as const,
  stats: (days: number) => ['features', 'stats', days] as const,
  enhanced: (ticker: string) => ['features', 'enhanced', ticker] as const,
};

// Hook for getting daily features for a specific ticker
export const useDailyFeatures = (ticker: string, date?: string) => {
  return useQuery({
    queryKey: featuresKeys.daily(ticker, date),
    queryFn: () => featuresApi.getDailyFeatures(ticker, date),
    enabled: !!ticker,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
    onError: (error) => {
      console.error(`Error fetching features for ${ticker}:`, formatApiError(error));
    }
  });
};

// Hook for getting feature history for a ticker
export const useFeatureHistory = (ticker: string, days: number = 30) => {
  return useQuery({
    queryKey: featuresKeys.history(ticker, days),
    queryFn: () => featuresApi.getFeatureHistory(ticker, days),
    enabled: !!ticker,
    staleTime: 10 * 60 * 1000, // 10 minutes
    retry: 2,
    onError: (error) => {
      console.error(`Error fetching feature history for ${ticker}:`, formatApiError(error));
    }
  });
};

// Hook for getting features summary across all tickers
export const useFeaturesSummary = (date?: string, limit: number = 20) => {
  return useQuery({
    queryKey: featuresKeys.summary(date, limit),
    queryFn: () => featuresApi.getFeaturesSummary(date, limit),
    staleTime: 2 * 60 * 1000, // 2 minutes
    retry: 2,
    onError: (error) => {
      console.error('Error fetching features summary:', formatApiError(error));
    }
  });
};

// Hook for getting feature store statistics
export const useFeatureStats = (days: number = 7) => {
  return useQuery({
    queryKey: featuresKeys.stats(days),
    queryFn: () => featuresApi.getFeatureStats(days),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
    onError: (error) => {
      console.error('Error fetching feature stats:', formatApiError(error));
    }
  });
};

// Hook for calculating features immediately (mutation)
export const useCalculateFeatures = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ticker, date }: { ticker: string; date?: string }) =>
      featuresApi.calculateFeaturesImmediate(ticker, date),
    onSuccess: (data, variables) => {
      // Invalidate and refetch related queries
      queryClient.invalidateQueries({ queryKey: featuresKeys.daily(variables.ticker) });
      queryClient.invalidateQueries({ queryKey: featuresKeys.history(variables.ticker, 30) });
      queryClient.invalidateQueries({ queryKey: featuresKeys.summary() });
      queryClient.invalidateQueries({ queryKey: featuresKeys.stats(7) });
      
      console.log(`✅ Features calculated for ${variables.ticker}`);
    },
    onError: (error, variables) => {
      console.error(`❌ Error calculating features for ${variables.ticker}:`, formatApiError(error));
    }
  });
};

// Custom hook for feature data with derived calculations
export const useEnhancedFeatures = (ticker: string, date?: string) => {
  const featuresQuery = useDailyFeatures(ticker, date);
  const historyQuery = useFeatureHistory(ticker, 30);

  // Derive additional insights from the data
  const enhancedData = {
    ...featuresQuery,
    data: featuresQuery.data ? {
      ...featuresQuery.data,
      // Calculate derived metrics
      sentimentTrend: historyQuery.data?.features ? 
        calculateSentimentTrend(historyQuery.data.features) : null,
      returnsTrend: historyQuery.data?.features ? 
        calculateReturnsTrend(historyQuery.data.features) : null,
      riskScore: featuresQuery.data ? 
        calculateRiskScore(featuresQuery.data) : null,
    } : undefined
  };

  return enhancedData;
};

// Hook to fetch LLM-enhanced analytics for a ticker.
// Disabled by default: the endpoint runs LLM inference server-side (30-60s)
// and used to fire on every StockDetail view, timing out at 10s each time.
// The AI Trading Desk (/desk/{ticker}) supersedes it with pre-computed
// analyses; callers may still opt in explicitly (user-clicked).
export const useEnhancedAnalytics = (ticker: string, enabled: boolean = false) => {
  return useQuery<EnhancedFeaturesResponse>({
    queryKey: featuresKeys.enhanced(ticker),
    queryFn: () => featuresApi.getEnhancedFeatures(ticker),
    enabled: !!ticker && enabled,
    staleTime: 30 * 60 * 1000,
    retry: 0,
    onError: (error) => {
      console.error(`Error fetching enhanced analytics for ${ticker}:`, formatApiError(error));
    }
  });
};

// Helper functions for derived calculations
const calculateSentimentTrend = (features: DailyFeatures[]) => {
  const recentFeatures = features.slice(-7); // Last 7 days
  const sentiments = recentFeatures
    .map(f => f.sent_mean_7d)
    .filter(s => s !== null) as number[];

  if (sentiments.length < 2) return null;

  const firstSentiment = sentiments[0];
  const lastSentiment = sentiments[sentiments.length - 1];
  const trend = lastSentiment - firstSentiment;

  return {
    direction: trend > 0 ? 'up' : trend < 0 ? 'down' : 'flat',
    magnitude: Math.abs(trend),
    current: lastSentiment,
    change: trend
  };
};

const calculateReturnsTrend = (features: DailyFeatures[]) => {
  const recentFeatures = features.slice(-5); // Last 5 days
  const returns = recentFeatures
    .map(f => f.ret_1d)
    .filter(r => r !== null) as number[];

  if (returns.length < 2) return null;

  const avgReturn = returns.reduce((sum, r) => sum + r, 0) / returns.length;
  const volatility = Math.sqrt(
    returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length
  );

  return {
    avgReturn,
    volatility,
    trend: avgReturn > 0 ? 'positive' : avgReturn < 0 ? 'negative' : 'neutral'
  };
};

const calculateRiskScore = (features: DailyFeatures): number => {
  // Simple risk score based on volatility and sentiment shock
  let risk = 0;

  // Add risk for high volatility (vol_z)
  if (features.vol_z && Math.abs(features.vol_z) > 2) {
    risk += Math.abs(features.vol_z) * 0.2;
  }

  // Add risk for sentiment shock
  if (features.sent_shock && Math.abs(features.sent_shock) > 1) {
    risk += Math.abs(features.sent_shock) * 0.3;
  }

  // Add risk for low article count (uncertainty)
  if (features.article_count_7d < 3) {
    risk += 0.5;
  }

  // Normalize to 0-1 scale
  return Math.min(risk / 2, 1);
};
