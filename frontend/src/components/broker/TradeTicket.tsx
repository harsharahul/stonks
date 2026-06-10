import React, { useEffect, useMemo, useState } from 'react';
import { X, TrendingUp, TrendingDown, AlertTriangle, Loader2, CheckCircle2, FlaskConical } from 'lucide-react';

import { useBrokerAccount, usePlaceOrder, useSizing } from '../../hooks/useBroker';
import { cn } from '../../utils/format';

interface TradeTicketProps {
  symbol: string;
  open: boolean;
  onClose: () => void;
  /** Provenance for the order ledger — e.g. desk decision id */
  source?: 'manual' | 'desk' | 'signal';
  sourceRef?: string;
  /** Optional initial side, e.g. from a desk BUY decision */
  initialSide?: 'buy' | 'sell';
}

/**
 * Trade ticket modal: the moment Stonks becomes actionable.
 * Paper accounts get a visible PAPER badge; live accounts require an extra
 * explicit confirmation checkbox before the submit button arms.
 */
const TradeTicket: React.FC<TradeTicketProps> = ({
  symbol, open, onClose, source = 'manual', sourceRef, initialSide = 'buy',
}) => {
  const account = useBrokerAccount();
  const placeOrder = usePlaceOrder();
  const [side, setSide] = useState<'buy' | 'sell'>(initialSide);
  const [mode, setMode] = useState<'qty' | 'notional'>('qty');
  const [qty, setQty] = useState<string>('');
  const [notional, setNotional] = useState<string>('');
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market');
  const [limitPrice, setLimitPrice] = useState<string>('');
  const [useBracket, setUseBracket] = useState(false);
  const [stopLoss, setStopLoss] = useState<string>('');
  const [takeProfit, setTakeProfit] = useState<string>('');
  const [liveConfirmed, setLiveConfirmed] = useState(false);

  const sizing = useSizing(symbol, open && Boolean(account.data?.broker_info));

  useEffect(() => {
    if (open) {
      setSide(initialSide);
      placeOrder.reset();
      setLiveConfirmed(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, symbol, initialSide]);

  // Escape closes the ticket (standard modal behavior)
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // Pre-fill suggested sizing once it arrives (only if user hasn't typed)
  useEffect(() => {
    if (sizing.data && !qty) {
      setQty(String(sizing.data.suggested_qty || ''));
      setStopLoss(String(sizing.data.suggested_stop_loss || ''));
      setTakeProfit(String(sizing.data.suggested_take_profit || ''));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sizing.data]);

  const isPaper = account.data?.account?.paper ?? true;
  const isLinked = Boolean(account.data?.broker_info);
  const tradingHalted = account.data?.trading_halted ?? false;

  const estValue = useMemo(() => {
    const p = sizing.data?.entry_price;
    if (mode === 'notional') return parseFloat(notional) || 0;
    if (!p) return 0;
    return (parseFloat(qty) || 0) * p;
  }, [mode, qty, notional, sizing.data]);

  const canSubmit =
    isLinked &&
    !tradingHalted &&
    !placeOrder.isLoading &&
    (mode === 'qty' ? parseFloat(qty) > 0 : parseFloat(notional) > 0) &&
    (orderType === 'market' || parseFloat(limitPrice) > 0) &&
    (isPaper || liveConfirmed);

  const submit = () => {
    if (!canSubmit) return;
    placeOrder.mutate({
      symbol,
      side,
      qty: mode === 'qty' ? parseFloat(qty) : undefined,
      notional: mode === 'notional' ? parseFloat(notional) : undefined,
      order_type: orderType,
      limit_price: orderType === 'limit' ? parseFloat(limitPrice) : undefined,
      stop_loss_price: useBracket && mode === 'qty' && parseFloat(stopLoss) > 0 ? parseFloat(stopLoss) : undefined,
      take_profit_price: useBracket && mode === 'qty' && parseFloat(takeProfit) > 0 ? parseFloat(takeProfit) : undefined,
      source,
      source_ref: sourceRef,
      confirm_live: !isPaper,
    });
  };

  if (!open) return null;

  const placed = placeOrder.isSuccess ? placeOrder.data?.order : null;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center gap-3">
            <h2 className="font-mono text-lg font-bold tracking-tight">{symbol}</h2>
            {isPaper ? (
              <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
                <FlaskConical className="w-3 h-3" /> Paper
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300">
                <AlertTriangle className="w-3 h-3" /> Live
              </span>
            )}
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {!isLinked ? (
            <div className="text-sm text-neutral-600 dark:text-neutral-400">
              No brokerage linked yet. Head to{' '}
              <a href="/portfolio" className="text-emerald-600 underline">Portfolio</a>{' '}
              to connect your Alpaca account (paper recommended).
            </div>
          ) : placed ? (
            <div className="text-center py-6">
              <CheckCircle2 className="w-10 h-10 mx-auto text-emerald-500 mb-3" />
              <p className="font-semibold">
                {placed.side.toUpperCase()} {placed.symbol} {placed.status === 'filled' ? 'filled' : 'submitted'}
              </p>
              <p className="text-sm text-neutral-500 mt-1 font-mono">
                status: {placed.status}
                {placed.filled_avg_price ? ` @ $${placed.filled_avg_price.toFixed(2)}` : ''}
              </p>
              {placeOrder.data && placeOrder.data.market_open === false && (
                <p className="text-xs text-amber-600 mt-2">Market closed — order queues for next open.</p>
              )}
            </div>
          ) : (
            <>
              {/* Side toggle */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setSide('buy')}
                  className={cn(
                    'flex items-center justify-center gap-2 py-2.5 rounded-lg font-bold text-sm uppercase tracking-wider transition-colors',
                    side === 'buy'
                      ? 'bg-emerald-600 text-white'
                      : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-500 hover:text-emerald-600',
                  )}
                >
                  <TrendingUp className="w-4 h-4" /> Buy
                </button>
                <button
                  onClick={() => setSide('sell')}
                  className={cn(
                    'flex items-center justify-center gap-2 py-2.5 rounded-lg font-bold text-sm uppercase tracking-wider transition-colors',
                    side === 'sell'
                      ? 'bg-red-700 text-white'
                      : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-500 hover:text-red-600',
                  )}
                >
                  <TrendingDown className="w-4 h-4" /> Sell
                </button>
              </div>

              {/* Qty / notional */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs uppercase tracking-wider text-neutral-500">
                    {mode === 'qty' ? 'Shares' : 'Dollars'}
                  </label>
                  <button
                    onClick={() => setMode(m => (m === 'qty' ? 'notional' : 'qty'))}
                    className="text-[11px] text-emerald-600 hover:underline"
                  >
                    switch to {mode === 'qty' ? '$ amount' : 'shares'}
                  </button>
                </div>
                {mode === 'qty' ? (
                  <input
                    type="number" min="0" step="1" value={qty}
                    onChange={e => setQty(e.target.value)}
                    placeholder={sizing.data ? `suggested: ${sizing.data.suggested_qty}` : 'qty'}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent font-mono text-sm focus:ring-2 focus:ring-emerald-500 outline-none"
                  />
                ) : (
                  <input
                    type="number" min="0" step="1" value={notional}
                    onChange={e => setNotional(e.target.value)}
                    placeholder="500"
                    className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent font-mono text-sm focus:ring-2 focus:ring-emerald-500 outline-none"
                  />
                )}
                {sizing.data && (
                  <p className="text-[11px] text-neutral-500 mt-1">
                    last ${sizing.data.entry_price.toFixed(2)} · est. value ${estValue.toFixed(0)} · equity $
                    {sizing.data.equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </p>
                )}
              </div>

              {/* Order type */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs uppercase tracking-wider text-neutral-500 block mb-1.5">Type</label>
                  <select
                    value={orderType}
                    onChange={e => setOrderType(e.target.value as 'market' | 'limit')}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-sm"
                  >
                    <option value="market">Market</option>
                    <option value="limit">Limit</option>
                  </select>
                </div>
                {orderType === 'limit' && (
                  <div>
                    <label className="text-xs uppercase tracking-wider text-neutral-500 block mb-1.5">Limit price</label>
                    <input
                      type="number" min="0" step="0.01" value={limitPrice}
                      onChange={e => setLimitPrice(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent font-mono text-sm"
                    />
                  </div>
                )}
              </div>

              {/* Bracket */}
              {mode === 'qty' && (
                <div>
                  <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                    <input type="checkbox" checked={useBracket} onChange={e => setUseBracket(e.target.checked)} />
                    Protect with stop-loss / take-profit
                  </label>
                  {useBracket && (
                    <div className="grid grid-cols-2 gap-3 mt-2">
                      <div>
                        <label className="text-[11px] text-red-600 block mb-1">Stop loss $</label>
                        <input
                          type="number" min="0" step="0.01" value={stopLoss}
                          onChange={e => setStopLoss(e.target.value)}
                          className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent font-mono text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-emerald-600 block mb-1">Take profit $</label>
                        <input
                          type="number" min="0" step="0.01" value={takeProfit}
                          onChange={e => setTakeProfit(e.target.value)}
                          className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent font-mono text-sm"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Live confirmation */}
              {!isPaper && (
                <label className="flex items-start gap-2 text-sm p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 cursor-pointer">
                  <input
                    type="checkbox" checked={liveConfirmed}
                    onChange={e => setLiveConfirmed(e.target.checked)}
                    className="mt-0.5"
                  />
                  <span className="text-red-700 dark:text-red-300">
                    This is a <strong>real-money</strong> account. I confirm this order.
                  </span>
                </label>
              )}

              {tradingHalted && (
                <p className="text-sm text-red-600 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" /> Trading is globally halted by the administrator.
                </p>
              )}

              {placeOrder.isError && (
                <p className="text-sm text-red-600">
                  {(placeOrder.error as any)?.response?.data?.detail || 'Order failed — see order history.'}
                </p>
              )}

              <button
                onClick={submit}
                disabled={!canSubmit}
                className={cn(
                  'w-full py-3 rounded-lg font-bold text-sm uppercase tracking-wider transition-colors flex items-center justify-center gap-2',
                  side === 'buy' ? 'bg-emerald-600 hover:bg-emerald-700 text-white' : 'bg-red-700 hover:bg-red-800 text-white',
                  !canSubmit && 'opacity-40 cursor-not-allowed',
                )}
              >
                {placeOrder.isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                {side === 'buy' ? 'Buy' : 'Sell'} {symbol}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default TradeTicket;
