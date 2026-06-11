/**
 * Consolidated Rankings — every brain, one list.
 * Signal consensus (track-record-weighted) + AI Desk verdict + quant
 * recommendation blended into a single explainable stance per ticker.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Layers } from 'lucide-react';
import apiClient from '../api/client';
import { cn } from '../utils/format';

interface RankingWhySignal {
  signal_type: string;
  source: string;
  direction: string;
  contribution: number;
  source_win_rate: number | null;
}

interface Ranking {
  ticker: string;
  composite: number | null;
  stance: string;
  components: { signals: number | null; desk: number | null; recommendation: number | null };
  why: {
    signals?: RankingWhySignal[];
    desk?: { decision: string; conviction: number; as_of_date: string };
    recommendation?: { action: string; score: number };
  };
}

interface RankingsResponse {
  generated_at: string;
  rankings: Ranking[];
  disclaimer: string;
}

const STANCE_STYLES: Record<string, string> = {
  'strongly bullish': 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
  bullish: 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400',
  neutral: 'bg-neutral-100 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-300',
  bearish: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
  'strongly bearish': 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
};

function whyLine(r: Ranking): string {
  const parts: string[] = [];
  if (r.why.desk) parts.push(`Desk: ${r.why.desk.decision} (${Math.round(r.why.desk.conviction * 100)}%)`);
  const topSig = r.why.signals?.[0];
  if (topSig) {
    const wr = topSig.source_win_rate != null ? ` · ${Math.round(topSig.source_win_rate * 100)}% win` : '';
    parts.push(`${topSig.signal_type} (${topSig.source}${wr})`);
  }
  if (r.why.recommendation) parts.push(`Quant: ${r.why.recommendation.action}`);
  return parts.join('  ·  ') || 'No active voices';
}

const ConsolidatedRankings: React.FC = () => {
  const rankings = useQuery({
    queryKey: ['consolidated', 'rankings'],
    queryFn: async (): Promise<RankingsResponse> => (await apiClient.get('/consolidated/rankings?limit=10')).data,
    refetchInterval: 120_000,
  });

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-lg font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
          <Layers className="w-5 h-5 text-indigo-600" />
          Consolidated Rankings
        </h2>
        <span className="text-[10px] text-neutral-400">signals × desk × quant, weighted by verified records</span>
      </div>
      <p className="text-[10px] text-neutral-400 mb-3">Market stance, not investment advice.</p>

      {rankings.isLoading ? (
        <div className="h-24 bg-neutral-100 dark:bg-neutral-800 rounded-lg animate-pulse" />
      ) : rankings.error || !rankings.data?.rankings?.length ? (
        <p className="text-sm text-neutral-500 dark:text-neutral-400 py-4 text-center">
          No consolidated view yet — voices appear as signals, desk runs, and recommendations land.
        </p>
      ) : (
        <div className="space-y-1.5">
          {rankings.data.rankings.map((r, i) => (
            <div
              key={r.ticker}
              className="flex items-center gap-3 px-2 py-1.5 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-800/60"
            >
              <span className="text-[10px] text-neutral-400 w-4 text-right shrink-0">{i + 1}</span>
              <Link
                to={`/stocks/${r.ticker}`}
                className="font-semibold text-blue-600 dark:text-blue-400 hover:underline w-14 shrink-0"
              >
                {r.ticker}
              </Link>
              <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0 capitalize', STANCE_STYLES[r.stance] || STANCE_STYLES.neutral)}>
                {r.stance}
              </span>
              <span className="text-xs tabular-nums text-neutral-500 dark:text-neutral-400 w-12 shrink-0">
                {r.composite != null ? (r.composite > 0 ? '+' : '') + r.composite.toFixed(2) : '—'}
              </span>
              <span className="text-[11px] text-neutral-400 dark:text-neutral-500 truncate">{whyLine(r)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ConsolidatedRankings;
