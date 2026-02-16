import { useQuery } from '@tanstack/react-query';
import { feedApi, signalsApi, anomaliesApi, marketAnalysisApi, formatApiError } from '../api/client';

// Query key factory
export const wsbDashboardKeys = {
  all: ['wsb-dashboard'] as const,
  trending: (days?: number, limit?: number) => ['wsb-dashboard', 'trending', days, limit] as const,
  alerts: (hours?: number) => ['wsb-dashboard', 'alerts', hours] as const,
  marketOverview: () => ['wsb-dashboard', 'market-overview'] as const,
  anomalies: () => ['wsb-dashboard', 'anomalies'] as const,
  ingestionStatus: () => ['wsb-dashboard', 'ingestion-status'] as const,
  sentimentAnalysis: () => ['wsb-dashboard', 'sentiment-analysis'] as const,
  marketAnalysis: () => ['wsb-dashboard', 'market-analysis'] as const,
};

export const useWSBTrending = (days: number = 7, limit: number = 20) => {
  return useQuery({
    queryKey: wsbDashboardKeys.trending(days, limit),
    queryFn: () => feedApi.getWSBTrending({ days, limit }),
    staleTime: 2 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    retry: 2,
    onError: (error: any) => {
      console.error('Error fetching WSB trending:', formatApiError(error));
    },
  });
};

export const useLatestAlerts = (hours: number = 12) => {
  return useQuery({
    queryKey: wsbDashboardKeys.alerts(hours),
    queryFn: () => signalsApi.getAlerts({ hours, limit: 15 }),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
    retry: 2,
    onError: (error: any) => {
      console.error('Error fetching alerts:', formatApiError(error));
    },
  });
};

export const useMarketSignalsOverview = () => {
  return useQuery({
    queryKey: wsbDashboardKeys.marketOverview(),
    queryFn: () => signalsApi.getMarketOverview({ limit: 20 }),
    staleTime: 2 * 60 * 1000,
    retry: 2,
    onError: (error: any) => {
      console.error('Error fetching market overview:', formatApiError(error));
    },
  });
};

export const useMarketAnomalies = () => {
  return useQuery({
    queryKey: wsbDashboardKeys.anomalies(),
    queryFn: () => anomaliesApi.getMarketAnomalies(),
    staleTime: 5 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error('Error fetching market anomalies:', formatApiError(error));
    },
  });
};

export const useIngestionStatus = () => {
  return useQuery({
    queryKey: wsbDashboardKeys.ingestionStatus(),
    queryFn: () => feedApi.getIngestionStatus(),
    staleTime: 2 * 60 * 1000,
    refetchInterval: 2 * 60 * 1000,
    retry: 2,
    onError: (error: any) => {
      console.error('Error fetching ingestion status:', formatApiError(error));
    },
  });
};

export const useSentimentAnalysis = () => {
  return useQuery({
    queryKey: wsbDashboardKeys.sentimentAnalysis(),
    queryFn: () => marketAnalysisApi.getSentimentAnalysis(),
    staleTime: 5 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error('Error fetching sentiment analysis:', formatApiError(error));
    },
  });
};

export const useMarketAnalysis = () => {
  return useQuery({
    queryKey: wsbDashboardKeys.marketAnalysis(),
    queryFn: () => marketAnalysisApi.getMarketOverview(),
    staleTime: 5 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error('Error fetching market analysis:', formatApiError(error));
    },
  });
};
