import React from 'react';
import { Monitor, RefreshCw, CheckCircle, XCircle, AlertTriangle, Clock, Wifi, Database, Activity } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useHealthCheck, useReadyCheck, useStockStats } from '../hooks/useSystemStatus';
import { useIngestionStatus } from '../hooks/useWSBDashboard';
import FreshnessIndicator from './FreshnessIndicator';
import { cn } from '../utils/format';

// Keep in sync with app/celery_beat_config.py (the source of truth).
const BEAT_TASKS = [
  { name: 'News Ingestion (RSS)', schedule: 'Every 10 min', sourceKey: 'News RSS' },
  { name: 'WSB Reddit Enhanced', schedule: 'Every 30 min', sourceKey: 'WSB Enhanced' },
  { name: 'Post-Ingest Processing', schedule: 'Every 15 min', sourceKey: null },
  { name: 'Price Ingestion', schedule: 'Hourly', sourceKey: null },
  { name: 'Feature Calculation', schedule: 'Daily 05:00 UTC', sourceKey: null },
  { name: 'Signal Generation', schedule: 'Daily 06:00 UTC', sourceKey: null },
  { name: 'Recommendations', schedule: 'Daily 06:30 UTC', sourceKey: null },
  { name: 'Alert Generation', schedule: 'Every 5 min', sourceKey: null },
  { name: 'Anomaly Detection', schedule: 'Every 15 min', sourceKey: null },
  { name: 'Earnings Calendar', schedule: 'Daily 07:00 UTC', sourceKey: 'Earnings Calendar' },
  { name: 'Stock Knowledge (LLM)', schedule: 'Daily 02:30 UTC', sourceKey: null },
  { name: 'AI Desk — Universe Refresh', schedule: 'Sunday 00:00 UTC', sourceKey: null },
  { name: 'AI Desk — Nightly Batch', schedule: 'Daily 07:15 UTC', sourceKey: null },
  { name: 'AI Desk — Outcome Scoring', schedule: 'Daily 23:00 UTC', sourceKey: null },
];

const StatusDot: React.FC<{ ok: boolean | undefined; loading?: boolean }> = ({ ok, loading }) => {
  if (loading) return <span className="w-2.5 h-2.5 rounded-full bg-neutral-300 dark:bg-neutral-600 animate-pulse" />;
  if (ok === undefined) return <span className="w-2.5 h-2.5 rounded-full bg-neutral-300 dark:bg-neutral-600" />;
  return <span className={cn('w-2.5 h-2.5 rounded-full', ok ? 'bg-emerald-500' : 'bg-red-500')} />;
};

