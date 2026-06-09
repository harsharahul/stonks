import React, { useState } from 'react';
import {
  Briefcase, Link2, Unlink, RefreshCw, FlaskConical, AlertTriangle,
  TrendingUp, TrendingDown, Loader2, ShieldCheck, XCircle,
} from 'lucide-react';

import {
  useBrokerAccount, useLinkAccount, useUnlinkAccount,
  usePositions, useOrders, useCancelOrder,
} from '../../hooks/useBroker';
import TradeTicket from './TradeTicket';
import { cn } from '../../utils/format';

const fmtUsd = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

const fmtPct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(2)}%`;

// ---------------------------------------------------------------------------
// Link form
// ---------------------------------------------------------------------------

const LinkBrokerCard: React.FC = () => {
  const link = useLinkAccount();
  const [apiKey, setApiKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [paper, setPaper] = useState(true);
  const [confirmLive, setConfirmLive] = useState(false);

  const canLink = apiKey.length >= 8 && secretKey.length >= 8 && (paper || confirmLive) && !link.isLoading;

  return (
    <div className="max-w-lg mx-auto rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-6">
      <div className="flex items-center gap-2 mb-1">
        <Link2 className="w-5 h-5 text-emerald-600" />
        <h2 className="text-lg font-semibold">Connect your Alpaca account</h2>
      </div>
      <p className="text-sm text-neutral-500 mb-5">
        Trade directly from Stonks. Start with a free{' '}
        <a href="https://alpaca.markets" target="_blank" rel="noreferrer" className="text-emerald-600 underline">
          Alpaca
        </a>{' '}
        paper account — your keys are encrypted at rest and never shown again.
      </p>

      <div className="space-y-3">
        <div>
          <label className="text-xs uppercase tracking-wider text-neutral-500 block mb-1">API Key ID</label>
          <input
            type="password" autoComplete="off" value={apiKey}
            onChange={e => setApiKey(e.target.value.trim())}
            className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent font-mono text-sm"
          />
        </div>
        <div>
          <label className="text-xs uppercase tracking-wider text-neutral-500 block mb-1">Secret Key</label>
          <input
            type="password" autoComplete="off" value={secretKey}
            onChange={e => setSecretKey(e.target.value.trim())}
            className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent font-mono text-sm"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => { setPaper(true); setConfirmLive(false); }}
            className={cn(
              'flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-semibold transition-colors',
              paper ? 'bg-sky-600 text-white' : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-500',
            )}
          >
            <FlaskConical className="w-4 h-4" /> Paper
          </button>
          <button
            onClick={() => setPaper(false)}
            className={cn(
              'flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-semibold transition-colors',
              !paper ? 'bg-red-700 text-white' : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-500',
            )}
          >
            <AlertTriangle className="w-4 h-4" /> Live
          </button>
        </div>

        {!paper && (
          <label className="flex items-start gap-2 text-sm p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 cursor-pointer">
            <input type="checkbox" checked={confirmLive} onChange={e => setConfirmLive(e.target.checked)} className="mt-0.5" />
            <span className="text-red-700 dark:text-red-300">
              I understand this links a <strong>real-money</strong> account.
            </span>
          </label>
        )}

        {link.isError && (
          <p className="text-sm text-red-600">
            {(link.error as any)?.response?.data?.detail || 'Linking failed.'}
          </p>
        )}

        <button
          onClick={() => link.mutate({ api_key: apiKey, secret_key: secretKey, paper, confirm_live: confirmLive })}
          disabled={!canLink}
          className={cn(
            'w-full py-2.5 rounded-lg font-bold text-sm uppercase tracking-wider bg-emerald-600 hover:bg-emerald-700 text-white transition-colors flex items-center justify-center gap-2',
            !canLink && 'opacity-40 cursor-not-allowed',
          )}
        >
          {link.isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
          Connect account
        </button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Portfolio page
// ---------------------------------------------------------------------------

const PortfolioPage: React.FC = () => {
  const account = useBrokerAccount();
  const isLinked = Boolean(account.data?.broker_info);
  const positions = usePositions(isLinked);
  const orders = useOrders(isLinked);
  const unlink = useUnlinkAccount();
  const cancelOrder = useCancelOrder();
  const [ticketSymbol, setTicketSymbol] = useState<string | null>(null);
  const [ticketSide, setTicketSide] = useState<'buy' | 'sell'>('buy');

  const notLinked = account.isError && (account.error as any)?.response?.status === 404;

  if (account.isLoading) {
    return (
      <div className="max-w-5xl mx-auto p-6">
        <div className="h-32 rounded-xl bg-neutral-100 dark:bg-neutral-800 animate-pulse" />
      </div>
    );
  }

  if (notLinked || !account.data) {
    return (
      <div className="max-w-5xl mx-auto p-6 pt-12">
        <LinkBrokerCard />
      </div>
    );
  }

  const info = account.data.broker_info;
  const acct = account.data.account;

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Briefcase className="w-6 h-6" />
          <h1 className="text-xl font-bold">Portfolio</h1>
          {acct.paper ? (
            <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
              <FlaskConical className="w-3 h-3" /> Paper {acct.account_label || ''}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300">
              <AlertTriangle className="w-3 h-3" /> Live {acct.account_label || ''}
            </span>
          )}
          {account.data.market_open !== null && (
            <span className={cn('text-[11px] uppercase tracking-wider', account.data.market_open ? 'text-emerald-600' : 'text-neutral-500')}>
              {account.data.market_open ? '● market open' : '○ market closed'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { positions.refetch(); orders.refetch(); account.refetch(); }}
            className="p-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800"
            title="Refresh"
          >
            <RefreshCw className={cn('w-4 h-4', (positions.isFetching || orders.isFetching) && 'animate-spin')} />
          </button>
          <button
            onClick={() => { if (window.confirm('Unlink your Alpaca account? Order history is preserved.')) unlink.mutate(); }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-neutral-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
          >
            <Unlink className="w-3.5 h-3.5" /> Unlink
          </button>
        </div>
      </div>

      {/* Account stats */}
      {info ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Equity', value: fmtUsd(info.equity) },
            { label: 'Cash', value: fmtUsd(info.cash) },
            { label: 'Buying power', value: fmtUsd(info.buying_power) },
            { label: 'Portfolio value', value: fmtUsd(info.portfolio_value) },
          ].map(s => (
            <div key={s.label} className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4">
              <div className="text-[11px] uppercase tracking-wider text-neutral-500">{s.label}</div>
              <div className="mt-1 font-mono text-xl font-semibold">{s.value}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950 p-4 text-sm flex items-center gap-2">
          <XCircle className="w-4 h-4 text-amber-600" />
          Credentials no longer valid or Alpaca unreachable — re-link your account.
        </div>
      )}

      {/* Positions */}
      <section className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-800 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4" />
          <h2 className="text-sm font-semibold uppercase tracking-wider">Positions</h2>
          <span className="text-xs text-neutral-500">({positions.data?.count ?? 0})</span>
        </div>
        {positions.data && positions.data.positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-neutral-500 border-b border-neutral-200 dark:border-neutral-800">
                  <th className="px-4 py-2">Symbol</th>
                  <th className="px-4 py-2 text-right">Qty</th>
                  <th className="px-4 py-2 text-right">Avg entry</th>
                  <th className="px-4 py-2 text-right">Last</th>
                  <th className="px-4 py-2 text-right">Value</th>
                  <th className="px-4 py-2 text-right">P/L</th>
                  <th className="px-4 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {positions.data.positions.map(p => (
                  <tr key={p.symbol} className="border-b border-neutral-100 dark:border-neutral-800/50 hover:bg-neutral-50 dark:hover:bg-neutral-800/40">
                    <td className="px-4 py-2.5 font-mono font-semibold">{p.symbol}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{p.qty}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{fmtUsd(p.avg_entry_price)}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{fmtUsd(p.current_price)}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{fmtUsd(p.market_value)}</td>
                    <td className={cn('px-4 py-2.5 text-right font-mono', (p.unrealized_pl ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-600')}>
                      {fmtUsd(p.unrealized_pl)} ({fmtPct(p.unrealized_plpc)})
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="inline-flex gap-1">
                        <button
                          onClick={() => { setTicketSymbol(p.symbol); setTicketSide('buy'); }}
                          className="p-1.5 rounded hover:bg-emerald-50 dark:hover:bg-emerald-950/40 text-emerald-600" title={`Buy ${p.symbol}`}
                        >
                          <TrendingUp className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => { setTicketSymbol(p.symbol); setTicketSide('sell'); }}
                          className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-950/40 text-red-600" title={`Sell ${p.symbol}`}
                        >
                          <TrendingDown className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-4 py-8 text-center text-sm text-neutral-500">
            No open positions. Find a stock and hit Trade.
          </div>
        )}
      </section>

      {/* Orders */}
      <section className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-800">
          <h2 className="text-sm font-semibold uppercase tracking-wider">Order history</h2>
        </div>
        {orders.data && orders.data.orders.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-neutral-500 border-b border-neutral-200 dark:border-neutral-800">
                  <th className="px-4 py-2">When</th>
                  <th className="px-4 py-2">Symbol</th>
                  <th className="px-4 py-2">Side</th>
                  <th className="px-4 py-2 text-right">Qty / $</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Source</th>
                  <th className="px-4 py-2 text-right" />
                </tr>
              </thead>
              <tbody>
                {orders.data.orders.map(o => {
                  const cancellable = ['submitted', 'accepted', 'new', 'pending'].includes(o.status);
                  return (
                    <tr key={o.id} className="border-b border-neutral-100 dark:border-neutral-800/50">
                      <td className="px-4 py-2 text-xs text-neutral-500">
                        {o.created_at ? new Date(o.created_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-2 font-mono font-semibold">{o.symbol}</td>
                      <td className={cn('px-4 py-2 font-semibold uppercase text-xs', o.side === 'buy' ? 'text-emerald-600' : 'text-red-600')}>
                        {o.side}
                      </td>
                      <td className="px-4 py-2 text-right font-mono">
                        {o.qty ?? (o.notional ? fmtUsd(o.notional) : '—')}
                        {o.filled_avg_price ? ` @ ${fmtUsd(o.filled_avg_price)}` : ''}
                      </td>
                      <td className="px-4 py-2 text-xs">{o.order_type}{o.limit_price ? ` ${fmtUsd(o.limit_price)}` : ''}</td>
                      <td className="px-4 py-2">
                        <span className={cn(
                          'text-[10px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded',
                          o.status === 'filled' && 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
                          ['canceled', 'rejected', 'failed'].includes(o.status) && 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
                          !['filled', 'canceled', 'rejected', 'failed'].includes(o.status) && 'bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300',
                        )}>
                          {o.status}
                        </span>
                        {o.error && <span className="block text-[10px] text-red-500 mt-0.5 max-w-[200px] truncate" title={o.error}>{o.error}</span>}
                      </td>
                      <td className="px-4 py-2 text-xs text-neutral-500">{o.source}</td>
                      <td className="px-4 py-2 text-right">
                        {cancellable && o.alpaca_order_id && (
                          <button
                            onClick={() => cancelOrder.mutate(o.id)}
                            className="text-xs text-neutral-500 hover:text-red-600"
                          >
                            cancel
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-4 py-8 text-center text-sm text-neutral-500">No orders yet.</div>
        )}
      </section>

      {ticketSymbol && (
        <TradeTicket
          symbol={ticketSymbol}
          open={Boolean(ticketSymbol)}
          onClose={() => setTicketSymbol(null)}
          initialSide={ticketSide}
        />
      )}
    </div>
  );
};

export default PortfolioPage;
