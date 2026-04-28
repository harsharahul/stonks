/**
 * React Query hooks for the AI Trading Desk API.
 */
import { useQuery } from '@tanstack/react-query';
import { deskApi, DeskUniverseResponse, DeskTickerView, DeskHistoryResponse } from '../api/desk';

export const deskKeys = {
  all: ['desk'] as const,
  universe: () => ['desk', 'universe'] as const,
  ticker: (ticker: string) => ['desk', 'ticker', ticker.toUpperCase()] as const,
  history: (ticker: string, limit: number) =>
    ['desk', 'history', ticker.toUpperCase(), limit] as const,
};

export function useDeskUniverse() {
  return useQuery<DeskUniverseResponse>({
    queryKey: deskKeys.universe(),
    queryFn: () => deskApi.getUniverse(),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useDeskForTicker(ticker: string | null | undefined) {
  return useQuery<DeskTickerView>({
    queryKey: ticker ? deskKeys.ticker(ticker) : ['desk', 'ticker', '__none__'],
    queryFn: () => {
      if (!ticker) throw new Error('No ticker selected');
      return deskApi.getDeskForTicker(ticker);
    },
    enabled: Boolean(ticker),
    staleTime: 60 * 1000,
    retry: 1,
  });
}

export function useDeskHistory(ticker: string | null | undefined, limit: number = 30) {
  return useQuery<DeskHistoryResponse>({
    queryKey: ticker ? deskKeys.history(ticker, limit) : ['desk', 'history', '__none__'],
    queryFn: () => {
      if (!ticker) throw new Error('No ticker selected');
      return deskApi.getHistory(ticker, limit);
    },
    enabled: Boolean(ticker),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
