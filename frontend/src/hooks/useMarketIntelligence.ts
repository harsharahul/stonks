import { useQuery } from '@tanstack/react-query';
import { marketAnalysisApi, recommendationsApi, stocksApi, formatApiError } from '../api/client';

export const intelligenceKeys = {
  all: ['intelligence'] as const,
  outlook: () => ['intelligence', 'outlook'] as const,
  overview: () => ['intelligence', 'overview'] as const,
  pressureTest: () => ['intelligence', 'pressure-test'] as const,
  recommendations: () => ['intelligence', 'recommendations'] as const,
  morningBrief: () => ['intelligence', 'morning-brief'] as const,
  stockKnowledge: (ticker: string) => ['intelligence', 'knowledge', ticker] as const,
};

export const useTomorrowOutlook = () => {
  return useQuery({
    queryKey: intelligenceKeys.outlook(),
    queryFn: () => marketAnalysisApi.getTomorrowOutlook(),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    retry: 2,
    onError: (error: any) => {
      console.error('Error fetching tomorrow outlook:', formatApiError(error));
    },
  });
};

export const useIntelMarketOverview = () => {
  return useQuery({
    queryKey: intelligenceKeys.overview(),
    queryFn: () => marketAnalysisApi.getMarketOverview(),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    retry: 2,
    onError: (error: any) => {
      console.error('Error fetching market overview:', formatApiError(error));
    },
  });
};

export const usePressureTest = () => {
  return useQuery({
    queryKey: intelligenceKeys.pressureTest(),
    queryFn: () => marketAnalysisApi.getPressureTestSummary(),
    staleTime: 10 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error('Error fetching pressure test:', formatApiError(error));
    },
  });
};

export const useDailyRecommendations = () => {
  return useQuery({
    queryKey: intelligenceKeys.recommendations(),
    queryFn: () => recommendationsApi.getDailyRecommendations(),
    staleTime: 10 * 60 * 1000,
    refetchInterval: 30 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error('Error fetching recommendations:', formatApiError(error));
    },
  });
};

export const useMorningBrief = () => {
  return useQuery({
    queryKey: intelligenceKeys.morningBrief(),
    queryFn: () => marketAnalysisApi.getMorningBrief(),
    staleTime: 15 * 60 * 1000,
    refetchInterval: 30 * 60 * 1000,
    retry: 1,
    onError: (error: any) => {
      console.error('Error fetching morning brief:', formatApiError(error));
    },
  });
};

export const useStockKnowledge = (ticker: string) => {
  return useQuery({
    queryKey: intelligenceKeys.stockKnowledge(ticker),
    queryFn: () => stocksApi.getStockKnowledge(ticker),
    staleTime: 30 * 60 * 1000,
    retry: 0,
    enabled: !!ticker,
    onError: () => {
      // 404 is expected when knowledge hasn't been generated yet — suppress error
    },
  });
};
