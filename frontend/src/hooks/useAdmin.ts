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

export function useTriggerTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobName: string) => adminApi.triggerTask(jobName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'jobs'] });
    },
  });
}
