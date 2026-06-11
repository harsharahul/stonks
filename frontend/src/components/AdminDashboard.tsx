import React, { useState, useMemo } from 'react';
import { Shield, Play, RefreshCw, Clock, CheckCircle, XCircle, Loader2, Filter } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useTaskCatalog, useJobHistory, useTriggerTask, useSignalSources, useToggleSignalSource } from '../hooks/useAdmin';
import { useToast } from '../hooks/useToast';
import ToastManager from './ToastManager';
import { cn, formatRelativeTime } from '../utils/format';
import type { ETLJobRun, TaskCatalogEntry } from '../types/api';

const QUEUE_COLORS: Record<string, string> = {
  ingestion: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  compute: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  analytics: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
};

const STATUS_STYLES: Record<string, string> = {
  queued: 'bg-neutral-100 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-300',
  running: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 animate-pulse',
  completed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  success: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

function formatDuration(start: string | null, end: string | null): string {
  if (!start) return '—';
  if (!end) return 'Running...';
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 1000) return `${ms}ms`;
  const secs = Math.round(ms / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

// Tasks that need a parameter typed in before Run Now can dispatch them.
const PARAM_TASKS: Record<string, { key: string; placeholder: string }> = {
  desk_run_ticker: { key: 'ticker', placeholder: 'AAPL' },
};

const AdminDashboard: React.FC = () => {
  const queryClient = useQueryClient();
  const catalog = useTaskCatalog();
  const triggerTask = useTriggerTask();
  const signalSources = useSignalSources();
  const toggleSource = useToggleSignalSource();
  const [jobFilter, setJobFilter] = useState<string>('');
  const [taskParams, setTaskParams] = useState<Record<string, string>>({});
  const jobHistory = useJobHistory(jobFilter || undefined);
  const { toasts, showSuccess, showError: showErrorToast, removeToast } = useToast();

  const tasks = catalog.data?.tasks ?? {};
  const taskEntries = Object.entries(tasks);
  const jobs = jobHistory.data?.jobs ?? [];

  // Build last-run lookup from job history
  const lastRunByTask = useMemo(() => {
    const map: Record<string, ETLJobRun> = {};
    for (const job of jobs) {
      if (!map[job.job_name]) map[job.job_name] = job;
    }
    return map;
  }, [jobs]);

  const handleTrigger = async (jobName: string) => {
    const paramSpec = PARAM_TASKS[jobName];
    let params: Record<string, unknown> | undefined;
    if (paramSpec) {
      const value = (taskParams[jobName] || '').trim().toUpperCase();
      if (!value) {
        showErrorToast('Missing Parameter', `Enter a ${paramSpec.key} before running ${jobName.replace(/_/g, ' ')}`);
        return;
      }
      params = { [paramSpec.key]: value };
    }
    if (!window.confirm(`Run "${jobName.replace(/_/g, ' ')}" now?`)) return;
    try {
      const result = await triggerTask.mutateAsync({ jobName, params });
      showSuccess('Task Dispatched', result.message);
    } catch (err: any) {
      showErrorToast('Dispatch Failed', err?.response?.data?.detail || 'Failed to dispatch task');
    }
  };

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ['admin'] });
  };

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
            <Shield className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-neutral-900 dark:text-white">Admin Dashboard</h1>
            <p className="text-sm text-neutral-500 dark:text-neutral-400">
              Manage tasks and view job history
            </p>
          </div>
        </div>
        <button
          onClick={refreshAll}
          className="px-3 py-2 text-sm bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors inline-flex items-center gap-1.5"
        >
          <RefreshCw className={cn('w-3.5 h-3.5', (catalog.isFetching || jobHistory.isFetching) && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Task Catalog Grid */}
      <div>
        <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">Task Catalog</h2>
        {catalog.isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className="h-32 bg-neutral-100 dark:bg-neutral-800 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : catalog.error ? (
          <div className="card bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm">
            Failed to load task catalog. Is the backend running?
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {taskEntries.map(([name, info]: [string, TaskCatalogEntry]) => {
              const lastRun = lastRunByTask[name];
              return (
                <div
                  key={name}
                  className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4 hover:border-neutral-300 dark:hover:border-neutral-600 transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
                        {name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </h3>
                      <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">{info.description}</p>
                    </div>
                    <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded', QUEUE_COLORS[info.queue] || QUEUE_COLORS.ingestion)}>
                      {info.queue}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-neutral-500 dark:text-neutral-400 mb-3">
                    <Clock className="w-3 h-3" />
                    <span>{info.schedule}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    {lastRun ? (
                      <span className="text-[10px] text-neutral-400 dark:text-neutral-500">
                        Last: {formatRelativeTime(lastRun.started_at || '')}
                        {lastRun.status && (
                          <span className={cn('ml-1 px-1 py-0.5 rounded', STATUS_STYLES[lastRun.status] || STATUS_STYLES.queued)}>
                            {lastRun.status}
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-[10px] text-neutral-400 dark:text-neutral-500">No runs recorded</span>
                    )}
                    {PARAM_TASKS[name] && (
                      <input
                        type="text"
                        value={taskParams[name] || ''}
                        onChange={e => setTaskParams(prev => ({ ...prev, [name]: e.target.value }))}
                        placeholder={PARAM_TASKS[name].placeholder}
                        className="w-20 px-2 py-1.5 text-xs uppercase bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-lg text-neutral-900 dark:text-white placeholder-neutral-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    )}
                    <button
                      onClick={() => handleTrigger(name)}
                      disabled={triggerTask.isLoading}
                      className="flex items-center gap-1 px-2.5 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
                    >
                      {triggerTask.isLoading ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Play className="w-3 h-3" />
                      )}
                      Run Now
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Signal Sources (plugin SDK) */}
      <div>
        <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">Signal Sources</h2>
        {signalSources.isLoading ? (
          <div className="h-24 bg-neutral-100 dark:bg-neutral-800 rounded-xl animate-pulse" />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(signalSources.data?.sources ?? []).map(src => (
              <div
                key={src.source_id}
                className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4"
              >
                <div className="flex items-start justify-between mb-1.5">
                  <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">{src.name}</h3>
                  <button
                    onClick={async () => {
                      try {
                        const r = await toggleSource.mutateAsync(src.source_id);
                        showSuccess('Source Updated', `${src.name} is now ${r.enabled ? 'enabled' : 'disabled'}`);
                      } catch (err: any) {
                        showErrorToast('Toggle Failed', err?.response?.data?.detail || 'Failed to toggle source');
                      }
                    }}
                    disabled={toggleSource.isLoading}
                    className={cn(
                      'text-[10px] font-medium px-2 py-1 rounded-full transition-colors',
                      src.enabled
                        ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400 hover:bg-green-100'
                        : 'bg-neutral-100 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-300 hover:bg-neutral-200'
                    )}
                  >
                    {src.enabled ? 'Enabled' : 'Disabled'}
                  </button>
                </div>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-2 line-clamp-2">{src.description}</p>
                <div className="flex items-center gap-2 text-[10px] text-neutral-400 dark:text-neutral-500">
                  <span>{src.signal_types.join(', ')}</span>
                  <span>·</span>
                  <span>every {Math.round(src.update_frequency_seconds / 60)}m</span>
                  {src.state?.last_status && (
                    <>
                      <span>·</span>
                      <span className={cn(src.state.last_status === 'error' && 'text-red-500')}>
                        {src.state.last_status}
                      </span>
                    </>
                  )}
                  {src.state != null && (
                    <>
                      <span>·</span>
                      <span>{src.state.signals_emitted_total} emitted</span>
                    </>
                  )}
                </div>
                {src.track_record != null && (
                  <div className="mt-2 pt-2 border-t border-neutral-100 dark:border-neutral-700 flex items-center gap-2 text-[10px]">
                    <span
                      className={cn(
                        'font-semibold',
                        (src.track_record.win_rate ?? 0) >= 0.5
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-red-500 dark:text-red-400'
                      )}
                    >
                      {Math.round((src.track_record.win_rate ?? 0) * 100)}% win rate
                    </span>
                    <span className="text-neutral-400">·</span>
                    <span className="text-neutral-500 dark:text-neutral-400">
                      {src.track_record.avg_signal_return != null
                        ? `${(src.track_record.avg_signal_return * 100).toFixed(2)}% avg 5d`
                        : '—'}
                    </span>
                    <span className="text-neutral-400">·</span>
                    <span className="text-neutral-400 dark:text-neutral-500">{src.track_record.scored} scored</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {signalSources.data?.builtin_track_records &&
          Object.keys(signalSources.data.builtin_track_records).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(signalSources.data.builtin_track_records).map(([sid, rec]) => (
                <div
                  key={sid}
                  className="flex items-center gap-2 text-[10px] bg-white dark:bg-neutral-800 rounded-full border border-neutral-200 dark:border-neutral-700 px-3 py-1.5"
                >
                  <span className="font-medium text-neutral-700 dark:text-neutral-200">{sid}</span>
                  <span
                    className={cn(
                      'font-semibold',
                      (rec.win_rate ?? 0) >= 0.5
                        ? 'text-green-600 dark:text-green-400'
                        : 'text-red-500 dark:text-red-400'
                    )}
                  >
                    {Math.round((rec.win_rate ?? 0) * 100)}%
                  </span>
                  <span className="text-neutral-400 dark:text-neutral-500">{rec.scored} scored</span>
                </div>
              ))}
            </div>
          )}
      </div>

      {/* Job History */}
      <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-100 dark:border-neutral-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-neutral-900 dark:text-white">Job History</h2>
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-neutral-400" />
            <select
              value={jobFilter}
              onChange={(e) => setJobFilter(e.target.value)}
              className="text-xs bg-neutral-50 dark:bg-neutral-700 border border-neutral-200 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 rounded-lg px-2 py-1 focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All tasks</option>
              {taskEntries.map(([name]) => (
                <option key={name} value={name}>
                  {name.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>
        </div>

        {jobHistory.isLoading ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="h-10 bg-neutral-100 dark:bg-neutral-700 rounded animate-pulse" />
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="px-4 py-12 text-center text-sm text-neutral-500 dark:text-neutral-400">
            No job runs found. Trigger a task above to get started.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ minWidth: '500px' }}>
              <thead>
                <tr className="bg-neutral-50 dark:bg-neutral-900 text-left">
                  <th className="px-4 py-2 text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Job</th>
                  <th className="px-4 py-2 text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Started</th>
                  <th className="px-4 py-2 text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider hidden sm:table-cell">Duration</th>
                  <th className="px-4 py-2 text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Status</th>
                  <th className="px-4 py-2 text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider hidden sm:table-cell">Items</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700">
                {jobs.map((job: ETLJobRun) => (
                  <tr key={job.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-700/50 transition-colors">
                    <td className="px-4 py-2.5">
                      <span className="font-medium text-neutral-900 dark:text-white">
                        {job.job_name.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-neutral-500 dark:text-neutral-400">
                      {job.started_at ? formatRelativeTime(job.started_at) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-neutral-500 dark:text-neutral-400 hidden sm:table-cell">
                      {formatDuration(job.started_at, job.finished_at)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={cn(
                        'inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded',
                        STATUS_STYLES[job.status] || STATUS_STYLES.queued
                      )}>
                        {job.status === 'completed' || job.status === 'success' ? (
                          <CheckCircle className="w-3 h-3" />
                        ) : job.status === 'failed' ? (
                          <XCircle className="w-3 h-3" />
                        ) : job.status === 'running' ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Clock className="w-3 h-3" />
                        )}
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-neutral-500 dark:text-neutral-400 hidden sm:table-cell">
                      {job.items_processed ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ToastManager toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};

export default AdminDashboard;