const KPICard: React.FC<{
  icon: React.ReactNode;
  label: string;
  status: string;
  ok: boolean | undefined;
  loading?: boolean;
  detail?: string;
}> = ({ icon, label, status, ok, loading, detail }) => (
  <div className={cn(
    'rounded-lg border p-4',
    loading ? 'bg-neutral-50 dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700' :
    ok ? 'bg-emerald-50 dark:bg-emerald-900/30 border-emerald-200 dark:border-emerald-700' :
    ok === false ? 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-700' :
    'bg-neutral-50 dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700'
  )}>
    <div className="flex items-center gap-2 mb-2">
      <span className="text-neutral-500 dark:text-neutral-400">{icon}</span>
      <span className="text-xs font-medium text-neutral-600 dark:text-neutral-400 uppercase tracking-wider">{label}</span>
    </div>
    <div className="flex items-center gap-2">
      <StatusDot ok={ok} loading={loading} />
      <span className={cn('text-sm font-semibold', ok ? 'text-emerald-700 dark:text-emerald-400' : ok === false ? 'text-red-700 dark:text-red-400' : 'text-neutral-600 dark:text-neutral-300')}>
        {loading ? 'Checking...' : status}
      </span>
    </div>
    {detail && <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">{detail}</p>}
  </div>
);

const SystemStatus: React.FC = () => {
  const queryClient = useQueryClient();
  const health = useHealthCheck();
  const ready = useReadyCheck();
  const ingestion = useIngestionStatus();
  const stockStats = useStockStats();

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ['system'] });
    queryClient.invalidateQueries({ queryKey: ['wsb-dashboard', 'ingestion-status'] });
  };

  const sources = ingestion.data?.sources ?? [];
  const pipelineHealth = ingestion.data?.system_health === 'healthy';
  const operationalCount = ingestion.data?.operational_sources ?? 0;
  const totalSources = ingestion.data?.total_sources ?? 0;

  const trackingStats = stockStats.data?.tracking_stats;

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-neutral-100 dark:bg-neutral-700 rounded-lg">
            <Monitor className="w-6 h-6 text-neutral-700 dark:text-neutral-300" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-neutral-900 dark:text-white">System Status</h1>
            <FreshnessIndicator
              dataUpdatedAt={ingestion.dataUpdatedAt}
              expectedIntervalMinutes={2}
              label="Last checked"
            />
          </div>
        </div>
        <button
          onClick={refreshAll}
          className="px-3 py-2 text-sm bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors inline-flex items-center gap-1.5"
        >
          <RefreshCw className={cn('w-3.5 h-3.5', (health.isFetching || ingestion.isFetching) && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Health KPI Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPICard
          icon={<Activity className="w-4 h-4" />}
          label="API"
          status={health.data?.status === 'healthy' ? 'Healthy' : health.isError ? 'Down' : 'Unknown'}
          ok={health.data?.status === 'healthy' ? true : health.isError ? false : undefined}
          loading={health.isLoading}
        />
        <KPICard
          icon={<Database className="w-4 h-4" />}
          label="Database"
          status={ready.data?.status === 'ready' ? 'Ready' : ready.isError ? 'Error' : 'Unknown'}
          ok={ready.data?.status === 'ready' ? true : ready.isError ? false : undefined}
          loading={ready.isLoading}
        />
        <KPICard
          icon={<Wifi className="w-4 h-4" />}
          label="Pipeline"
          status={pipelineHealth ? `${operationalCount}/${totalSources} sources` : ingestion.isError ? 'Error' : 'Checking...'}
          ok={ingestion.data ? pipelineHealth : undefined}
          loading={ingestion.isLoading}
          detail={pipelineHealth ? 'All sources operational' : undefined}
        />
        <KPICard
          icon={<Monitor className="w-4 h-4" />}
          label="Coverage"
          status={trackingStats ? `${trackingStats.coverage.feature_coverage}` : '—'}
          ok={trackingStats ? parseFloat(trackingStats.coverage.feature_coverage) > 50 : undefined}
          loading={stockStats.isLoading}
          detail={trackingStats ? `${trackingStats.active_stocks} active stocks` : undefined}
        />
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Data Sources */}
        <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-neutral-100 dark:border-neutral-700">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-white">Data Sources</h2>
          </div>
          {ingestion.isLoading ? (
            <div className="p-4 space-y-3">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="animate-pulse flex items-center gap-3">
                  <div className="w-8 h-8 bg-neutral-200 dark:bg-neutral-700 rounded-lg" />
                  <div className="flex-1 space-y-1">
                    <div className="h-3 bg-neutral-200 dark:bg-neutral-700 rounded w-24" />
                    <div className="h-2 bg-neutral-100 dark:bg-neutral-600 rounded w-32" />
                  </div>
                  <div className="h-5 w-16 bg-neutral-200 dark:bg-neutral-700 rounded" />
                </div>
              ))}
            </div>
          ) : (
            <div className="divide-y divide-neutral-100 dark:divide-neutral-700">
              {sources.map((src: any) => {
                const isOp = src.status === 'operational';
                const isDeg = src.status === 'degraded';
                return (
                  <div key={src.name} className="px-4 py-3 flex items-center gap-3">
                    <div className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center',
                      isOp ? 'bg-emerald-50 dark:bg-emerald-900/30' : isDeg ? 'bg-amber-50 dark:bg-amber-900/30' : 'bg-red-50 dark:bg-red-900/30'
                    )}>
                      {isOp ? <CheckCircle className="w-4 h-4 text-emerald-600" /> :
                       isDeg ? <AlertTriangle className="w-4 h-4 text-amber-600" /> :
                       <XCircle className="w-4 h-4 text-red-600" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-neutral-900 dark:text-white">{src.name}</div>
                      <div className="text-xs text-neutral-500 dark:text-neutral-400">
                        {src.article_count} articles
                        {src.freshness_minutes != null && ` · ${Math.round(src.freshness_minutes)}m ago`}
                      </div>
                    </div>
                    <span className={cn(
                      'text-xs font-medium px-2 py-0.5 rounded',
                      isOp ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400' :
                      isDeg ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400' :
                      'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                    )}>
                      {src.status}
                    </span>
                  </div>
                );
              })}
              {sources.length === 0 && (
                <div className="px-4 py-8 text-center text-sm text-neutral-500 dark:text-neutral-400">No source data available</div>
              )}
            </div>
          )}
        </div>

        {/* Celery Beat Schedule */}
        <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-neutral-100 dark:border-neutral-700">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-white">Celery Beat Schedule</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-neutral-50 dark:bg-neutral-700/50 text-left">
                  <th className="px-4 py-2 text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Task</th>
                  <th className="px-4 py-2 text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Schedule</th>
                  <th className="px-4 py-2 text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700">
                {BEAT_TASKS.map((task) => {
                  const matchedSource = task.sourceKey
                    ? sources.find((s: any) => s.name === task.sourceKey)
                    : null;
                  const isOp = matchedSource?.status === 'operational';
                  const freshness = matchedSource?.freshness_minutes;

                  return (
                    <tr key={task.name} className="hover:bg-neutral-50 dark:hover:bg-neutral-700/50">
                      <td className="px-4 py-2.5 text-neutral-900 dark:text-neutral-100 font-medium">{task.name}</td>
                      <td className="px-4 py-2.5 text-neutral-500 dark:text-neutral-400">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {task.schedule}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        {matchedSource ? (
                          <span className={cn(
                            'inline-flex items-center gap-1 text-xs font-medium',
                            isOp ? 'text-emerald-700 dark:text-emerald-400' : 'text-amber-700 dark:text-amber-400'
                          )}>
                            <StatusDot ok={isOp} />
                            {freshness != null ? `${Math.round(freshness)}m ago` : matchedSource.status}
                          </span>
                        ) : (
                          <span className="text-xs text-neutral-400 dark:text-neutral-500">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Tracking Stats */}
      {trackingStats && (
        <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 shadow-sm p-4">
          <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">Tracking Overview</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            {[
              { label: 'Total Stocks', value: trackingStats.total_stocks },
              { label: 'Active', value: trackingStats.active_stocks },
              { label: 'Inactive', value: trackingStats.inactive_stocks },
              { label: 'Signals (7d)', value: trackingStats.recent_activity.signals_7d },
              { label: 'Alerts (7d)', value: trackingStats.recent_activity.alerts_7d },
              { label: 'With Features', value: trackingStats.recent_activity.stocks_with_features_7d },
            ].map((stat) => (
              <div key={stat.label} className="bg-neutral-50 dark:bg-neutral-700/50 rounded-lg p-3">
                <div className="text-xs text-neutral-500 dark:text-neutral-400 mb-0.5">{stat.label}</div>
                <div className="text-lg font-bold text-neutral-900 dark:text-white">{stat.value}</div>
              </div>
            ))}
          </div>
          {/* Priority distribution */}
          <div className="mt-3 flex gap-2">
            {Object.entries(trackingStats.priority_distribution).map(([priority, count]) => (
              <span key={priority} className="text-xs bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-400 px-2 py-1 rounded">
                {priority}: {count as number}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SystemStatus;
