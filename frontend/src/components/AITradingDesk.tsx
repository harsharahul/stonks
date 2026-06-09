import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Brain, ChevronRight, Briefcase, MessageSquare, Newspaper,
  TrendingUp, Activity, AlertTriangle, Sparkles, Clock,
} from 'lucide-react';

import { useDeskUniverse, useDeskForTicker } from '../hooks/useAITradingDesk';
import type { DeskBrief, DeskDecisionRow, DeskUniverseRow } from '../api/desk';
import TradeTicket from './broker/TradeTicket';
import { cn, formatRelativeTime } from '../utils/format';

// ---------------------------------------------------------------------------
// Decision color palette — BUY=emerald, HOLD=neutral, SELL=red, etc.
// ---------------------------------------------------------------------------

type DecisionTone = 'buy' | 'hold' | 'sell';

function classifyDecision(decision: string | null | undefined): DecisionTone {
  const v = (decision || '').toLowerCase();
  if (v.includes('buy') || v.includes('overweight')) return 'buy';
  if (v.includes('sell') || v.includes('underweight')) return 'sell';
  return 'hold';
}

const TONE_BG: Record<DecisionTone, string> = {
  buy: 'bg-emerald-600 text-white',
  hold: 'bg-neutral-600 text-white',
  sell: 'bg-red-700 text-white',
};

