import React from 'react';
import { format, parseISO } from 'date-fns';
import { cn, formatCurrency } from '../utils/format';
import { classifyCandle, PATTERN_META } from '../utils/candlestickPatterns';
import type { LatestCandleData, DetectedPattern } from '../utils/candlestickPatterns';

// --- Pattern signal explanations ---

const PATTERN_SIGNAL_MAP: Record<string, string> = {
  doji: 'Indecision — watch the next candle for direction. Break above high = bullish, below low = bearish.',
  hammer: 'Buyers rejected lower prices aggressively. A green follow-through candle confirms a potential bottom.',
  inverted_hammer: 'Buying pressure emerging. Confirmation needed — watch for a gap up or strong green candle next.',
  shooting_star: 'Rally rejected at highs. A red follow-through candle below this body confirms distribution.',
  marubozu: 'Strong conviction candle with no wicks. Momentum likely continues in the same direction.',
  bullish_engulfing: 'Complete reversal of prior selling. High reliability — watch for follow-through above this high.',
  bearish_engulfing: 'Sellers overwhelmed buyers. High reliability — a close below this low confirms further downside.',
  piercing_line: 'Buyers reclaimed more than half the prior loss. Moderate reversal signal — needs confirmation.',
  dark_cloud_cover: 'Sellers erased more than half the prior gain. Watch for a red candle next to confirm.',
  morning_star: 'Three-candle bottom reversal. One of the strongest bullish patterns — watch for continued buying.',
  evening_star: 'Three-candle top reversal. One of the strongest bearish patterns — watch for continued selling.',
  three_white_soldiers: 'Sustained buying pressure over three sessions. Strong momentum — pullbacks may be buying opportunities.',
};

// --- Mini candle SVG ---

const MiniCandle: React.FC<{ o: number; h: number; l: number; c: number }> = ({ o, h, l, c }) => {
  const isUp = c >= o;
  const color = isUp ? '#10b981' : '#ef4444';
  const r = h - l || 1;
  const svgH = 72;
  const toY = (v: number) => 4 + ((h - v) / r) * (svgH - 8);

  const bodyTop = toY(Math.max(o, c));
  const bodyBottom = toY(Math.min(o, c));
  const bodyHeight = Math.max(2, bodyBottom - bodyTop);

  return (
    <svg width="36" height={svgH} viewBox={`0 0 36 ${svgH}`} className="shrink-0">
      {/* Wick */}
      <line x1="18" y1={toY(h)} x2="18" y2={toY(l)} stroke={color} strokeWidth="2" />
      {/* Body */}
      <rect
        x="7" y={bodyTop}
        width="22" height={bodyHeight}
        fill={color} rx="2"
      />
    </svg>
  );
};

// --- Indicator helpers ---

function getRsiZone(rsi: number): { label: string; color: string } {
  if (rsi >= 70) return { label: 'Overbought', color: 'text-red-600 dark:text-red-400' };
  if (rsi >= 60) return { label: 'Strong', color: 'text-orange-500 dark:text-orange-400' };
  if (rsi >= 40) return { label: 'Neutral', color: 'text-neutral-500 dark:text-neutral-400' };
  if (rsi >= 30) return { label: 'Weak', color: 'text-blue-500 dark:text-blue-400' };
  return { label: 'Oversold', color: 'text-green-600 dark:text-green-400' };
}

function getMacdStatus(macd: number, signal: number): { label: string; color: string } {
  if (macd > signal) return { label: 'Bullish crossover', color: 'text-green-600 dark:text-green-400' };
  return { label: 'Bearish crossover', color: 'text-red-600 dark:text-red-400' };
}

function getBbPosition(close: number, upper: number, lower: number): { pct: number; label: string; color: string } {
  const range = upper - lower;
  if (range === 0) return { pct: 50, label: 'Mid-band', color: 'text-neutral-500 dark:text-neutral-400' };
  const pct = Math.round(((close - lower) / range) * 100);
  if (pct >= 85) return { pct, label: 'Near upper band', color: 'text-red-500 dark:text-red-400' };
  if (pct >= 60) return { pct, label: 'Upper half', color: 'text-orange-500 dark:text-orange-400' };
  if (pct >= 40) return { pct, label: 'Mid-band', color: 'text-neutral-500 dark:text-neutral-400' };
  if (pct >= 15) return { pct, label: 'Lower half', color: 'text-blue-500 dark:text-blue-400' };
  return { pct, label: 'Near lower band', color: 'text-green-600 dark:text-green-400' };
}

// --- Market read synthesis ---

