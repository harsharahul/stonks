import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { signalsApi } from '../api/client';

type AlertDTO = {
  id: string;
  ticker: string;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  triggered_at: string;
};

const fetchLatestAlerts = async (): Promise<AlertDTO[]> => {
  const res = await signalsApi.getAlerts({ hours: 6, limit: 10 });
  return res.alerts as AlertDTO[];
};

const severityBadge = (sev: AlertDTO['severity']) => {
  const map: Record<AlertDTO['severity'], string> = {
    low: 'bg-neutral-100 text-neutral-700 dark:bg-neutral-700 dark:text-neutral-300',
    medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
    high: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  };
  return map[sev] || map.low;
};

const LatestAlertsPanel: React.FC = () => {
  const { data, isLoading, isError } = useQuery({ queryKey: ['latestAlerts'], queryFn: fetchLatestAlerts, refetchInterval: 60_000 });

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-neutral-900 dark:text-white">Latest Alerts</h2>
        <span className="text-xs text-neutral-500 dark:text-neutral-400">Last 6 hours</span>
      </div>
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-12 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <div className="text-sm text-red-600 dark:text-red-400">Failed to load alerts</div>
      ) : data && data.length > 0 ? (
        <ul className="divide-y divide-neutral-200 dark:divide-neutral-700">
          {data.slice(0, 6).map((a) => (
            <li key={a.id} className="py-3 flex items-start justify-between">
              <div className="mr-3">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-mono font-semibold text-neutral-900 dark:text-white">{a.ticker}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${severityBadge(a.severity)}`}>{a.severity.toUpperCase()}</span>
                  <span className="text-xs text-neutral-500 dark:text-neutral-400">{new Date(a.triggered_at).toLocaleTimeString()}</span>
                </div>
                <div className="text-sm font-medium text-neutral-900 dark:text-neutral-100 mt-1">{a.title}</div>
                <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5">{a.message}</div>
              </div>
              <span className="text-xs text-neutral-500 dark:text-neutral-400 capitalize">{a.alert_type.replace('_', ' ')}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-sm text-neutral-500 dark:text-neutral-400">No alerts in the last 6 hours</div>
      )}
    </div>
  );
};

export default LatestAlertsPanel;


