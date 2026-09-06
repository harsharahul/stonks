/**
 * /strategies: discover public strategies (verified records) + manage your own.
 * Every surface carries the not-investment-advice disclaimer; ranking is by
 * objective verified metrics only.
 */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Users, TrendingUp, Plus, Loader2, ShieldAlert } from 'lucide-react';
import { strategiesApi, StrategySummary } from '../../api/strategies';
import { useAuth } from '../../hooks/useAuth';
import { cn } from '../../utils/format';

export function Disclaimer() {
  return (
    <div className="flex items-start gap-2 text-[11px] text-neutral-500 dark:text-neutral-400 bg-neutral-50 dark:bg-neutral-800/60 border border-neutral-200 dark:border-neutral-700 rounded-lg px-3 py-2">
      <ShieldAlert className="w-3.5 h-3.5 mt-0.5 shrink-0" />
      <span>
        Strategies are user-published content, <strong>not investment advice</strong>. Past
        performance does not guarantee future results. Track records are computed from real
        broker fills.
      </span>
    </div>
  );
}

function PerfBadges({ s }: { s: StrategySummary }) {
  const p = s.performance;
  return (
    <div className="flex items-center gap-3 text-xs text-neutral-500 dark:text-neutral-400">
      <span className="inline-flex items-center gap-1">
        <Users className="w-3 h-3" />
        {s.follower_count ?? 0}
      </span>
      {p?.win_rate != null && (
        <span className={cn('font-medium', p.win_rate >= 0.5 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400')}>
          {(p.win_rate * 100).toFixed(0)}% win
        </span>
      )}
      {p?.avg_return_pct != null && (
        <span className="inline-flex items-center gap-1">
          <TrendingUp className="w-3 h-3" />
          {p.avg_return_pct.toFixed(1)}%/trade
        </span>
      )}
      <span className={cn(
        'text-[10px] px-1.5 py-0.5 rounded-full',
        p?.paper === false
          ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400'
          : 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
      )}>
        {p?.paper === false ? 'LIVE' : 'PAPER'}
      </span>
    </div>
  );
}

function StrategyCard({ s }: { s: StrategySummary }) {
  return (
    <Link
      to={`/strategies/${s.slug}`}
      className="block bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4 hover:border-blue-300 dark:hover:border-blue-700 transition-colors"
    >
      <div className="flex items-start justify-between mb-1">
        <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">{s.name}</h3>
        <span className="text-[10px] text-neutral-400 uppercase">{s.kind}</span>
      </div>
      <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-3 line-clamp-2 min-h-[2rem]">
        {s.description || 'No description provided.'}
      </p>
      <PerfBadges s={s} />
    </Link>
  );
}

function CreateStrategyForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [visibility, setVisibility] = useState('private');
  const [disclosure, setDisclosure] = useState('');
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => strategiesApi.create({ name, description, visibility, disclosure: disclosure || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      onDone();
    },
    onError: (e: any) => setError(e?.response?.data?.detail || e?.response?.data?.message || 'Failed to create strategy'),
  });

  return (
    <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4 space-y-3">
      <input
        value={name}
        onChange={e => setName(e.target.value)}
        placeholder="Strategy name (e.g. Dividend Momentum)"
        className="w-full px-3 py-2 text-sm bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-lg text-neutral-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <textarea
        value={description}
        onChange={e => setDescription(e.target.value)}
        placeholder="What does this strategy do, and why?"
        rows={2}
        className="w-full px-3 py-2 text-sm bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-lg text-neutral-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <div className="flex items-center gap-2">
        {['private', 'unlisted', 'public'].map(v => (
          <button
            key={v}
            onClick={() => setVisibility(v)}
            className={cn(
              'px-3 py-1.5 text-xs rounded-lg border transition-colors capitalize',
              visibility === v
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white dark:bg-neutral-900 text-neutral-600 dark:text-neutral-300 border-neutral-200 dark:border-neutral-700'
            )}
          >
            {v}
          </button>
        ))}
      </div>
      {visibility === 'public' && (
        <textarea
          value={disclosure}
          onChange={e => setDisclosure(e.target.value)}
          placeholder="Required disclosure: state your conflicts of interest (e.g. 'I hold positions in stocks this strategy trades')."
          rows={2}
          className="w-full px-3 py-2 text-sm bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-lg text-neutral-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
      )}
      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          onClick={() => create.mutate()}
          disabled={create.isLoading || name.trim().length < 3}
          className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
        >
          {create.isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Create Strategy'}
        </button>
        <button onClick={onDone} className="px-3 py-1.5 text-xs text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300">
          Cancel
        </button>
      </div>
    </div>
  );
}

const StrategiesPage: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [showCreate, setShowCreate] = useState(false);
  const discover = useQuery({ queryKey: ['strategies', 'public'], queryFn: () => strategiesApi.discover() });
  const mine = useQuery({
    queryKey: ['strategies', 'mine'],
    queryFn: () => strategiesApi.mine(),
    enabled: isAuthenticated,
  });

  return (
    <div className="max-w-[1200px] mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-neutral-900 dark:text-white">Strategies</h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            Follow strategies with verified, broker-fill track records
          </p>
        </div>
        {isAuthenticated && (
          <button
            onClick={() => setShowCreate(v => !v)}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
          >
            <Plus className="w-4 h-4" />
            New Strategy
          </button>
        )}
      </div>

      <Disclaimer />

      {showCreate && <CreateStrategyForm onDone={() => setShowCreate(false)} />}

      {isAuthenticated && (mine.data?.strategies?.length ?? 0) > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">My Strategies</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {mine.data!.strategies.map(s => <StrategyCard key={s.id} s={s} />)}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">Discover</h2>
        {discover.isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[1, 2, 3].map(i => <div key={i} className="h-32 bg-neutral-100 dark:bg-neutral-800 rounded-xl animate-pulse" />)}
          </div>
        ) : (discover.data?.strategies?.length ?? 0) === 0 ? (
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            No public strategies yet: be the first to publish one.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {discover.data!.strategies.map(s => <StrategyCard key={s.id} s={s} />)}
          </div>
        )}
      </div>
    </div>
  );
};

export default StrategiesPage;
