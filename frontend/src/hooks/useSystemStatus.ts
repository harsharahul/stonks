import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const useHealthCheck = () => {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: async () => {
      const res = await axios.get(`${baseUrl}/health`);
      return res.data as { status: string; service: string };
    },
    staleTime: 15_000,
    refetchInterval: 30_000,
    retry: 1,
  });
};

export const useReadyCheck = () => {
  return useQuery({
    queryKey: ['system', 'ready'],
    queryFn: async () => {
      const res = await axios.get(`${baseUrl}/ready`);
      return res.data as { status: string; service: string };
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  });
};

export const useStockStats = () => {
  return useQuery({
    queryKey: ['system', 'stock-stats'],
    queryFn: async () => {
      const res = await axios.get(`${baseUrl}/stocks-enhanced/stats`);
      return res.data;
    },
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
    retry: 1,
  });
};