function generateMarketRead(data: LatestCandleData, candleLabel: string): { text: string; sentiment: 'bullish' | 'bearish' | 'mixed' } {
  const signals: { text: string; bullish: boolean }[] = [];

  // Pattern signals
  const bullishPatterns = data.patterns.filter(p => p.sentiment === 'bullish');
  const bearishPatterns = data.patterns.filter(p => p.sentiment === 'bearish');

  if (bullishPatterns.length > 0) {
    signals.push({ text: bullishPatterns[0].name, bullish: true });
  }
  if (bearishPatterns.length > 0) {
    signals.push({ text: bearishPatterns[0].name, bullish: false });
  }

  // RSI
  if (data.rsi !== null) {
    if (data.rsi >= 70) signals.push({ text: 'overbought RSI', bullish: false });
    else if (data.rsi <= 30) signals.push({ text: 'oversold RSI', bullish: true });
    else signals.push({ text: `neutral RSI (${data.rsi.toFixed(0)})`, bullish: data.rsi >= 50 });
  }

  // MACD
  if (data.macd !== null && data.macdSignal !== null) {
    if (data.macd > data.macdSignal) {
      signals.push({ text: 'bullish MACD crossover', bullish: true });
    } else {
      signals.push({ text: 'bearish MACD crossover', bullish: false });
    }
  }

  // BB position
  if (data.bbUpper !== null && data.bbLower !== null) {
    const bb = getBbPosition(data.close, data.bbUpper, data.bbLower);
    if (bb.pct >= 85) signals.push({ text: 'price near upper Bollinger Band', bullish: false });
    else if (bb.pct <= 15) signals.push({ text: 'price near lower Bollinger Band', bullish: true });
  }

  if (signals.length === 0) {
    return { text: `${candleLabel} candle with insufficient indicator data for a full market read.`, sentiment: 'mixed' };
  }

  const bullishCount = signals.filter(s => s.bullish).length;
  const bearishCount = signals.filter(s => !s.bullish).length;
  const sentiment: 'bullish' | 'bearish' | 'mixed' =
    bullishCount > bearishCount ? 'bullish' :
    bearishCount > bullishCount ? 'bearish' : 'mixed';

  const signalTexts = signals.map(s => s.text);
  const joined = signalTexts.length <= 2
    ? signalTexts.join(' + ')
    : signalTexts.slice(0, -1).join(', ') + ' + ' + signalTexts[signalTexts.length - 1];

  const outlook =
    sentiment === 'bullish' ? 'suggest upward momentum. Watch for follow-through buying in the next session.' :
    sentiment === 'bearish' ? 'suggest downward pressure. Watch for continued selling or support levels.' :
    'present conflicting signals. Wait for confirmation before acting.';

  return { text: `${joined} ${outlook}`, sentiment };
}

// --- Main Component ---

interface LatestCandleInsightProps {
  data: LatestCandleData;
  ticker: string;
  className?: string;
}

