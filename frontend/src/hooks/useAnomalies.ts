import { useQuery } from '@tanstack/react-query';
import { anomaliesApi, formatApiError } from '../api/client';

export const anomalyKeys = {
  all: ['anomalies'] as const,
  allAnomalies: (params?: { limit?: number }) => ['anomalies', 'all', params] as const,
  ticker: (ticker: string) => ['anomalies', 'ticker', ticker] as const,
  price: (ticker: string) => ['anomalies', 'price', ticker] as const,
  sentiment: (ticker: string) => ['anomalies', 'sentiment', ticker] as const,
  patterns: (ticker: string) => ['anomalies', 'patterns', ticker] as const,
};

export const useAllAnomalies = (params?: {
  ticker?: string;
  include_market_wide?: boolean;
  min_severity?: number;
  limit?: number;
}) => {
  return useQuery({
    queryKey: anomalyKeys.allAnomalies(params),
    queryFn: () => anomaliesApi.getAllAnomalies(params),
    staleTime: 5 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error('Error fetching all anomalies:', formatApiError(error));
    },
  });
};

export const useTickerAnomalies = (ticker: string, params?: {
  lookback_days?: number;
  z_threshold?: number;
}) => {
  return useQuery({
    queryKey: anomalyKeys.ticker(ticker),
    queryFn: () => anomaliesApi.getTickerAnomalies(ticker, params),
    enabled: !!ticker,
    staleTime: 5 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error(`Error fetching anomalies for ${ticker}:`, formatApiError(error));
    },
  });
};

export const usePriceAnomalies = (ticker: string, params?: {
  lookback_days?: number;
  z_threshold?: number;
}) => {
  return useQuery({
    queryKey: anomalyKeys.price(ticker),
    queryFn: () => anomaliesApi.getPriceAnomalies(ticker, params),
    enabled: !!ticker,
    staleTime: 5 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error(`Error fetching price anomalies for ${ticker}:`, formatApiError(error));
    },
  });
};

export const useSentimentAnomalies = (ticker: string, params?: {
  lookback_days?: number;
  z_threshold?: number;
}) => {
  return useQuery({
    queryKey: anomalyKeys.sentiment(ticker),
    queryFn: () => anomaliesApi.getSentimentAnomalies(ticker, params),
    enabled: !!ticker,
    staleTime: 5 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error(`Error fetching sentiment anomalies for ${ticker}:`, formatApiError(error));
    },
  });
};

export const usePatternAnomalies = (ticker: string, params?: {
  lookback_days?: number;
}) => {
  return useQuery({
    queryKey: anomalyKeys.patterns(ticker),
    queryFn: () => anomaliesApi.getPatternAnomalies(ticker, params),
    enabled: !!ticker,
    staleTime: 5 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error(`Error fetching pattern anomalies for ${ticker}:`, formatApiError(error));
    },
  });
};
