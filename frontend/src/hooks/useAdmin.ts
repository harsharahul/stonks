import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api/client';

export function useTaskCatalog() {
  return useQuery({
    queryKey: ['admin', 'task-catalog'],
    queryFn: () => adminApi.getTaskCatalog(),
    staleTime: Infinity,
  });
}

export function useJobHistory(jobName?: string) {
  return useQuery({
    queryKey: ['admin', 'jobs', jobName],
    queryFn: () => adminApi.getJobHistory({ job_name: jobName, limit: 50 }),
    refetchInterval: 10_000,
  });
}

export function useSignalSources() {
  return useQuery({
    queryKey: ['admin', 'signal-sources'],
    queryFn: () => adminApi.getSignalSources(),
    refetchInterval: 30_000,
  });
}

export function useToggleSignalSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => adminApi.toggleSignalSource(sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'signal-sources'] });
    },
  });
}

export function useTriggerTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobName, params }: { jobName: string; params?: Record<string, unknown> }) =>
      adminApi.triggerTask(jobName, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'jobs'] });
    },
  });
}
