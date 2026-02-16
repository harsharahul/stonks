import { useQuery } from '@tanstack/react-query';
import { pricesApi } from '../api/client';
import type { PriceHistoryResponse, PricePeriod } from '../types/api';

/**
 * Fetch OHLCV price history for a ticker with a configurable period.
 * Each period is cached independently via distinct query keys.
 */
export const usePriceHistory = (ticker: string, period: PricePeriod = '1M') => {
  return useQuery<PriceHistoryResponse>({
    queryKey: ['prices', 'history', ticker, period],
    queryFn: () => pricesApi.getPriceHistory(ticker, period),
    enabled: !!ticker,
    staleTime: 5 * 60 * 1000, // 5 minutes (prices update hourly)
    retry: 2,
  });
};
