/**
 * /strategies/:slug — verified track record, privacy-reduced trade feed,
 * follow/unfollow. The record chart is computed from broker fills only.
 */
import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Users, Bell, BellOff, Loader2, ArrowLeft, ShieldAlert } from 'lucide-react';
import { strategiesApi } from '../../api/strategies';
import { useAuth } from '../../hooks/useAuth';
import { cn, formatRelativeTime } from '../../utils/format';
import { Disclaimer } from './StrategiesPage';

function StatCard({ label, value, tone }: { label: string; value: string; tone?: 'good' | 'bad' }) {
  return (
    <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-3">
      <div className="text-[10px] uppercase tracking-wide text-neutral-400">{label}</div>
      <div className={cn(
        'text-lg font-semibold',
        tone === 'good' ? 'text-green-600 dark:text-green-400'
          : tone === 'bad' ? 'text-red-600 dark:text-red-400'
          : 'text-neutral-900 dark:text-white'
      )}>
        {value}
      </div>
    </div>
  );
}

const StrategyDetailPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();

  const detail = useQuery({
    // isAuthenticated in the key: the first fetch often races the OIDC token
    // bridge and comes back anonymous (is_owner/is_following wrong) — keying
    // on auth state refetches once the session lands.
    queryKey: ['strategies', 'detail', slug, isAuthenticated],
    queryFn: () => strategiesApi.detail(slug!),
    enabled: Boolean(slug),
  });

  const followMutation = useMutation({
    mutationFn: (following: boolean) =>
      following ? strategiesApi.unfollow(slug!) : strategiesApi.follow(slug!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['strategies'] }),
  });

  if (detail.isLoading) {
    return <div className="max-w-[1000px] mx-auto px-4 py-10"><Loader2 className="w-6 h-6 animate-spin text-neutral-400" /></div>;
  }
  if (detail.error || !detail.data) {
    return (
      <div className="max-w-[1000px] mx-auto px-4 py-10 text-sm text-neutral-500">
        Strategy not found. <Link to="/strategies" className="text-blue-600">Back to strategies</Link>
      </div>
    );
  }

  const { strategy, is_owner, is_following, follower_count, performance, trades } = detail.data;
  const latest = performance.length ? performance[performance.length - 1] : null;

  return (
    <div className="max-w-[1000px] mx-auto px-4 py-6 space-y-5">
      <Link to="/strategies" className="inline-flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300">
        <ArrowLeft className="w-3 h-3" /> All strategies
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-neutral-900 dark:text-white">{strategy.name}</h1>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 uppercase">
              {strategy.kind}
            </span>
            {latest && (
              <span className={cn(
                'text-[10px] px-1.5 py-0.5 rounded-full',
                latest.paper === false
                  ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                  : 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
              )}>
                {latest.paper === false ? 'LIVE' : 'PAPER'}
              </span>
            )}
          </div>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1 max-w-xl">
            {strategy.description || 'No description provided.'}
          </p>
        </div>
        {isAuthenticated && !is_owner && (
          <button
            onClick={() => followMutation.mutate(is_following)}
            disabled={followMutation.isLoading}
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg font-medium transition-colors',
              is_following
                ? 'bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-200 hover:bg-neutral-200'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            )}
          >
            {followMutation.isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : is_following ? <BellOff className="w-4 h-4" /> : <Bell className="w-4 h-4" />}
            {is_following ? 'Unfollow' : 'Follow'}
          </button>
        )}
      </div>

      <Disclaimer />

      {strategy.disclosure && (
        <div className="flex items-start gap-2 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2">
          <ShieldAlert className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span><strong>Owner disclosure:</strong> {strategy.disclosure}</span>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <StatCard label="Followers" value={String(follower_count)} />
        <StatCard
          label="Win rate"
          value={latest?.win_rate != null ? `${(latest.win_rate * 100).toFixed(0)}%` : '—'}
          tone={latest?.win_rate != null ? (latest.win_rate >= 0.5 ? 'good' : 'bad') : undefined}
        />
        <StatCard
          label="Avg return / trade"
          value={latest?.avg_return_pct != null ? `${latest.avg_return_pct.toFixed(1)}%` : '—'}
          tone={latest?.avg_return_pct != null ? (latest.avg_return_pct >= 0 ? 'good' : 'bad') : undefined}
        />
        <StatCard label="Closed trades" value={String(latest?.closed_trade_count ?? 0)} />
        <StatCard
          label="Max drawdown"
          value={latest?.max_drawdown_pct != null ? `${latest.max_drawdown_pct.toFixed(1)}%` : '—'}
          tone={latest?.max_drawdown_pct != null && latest.max_drawdown_pct < -20 ? 'bad' : undefined}
        />
      </div>

      <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-100 dark:border-neutral-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-neutral-900 dark:text-white">Trade Feed</h2>
          <span className="text-[10px] text-neutral-400">sizes withheld for privacy</span>
        </div>
        {trades.length === 0 ? (
          <p className="px-4 py-6 text-sm text-neutral-500 dark:text-neutral-400">No trades yet.</p>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {trades.map((t, i) => (
                <tr key={i} className="border-b border-neutral-50 dark:border-neutral-700/50 last:border-0">
                  <td className="px-4 py-2">
                    <span className={cn(
                      'text-[10px] font-bold uppercase px-1.5 py-0.5 rounded',
                      t.side === 'buy'
                        ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                    )}>
                      {t.side}
                    </span>
                  </td>
                  <td className="px-2 py-2 font-medium text-neutral-900 dark:text-white">
                    <Link to={`/stocks/${t.symbol}`} className="hover:text-blue-600">{t.symbol}</Link>
                  </td>
                  <td className="px-2 py-2 text-neutral-500 dark:text-neutral-400">
                    {t.filled_avg_price != null ? `$${t.filled_avg_price.toFixed(2)}` : t.status}
                  </td>
                  <td className="px-2 py-2 text-[10px] text-neutral-400 uppercase">{t.paper ? 'paper' : 'live'}</td>
                  <td className="px-4 py-2 text-right text-xs text-neutral-400">
                    {t.at ? formatRelativeTime(t.at) : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default StrategyDetailPage;