const LatestCandleInsight: React.FC<LatestCandleInsightProps> = ({ data, ticker, className }) => {
  const candle = classifyCandle(data.open, data.high, data.low, data.close);
  const isUp = data.close >= data.open;
  const changePct = data.prevClose ? ((data.close - data.prevClose) / data.prevClose * 100) : null;
  const marketRead = generateMarketRead(data, candle.label);

  let dateStr: string;
  try {
    dateStr = format(parseISO(data.date), 'MMM d, yyyy');
  } catch {
    dateStr = data.date;
  }

  const sentimentBorderColor =
    marketRead.sentiment === 'bullish' ? 'border-green-500 dark:border-green-600' :
    marketRead.sentiment === 'bearish' ? 'border-red-500 dark:border-red-600' : 'border-amber-500 dark:border-amber-600';

  return (
    <div className={cn('card', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-blue-500" />
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">Latest Candle Insight</h3>
        </div>
        <span className="text-sm text-neutral-500 dark:text-neutral-400">{dateStr} &middot; {ticker}</span>
      </div>

      {/* 3-column grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Column 1: Candle Shape */}
        <div className="flex gap-3">
          <MiniCandle o={data.open} h={data.high} l={data.low} c={data.close} />
          <div className="space-y-1.5">
            <div className={cn(
              'text-sm font-bold',
              isUp ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
            )}>
              {candle.label}
            </div>
            <div className="space-y-0.5 text-xs text-neutral-500 dark:text-neutral-400">
              <div>Body: <span className="font-medium text-neutral-700 dark:text-neutral-300">{candle.bodyPct}%</span></div>
              <div>Upper wick: <span className="font-medium text-neutral-700 dark:text-neutral-300">{candle.upperWickPct}%</span></div>
              <div>Lower wick: <span className="font-medium text-neutral-700 dark:text-neutral-300">{candle.lowerWickPct}%</span></div>
            </div>
            {changePct !== null && (
              <div className={cn(
                'text-sm font-semibold',
                changePct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
              )}>
                {changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%
              </div>
            )}
            <div className="text-xs text-neutral-400 dark:text-neutral-500">
              {formatCurrency(data.open)} &rarr; {formatCurrency(data.close)}
            </div>
          </div>
        </div>

        {/* Column 2: Patterns */}
        <div>
          <div className="text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-2">Patterns</div>
          {data.patterns.length > 0 ? (
            <div className="space-y-3">
              {data.patterns.map((p: DetectedPattern, i: number) => {
                const meta = PATTERN_META[p.type] || { icon: '?', color: '#737373' };
                const signal = PATTERN_SIGNAL_MAP[p.type] || '';
                return (
                  <div key={i}>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span
                        className="w-5 h-5 flex items-center justify-center rounded-full text-xs border shrink-0"
                        style={{ borderColor: meta.color, color: meta.color }}
                      >
                        {meta.icon}
                      </span>
                      <span className="text-sm font-semibold text-neutral-900 dark:text-white">{p.name}</span>
                      <span className={cn(
                        'px-1.5 py-0.5 text-[10px] font-semibold rounded-full',
                        p.sentiment === 'bullish' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' :
                        p.sentiment === 'bearish' ? 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400' :
                        'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400'
                      )}>
                        {p.sentiment}
                      </span>
                    </div>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400 ml-7">{p.description}</p>
                    {signal && (
                      <p className="text-xs text-neutral-700 dark:text-neutral-300 ml-7 mt-0.5 italic">{signal}</p>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div>
              <p className="text-sm text-neutral-500 dark:text-neutral-400">No candlestick pattern detected</p>
              <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
                Plain {candle.label.toLowerCase()} candle — look to indicators for context.
              </p>
            </div>
          )}
        </div>

        {/* Column 3: Indicators */}
        <div>
          <div className="text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-2">Indicators</div>
          <div className="space-y-3">
            {/* RSI */}
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-neutral-500 dark:text-neutral-400">RSI (14)</span>
                {data.rsi !== null ? (
                  <span className={cn('font-semibold', getRsiZone(data.rsi).color)}>
                    {data.rsi.toFixed(1)} &middot; {getRsiZone(data.rsi).label}
                  </span>
                ) : (
                  <span className="text-neutral-400 dark:text-neutral-500">Insufficient data</span>
                )}
              </div>
              {data.rsi !== null && (
                <div className="w-full h-1.5 bg-neutral-100 dark:bg-neutral-700 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all',
                      data.rsi >= 70 ? 'bg-red-500' :
                      data.rsi <= 30 ? 'bg-green-500' : 'bg-purple-400'
                    )}
                    style={{ width: `${Math.min(100, data.rsi)}%` }}
                  />
                </div>
              )}
            </div>

            {/* MACD */}
            <div>
              <div className="flex items-center justify-between text-xs mb-0.5">
                <span className="text-neutral-500 dark:text-neutral-400">MACD</span>
                {data.macd !== null && data.macdSignal !== null ? (
                  <span className={cn('font-semibold', getMacdStatus(data.macd, data.macdSignal).color)}>
                    {getMacdStatus(data.macd, data.macdSignal).label}
                  </span>
                ) : (
                  <span className="text-neutral-400 dark:text-neutral-500">Insufficient data</span>
                )}
              </div>
              {data.macd !== null && (
                <div className="text-[11px] text-neutral-500 dark:text-neutral-400 font-mono">
                  MACD {data.macd.toFixed(2)} &middot; Signal {data.macdSignal?.toFixed(2) ?? '—'}
                  {data.macdHist !== null && (
                    <span className={data.macdHist >= 0 ? ' text-green-600' : ' text-red-600'}>
                      {' '}Hist {data.macdHist >= 0 ? '+' : ''}{data.macdHist.toFixed(2)}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Bollinger Bands */}
            <div>
              <div className="flex items-center justify-between text-xs mb-0.5">
                <span className="text-neutral-500 dark:text-neutral-400">Bollinger Bands</span>
                {data.bbUpper !== null && data.bbLower !== null ? (() => {
                  const bb = getBbPosition(data.close, data.bbUpper, data.bbLower);
                  return (
                    <span className={cn('font-semibold', bb.color)}>
                      {bb.label} ({bb.pct}%)
                    </span>
                  );
                })() : (
                  <span className="text-neutral-400 dark:text-neutral-500">Insufficient data</span>
                )}
              </div>
              {data.bbUpper !== null && data.bbLower !== null && (
                <div className="relative w-full h-1.5 bg-neutral-100 dark:bg-neutral-700 rounded-full overflow-hidden">
                  <div
                    className="absolute h-full w-1.5 bg-blue-500 rounded-full"
                    style={{ left: `${Math.min(100, Math.max(0, getBbPosition(data.close, data.bbUpper, data.bbLower).pct))}%`, transform: 'translateX(-50%)' }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Market Read bar */}
      <div className={cn(
        'mt-4 p-3 rounded-r-lg border-l-4 bg-neutral-50 dark:bg-neutral-700 text-sm',
        sentimentBorderColor
      )}>
        <span className="font-semibold text-neutral-700 dark:text-neutral-300">Market Read: </span>
        <span className="text-neutral-600 dark:text-neutral-400">{marketRead.text}</span>
      </div>
    </div>
  );
};

export default LatestCandleInsight;
