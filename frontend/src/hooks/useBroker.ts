/**
 * React Query hooks for the brokerage (Alpaca) API.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brokerApi, PlaceOrderInput } from '../api/broker';

export const brokerKeys = {
  all: ['broker'] as const,
  account: () => ['broker', 'account'] as const,
  positions: () => ['broker', 'positions'] as const,
  orders: () => ['broker', 'orders'] as const,
  sizing: (symbol: string) => ['broker', 'sizing', symbol.toUpperCase()] as const,
};

export function useBrokerAccount() {
  return useQuery({
    queryKey: brokerKeys.account(),
    queryFn: () => brokerApi.getAccount(),
    staleTime: 60 * 1000,
    retry: (failureCount, error: any) => {
      // 404 = not linked — a stable state, don't retry
      if (error?.response?.status === 404) return false;
      return failureCount < 2;
    },
  });
}

export function useLinkAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: brokerApi.linkAccount,
    onSuccess: () => qc.invalidateQueries({ queryKey: brokerKeys.all }),
  });
}

export function useUnlinkAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: brokerApi.unlinkAccount,
    onSuccess: () => qc.invalidateQueries({ queryKey: brokerKeys.all }),
  });
}

export function usePositions(enabled = true) {
  return useQuery({
    queryKey: brokerKeys.positions(),
    queryFn: () => brokerApi.getPositions(),
    enabled,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
    retry: 1,
  });
}

export function useOrders(enabled = true) {
  return useQuery({
    queryKey: brokerKeys.orders(),
    queryFn: () => brokerApi.listOrders(),
    enabled,
    staleTime: 30 * 1000,
    retry: 1,
  });
}

export function usePlaceOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PlaceOrderInput) => brokerApi.placeOrder(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: brokerKeys.orders() });
      qc.invalidateQueries({ queryKey: brokerKeys.positions() });
      qc.invalidateQueries({ queryKey: brokerKeys.account() });
    },
  });
}

export function useCancelOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (orderId: string) => brokerApi.cancelOrder(orderId),
    onSuccess: () => qc.invalidateQueries({ queryKey: brokerKeys.orders() }),
  });
}

export function useSizing(symbol: string | null, enabled = false) {
  return useQuery({
    queryKey: symbol ? brokerKeys.sizing(symbol) : ['broker', 'sizing', '__none__'],
    queryFn: () => {
      if (!symbol) throw new Error('no symbol');
      return brokerApi.getSizing(symbol);
    },
    enabled: Boolean(symbol) && enabled,
    staleTime: 60 * 1000,
    retry: 1,
  });
}
