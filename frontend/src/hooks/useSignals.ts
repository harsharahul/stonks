import { useQuery } from '@tanstack/react-query';
import { signalsApi } from '../api/client';

export const signalKeys = {
  all: ['signals'] as const,
  list: (params?: Record<string, any>) => ['signals', 'list', params] as const,
  ticker: (ticker: string) => ['signals', 'ticker', ticker] as const,
  types: () => ['signals', 'types'] as const,
  alertStats: (days?: number) => ['signals', 'alert-stats', days] as const,
};

export const useAllSignals = (params?: {
  ticker?: string;
  signal_type?: string;
  direction?: string;
  min_strength?: number;
  min_confidence?: number;
  active_only?: boolean;
  limit?: number;
}) => {
  return useQuery({
    queryKey: signalKeys.list(params),
    queryFn: () => signalsApi.getSignals(params),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
};

export const useTickerSignals = (ticker: string | null, activeOnly: boolean = true) => {
  return useQuery({
    queryKey: signalKeys.ticker(ticker || ''),
    queryFn: () => signalsApi.getTickerSignals(ticker!, { active_only: activeOnly }),
    enabled: !!ticker,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
};

export const useSignalTypes = () => {
  return useQuery({
    queryKey: signalKeys.types(),
    queryFn: () => signalsApi.getSignalTypes(),
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });
};

export const useAlertStats = (days: number = 7) => {
  return useQuery({
    queryKey: signalKeys.alertStats(days),
    queryFn: () => signalsApi.getAlertStats(days),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
};