const TONE_RING: Record<DecisionTone, string> = {
  buy: 'ring-emerald-500/40',
  hold: 'ring-neutral-500/40',
  sell: 'ring-red-500/40',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function pct(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${(n * 100).toFixed(1)}%`;
}

function tokenize(text: string | null | undefined, maxLines = 8): string[] {
  if (!text) return [];
  const lines = text.split('\n').filter(l => l.trim().length > 0);
  return lines.slice(0, maxLines);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const UniverseRail: React.FC<{
  rows: DeskUniverseRow[] | undefined;
  loading: boolean;
  selected: string | null;
  onSelect: (ticker: string) => void;
}> = ({ rows, loading, selected, onSelect }) => {
  if (loading) {
    return (
      <div className="h-full overflow-y-auto p-3 space-y-2">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-12 rounded-md bg-neutral-100 dark:bg-neutral-800 animate-pulse" />
        ))}
      </div>
    );
  }
  if (!rows || rows.length === 0) {
    return (
      <div className="h-full p-4 text-sm text-neutral-600 dark:text-neutral-400">
        Universe empty. Run the nightly batch (or kick off
        <code className="px-1 bg-neutral-100 dark:bg-neutral-800 mx-1 rounded">
          run_desk_for_ticker_task
        </code>
        manually).
      </div>
    );
  }
  return (
    <div className="h-full overflow-y-auto p-3 space-y-1.5">
      {rows.map((row) => {
        const dec = row.latest_decision;
        const tone = classifyDecision(dec?.decision);
        const isSelected = selected?.toUpperCase() === row.ticker.toUpperCase();
        return (
          <button
            key={row.ticker}
            onClick={() => onSelect(row.ticker)}
            className={cn(
              'w-full text-left px-3 py-2 rounded-md transition-colors',
              'border border-transparent',
              isSelected
                ? 'bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900 border-neutral-900 dark:border-neutral-100'
                : 'hover:bg-neutral-100 dark:hover:bg-neutral-800',
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="font-mono text-sm font-semibold tracking-wide">
                {row.ticker}
              </div>
              {dec ? (
                <span
                  className={cn(
                    'text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded font-semibold',
                    TONE_BG[tone],
                  )}
                >
                  {dec.decision}
                </span>
              ) : (
                <span className="text-[10px] uppercase tracking-wider text-neutral-400">
                  pending
                </span>
              )}
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px] opacity-70">
              <span>{row.reason.replace('_', ' ')}</span>
              <span>
                {dec
                  ? `conv ${(Number(dec.conviction) * 100).toFixed(0)}%`
                  : row.score !== null
                  ? `score ${row.score.toFixed(2)}`
                  : ''}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
};

const DecisionHeader: React.FC<{ decision: DeskDecisionRow; runStartedAt: string | null }> = ({
  decision,
  runStartedAt,
}) => {
  const tone = classifyDecision(decision.decision);
  const conviction = Number(decision.conviction || 0);
  const [tradeOpen, setTradeOpen] = useState(false);
  return (
    <div
      className={cn(
        'rounded-lg border bg-white dark:bg-neutral-900 ring-1',
        'border-neutral-200 dark:border-neutral-800',
        TONE_RING[tone],
        'p-5 sm:p-6',
      )}
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-baseline gap-3">
            <h2 className="font-mono text-2xl sm:text-3xl font-bold tracking-tight">
              {decision.ticker}
            </h2>
            <span className="text-xs uppercase tracking-wider text-neutral-500">
              {decision.as_of_date}
            </span>
          </div>
          <div className="mt-2 flex items-center gap-3">
            <span
              className={cn(
                'text-sm font-bold uppercase tracking-wider px-3 py-1 rounded',
                TONE_BG[tone],
              )}
            >
              {decision.decision}
            </span>
            {decision.horizon_days ? (
              <span className="text-xs text-neutral-500 inline-flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {decision.horizon_days}d horizon
              </span>
            ) : null}
            {runStartedAt ? (
              <span className="text-xs text-neutral-500">
                {formatRelativeTime(runStartedAt)}
              </span>
            ) : null}
          </div>
        </div>
        <div className="text-right min-w-[180px]">
          <div className="flex items-center justify-end gap-2 mb-2">
            <button
              onClick={() => setTradeOpen(true)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-bold text-xs uppercase tracking-wider text-white transition-colors',
                tone === 'sell' ? 'bg-red-700 hover:bg-red-800' : 'bg-emerald-600 hover:bg-emerald-700',
              )}
            >
              <Sparkles className="w-3.5 h-3.5" /> Trade
            </button>
          </div>
          <div className="text-xs uppercase tracking-wider text-neutral-500 mb-1">Conviction</div>
          <div className="font-mono text-lg font-semibold">
            {(conviction * 100).toFixed(0)}%
          </div>
          <div className="mt-2 h-2 rounded bg-neutral-200 dark:bg-neutral-800 overflow-hidden">
            <div
              className={cn(
                'h-full rounded',
                tone === 'buy'
                  ? 'bg-gradient-to-r from-emerald-400 to-emerald-600'
                  : tone === 'sell'
                  ? 'bg-gradient-to-r from-red-400 to-red-700'
                  : 'bg-gradient-to-r from-neutral-400 to-neutral-600',
              )}
              style={{ width: `${Math.min(100, Math.max(0, conviction * 100))}%` }}
            />
          </div>
        </div>
      </div>
      {decision.thesis_text ? (
        <div className="mt-5 prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap font-mono text-[13px] leading-relaxed text-neutral-700 dark:text-neutral-300">
          {decision.thesis_text.split('\n').slice(0, 12).join('\n')}
        </div>
      ) : null}
      <TradeTicket
        symbol={decision.ticker}
        open={tradeOpen}
        onClose={() => setTradeOpen(false)}
        source="desk"
        sourceRef={decision.id}
        initialSide={tone === 'sell' ? 'sell' : 'buy'}
      />
    </div>
  );
};

const AGENT_META: Record<string, { label: string; icon: React.ReactNode; accent: string }> = {
  fundamentals: {
    label: 'Fundamentals',
    icon: <Briefcase className="w-4 h-4" />,
    accent: 'border-blue-500/30 dark:border-blue-400/30',
  },
  social: {
    label: 'Sentiment',
    icon: <MessageSquare className="w-4 h-4" />,
    accent: 'border-amber-500/30 dark:border-amber-400/30',
  },
  news: {
    label: 'News & Catalysts',
    icon: <Newspaper className="w-4 h-4" />,
    accent: 'border-violet-500/30 dark:border-violet-400/30',
  },
  market: {
    label: 'Technical',
    icon: <TrendingUp className="w-4 h-4" />,
    accent: 'border-teal-500/30 dark:border-teal-400/30',
  },
};

const AgentCard: React.FC<{ brief: DeskBrief }> = ({ brief }) => {
  const meta = AGENT_META[brief.agent_name] || {
    label: brief.agent_name,
    icon: <Activity className="w-4 h-4" />,
    accent: 'border-neutral-500/30',
  };
  const lines = tokenize(brief.output_text, 14);
  return (
    <div
      className={cn(
        'rounded-lg border bg-white dark:bg-neutral-900 p-4',
        meta.accent,
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {meta.icon}
          <h3 className="text-sm font-semibold uppercase tracking-wider">{meta.label}</h3>
        </div>
        {brief.conviction !== null && brief.conviction !== undefined ? (
          <span className="text-[11px] text-neutral-500">
            conv {(Number(brief.conviction) * 100).toFixed(0)}%
          </span>
        ) : null}
      </div>
      <div className="font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-neutral-700 dark:text-neutral-300">
        {lines.join('\n')}
        {brief.output_text && brief.output_text.split('\n').filter(l => l.trim()).length > 14 ? (
          <span className="text-neutral-400">  …</span>
        ) : null}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const AITradingDesk: React.FC = () => {
  const navigate = useNavigate();
  const params = useParams<{ ticker?: string }>();
  const universe = useDeskUniverse();

  // Auto-select the highest-score ticker when no path param is given.
  const initialFromUniverse = useMemo(() => {
    if (params.ticker) return params.ticker.toUpperCase();
    const rows = universe.data?.tickers;
    if (!rows || rows.length === 0) return null;
    return rows[0].ticker;
  }, [params.ticker, universe.data]);

  const [selected, setSelected] = useState<string | null>(initialFromUniverse);
  useEffect(() => {
    if (!selected && initialFromUniverse) setSelected(initialFromUniverse);
  }, [initialFromUniverse, selected]);

  const ticker = selected;
  const desk = useDeskForTicker(ticker);

  const onSelect = (t: string) => {
    setSelected(t.toUpperCase());
    navigate(`/desk/${t.toUpperCase()}`, { replace: true });
  };

  const briefs = desk.data?.briefs ?? [];
  const analystBriefs = briefs.filter(b =>
    ['fundamentals', 'social', 'news', 'market'].includes(b.agent_name),
  );
  const traderBrief = briefs.find(b => b.agent_name === 'trader');
  const pmBrief = briefs.find(b => b.agent_name === 'portfolio_manager');

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col lg:flex-row gap-3 p-3">
      {/* Universe rail */}
      <aside className="lg:w-72 flex-shrink-0 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-800 flex items-center gap-2">
          <Brain className="w-4 h-4" />
          <h2 className="text-sm font-semibold uppercase tracking-wider">AI Trading Desk</h2>
        </div>
        <UniverseRail
          rows={universe.data?.tickers}
          loading={universe.isLoading}
          selected={ticker}
          onSelect={onSelect}
        />
      </aside>

      {/* Main pane */}
      <main className="flex-1 overflow-y-auto space-y-4">
        {!ticker ? (
          <div className="h-full flex items-center justify-center text-neutral-500">
            <div className="text-center">
              <Brain className="w-10 h-10 mx-auto mb-2 opacity-30" />
              <p>Select a ticker from the universe rail to see the desk's verdict.</p>
            </div>
          </div>
        ) : desk.isLoading ? (
          <div className="rounded-lg border border-neutral-200 dark:border-neutral-800 p-6 animate-pulse">
            <div className="h-6 w-40 bg-neutral-200 dark:bg-neutral-700 rounded mb-3" />
            <div className="h-4 w-60 bg-neutral-200 dark:bg-neutral-700 rounded" />
          </div>
        ) : desk.isError || !desk.data ? (
          <div className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950 p-5 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5" />
            <div>
              <p className="text-sm font-semibold">No desk decision yet for {ticker}.</p>
              <p className="text-sm text-neutral-700 dark:text-neutral-300 mt-1">
                The desk pipeline runs nightly at 7:15 UTC. To trigger a manual run, kick off
                the <code className="px-1 bg-neutral-100 dark:bg-neutral-800 rounded">run_desk_for_ticker_task</code>{' '}
                Celery task.
              </p>
            </div>
          </div>
        ) : (
          <>
            <DecisionHeader
              decision={desk.data.decision}
              runStartedAt={desk.data.run?.run_started_at ?? null}
            />

            {analystBriefs.length > 0 && (
              <section>
                <h3 className="text-xs uppercase tracking-wider text-neutral-500 mb-2 px-1">
                  Analyst desk
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {analystBriefs.map(b => (
                    <AgentCard key={b.id} brief={b} />
                  ))}
                </div>
              </section>
            )}

            {(traderBrief || pmBrief) && (
              <section>
                <h3 className="text-xs uppercase tracking-wider text-neutral-500 mb-2 px-1">
                  Trader & portfolio manager
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {traderBrief && (
                    <div className="rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Sparkles className="w-4 h-4" />
                        <h4 className="text-sm font-semibold uppercase tracking-wider">
                          Trader plan
                        </h4>
                      </div>
                      <div className="font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-neutral-700 dark:text-neutral-300">
                        {tokenize(traderBrief.output_text, 14).join('\n')}
                      </div>
                    </div>
                  )}
                  {pmBrief && (
                    <div className="rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <ChevronRight className="w-4 h-4" />
                        <h4 className="text-sm font-semibold uppercase tracking-wider">
                          Portfolio manager
                        </h4>
                      </div>
                      <div className="font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-neutral-700 dark:text-neutral-300">
                        {tokenize(pmBrief.output_text, 14).join('\n')}
                      </div>
                    </div>
                  )}
                </div>
              </section>
            )}

            {desk.data.outcome ? (
              <section>
                <h3 className="text-xs uppercase tracking-wider text-neutral-500 mb-2 px-1">
                  Outcome (vs SPY)
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <Stat label="Realized 5d" value={pct(desk.data.outcome.realized_return_5d)} />
                  <Stat label="Alpha 5d" value={pct(desk.data.outcome.alpha_5d)} />
                  <Stat label="Realized 30d" value={pct(desk.data.outcome.realized_return_30d)} />
                  <Stat label="Alpha 30d" value={pct(desk.data.outcome.alpha_30d)} />
                </div>
              </section>
            ) : null}
          </>
        )}
      </main>
    </div>
  );
};

const Stat: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-3">
    <div className="text-[11px] uppercase tracking-wider text-neutral-500">{label}</div>
    <div className="mt-1 font-mono text-base font-semibold">{value}</div>
  </div>
);

export default AITradingDesk;
