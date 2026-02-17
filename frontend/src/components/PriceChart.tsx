import React, { useState, useMemo, useEffect } from 'react';
import {
  ComposedChart,
  Area,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { TrendingUp, TrendingDown, CandlestickChart, AreaChart, Scan } from 'lucide-react';
import { cn, formatCurrency, formatLargeNumber } from '../utils/format';
import { usePriceHistory } from '../hooks/usePriceHistory';
import {
  calculateRSI,
  calculateMACD,
  calculateBollingerBands,
} from '../utils/technicalIndicators';
import { detectPatterns, PATTERN_META } from '../utils/candlestickPatterns';
import type { DetectedPattern, LatestCandleData } from '../utils/candlestickPatterns';
import type { PricePeriod, PriceDataPoint } from '../types/api';

const PERIODS: { label: string; value: PricePeriod }[] = [
  { label: '1W', value: '1W' },
  { label: '1M', value: '1M' },
  { label: '3M', value: '3M' },
  { label: '6M', value: '6M' },
  { label: '1Y', value: '1Y' },
  { label: 'ALL', value: 'ALL' },
];

type ChartMode = 'area' | 'candlestick';
type Indicator = 'none' | 'rsi' | 'macd' | 'bollinger';

type PatternFilter = 'all' | 'bullish' | 'bearish';

interface PriceChartProps {
  ticker: string;
  className?: string;
  onPatternsDetected?: (patterns: DetectedPattern[]) => void;
  onLatestCandleData?: (data: LatestCandleData | null) => void;
}

// Custom candlestick shape for Recharts Bar
const CandlestickShape = (props: any) => {
  const { x, y, width, height, payload } = props;
  if (!payload) return null;

  const { open, close, high, low } = payload;
  const isUp = close >= open;
  const color = isUp ? '#10b981' : '#ef4444';

  // The bar is positioned at the "close" value by recharts
  // We need to compute pixel positions from the price axis
  const yScale = props.yAxis;
  if (!yScale) return null;

  const yHigh = yScale.scale(high);
  const yLow = yScale.scale(low);
  const yOpen = yScale.scale(open);
  const yClose = yScale.scale(close);

  const bodyTop = Math.min(yOpen, yClose);
  const bodyHeight = Math.max(1, Math.abs(yOpen - yClose));
  const centerX = x + width / 2;

  return (
    <g>
      {/* Wick */}
      <line x1={centerX} y1={yHigh} x2={centerX} y2={yLow} stroke={color} strokeWidth={1} />
      {/* Body */}
      <rect
        x={x + 1}
        y={bodyTop}
        width={Math.max(width - 2, 2)}
        height={bodyHeight}
        fill={isUp ? color : color}
        stroke={color}
        strokeWidth={0.5}
      />
    </g>
  );
};

// Custom tooltip showing full OHLCV data + indicators + patterns
const PriceTooltip = ({ active, payload, indicator }: any) => {
  if (!active || !payload || payload.length === 0) return null;

  const data = payload[0]?.payload;
  if (!data) return null;

  return (
    <div className="bg-white dark:bg-neutral-800 p-3 border border-neutral-200 dark:border-neutral-600 rounded-lg shadow-lg text-sm">
      <p className="font-medium text-neutral-900 dark:text-white mb-1">
        {format(parseISO(data.date), 'MMM d, yyyy')}
      </p>
      <div className="space-y-0.5 text-neutral-600 dark:text-neutral-400">
        <div className="flex justify-between gap-4">
          <span>Open</span>
          <span className="font-medium text-neutral-900 dark:text-white">{formatCurrency(data.open)}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span>High</span>
          <span className="font-medium text-neutral-900 dark:text-white">{formatCurrency(data.high)}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span>Low</span>
          <span className="font-medium text-neutral-900 dark:text-white">{formatCurrency(data.low)}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span>Close</span>
          <span className="font-bold text-neutral-900 dark:text-white">{formatCurrency(data.close)}</span>
        </div>
        <div className="flex justify-between gap-4 pt-1 border-t border-neutral-100 dark:border-neutral-600">
          <span>Volume</span>
          <span className="font-medium text-neutral-900 dark:text-white">{formatLargeNumber(data.volume)}</span>
        </div>
        {indicator === 'bollinger' && data.bbUpper != null && (
          <div className="pt-1 border-t border-neutral-100 dark:border-neutral-600 space-y-0.5">
            <div className="flex justify-between gap-4">
              <span className="text-blue-600">BB Upper</span>
              <span className="font-medium">{formatCurrency(data.bbUpper)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-blue-600">BB Mid</span>
              <span className="font-medium">{formatCurrency(data.bbMiddle)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-blue-600">BB Lower</span>
              <span className="font-medium">{formatCurrency(data.bbLower)}</span>
            </div>
          </div>
        )}
        {data.patterns && data.patterns.length > 0 && (
          <div className="pt-1 border-t border-neutral-100 dark:border-neutral-600 mt-1">
            <div className="text-xs font-semibold text-purple-600 mb-0.5">Patterns</div>
            {data.patterns.map((p: DetectedPattern, i: number) => {
              const meta = PATTERN_META[p.type] || { icon: '?', color: '#737373' };
              return (
                <div key={i} className="text-xs flex items-center gap-1">
                  <span style={{ color: meta.color }}>{meta.icon}</span>
                  <span className="font-medium">{p.name}</span>
                  <span className={
                    p.sentiment === 'bullish' ? 'text-green-600' :
                    p.sentiment === 'bearish' ? 'text-red-600' : 'text-amber-500'
                  }>
                    ({p.sentiment})
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

// Sub-chart tooltip
const IndicatorTooltip = ({ active, payload }: any) => {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0]?.payload;
  if (!data) return null;

  return (
    <div className="bg-white dark:bg-neutral-800 p-2 border border-neutral-200 dark:border-neutral-600 rounded-lg shadow-lg text-xs">
      <p className="font-medium text-neutral-900 dark:text-white mb-1">
        {format(parseISO(data.date), 'MMM d, yyyy')}
      </p>
      {data.rsi != null && (
        <div className="flex justify-between gap-3">
          <span className="text-purple-600">RSI</span>
          <span className="font-medium">{data.rsi.toFixed(1)}</span>
        </div>
      )}
      {data.macd != null && (
        <div className="space-y-0.5">
          <div className="flex justify-between gap-3">
            <span className="text-blue-600">MACD</span>
            <span className="font-medium">{data.macd.toFixed(3)}</span>
          </div>
          {data.macdSignal != null && (
            <div className="flex justify-between gap-3">
              <span className="text-orange-500">Signal</span>
              <span className="font-medium">{data.macdSignal.toFixed(3)}</span>
            </div>
          )}
          {data.macdHist != null && (
            <div className="flex justify-between gap-3">
              <span className={data.macdHist >= 0 ? 'text-green-600' : 'text-red-600'}>Hist</span>
              <span className="font-medium">{data.macdHist.toFixed(3)}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const PriceChart: React.FC<PriceChartProps> = ({ ticker, className, onPatternsDetected, onLatestCandleData }) => {
  const [period, setPeriod] = useState<PricePeriod>('3M');
  const [chartMode, setChartMode] = useState<ChartMode>('area');
  const [indicator, setIndicator] = useState<Indicator>('none');
  const [showPatterns, setShowPatterns] = useState(false);
  const [patternFilter, setPatternFilter] = useState<PatternFilter>('all');
  const { data, isLoading, error } = usePriceHistory(ticker, period);

  // Compute technical indicators, patterns, and merge into price data
  const { chartData, allPatterns } = useMemo(() => {
    if (!data?.prices || data.prices.length === 0) return { chartData: [], allPatterns: [] };

    const closes = data.prices.map((p) => p.close);
    const rsiValues = calculateRSI(closes);
    const macdResult = calculateMACD(closes);
    const bbResult = calculateBollingerBands(closes);

    const patterns = detectPatterns(data.prices);

    // Group patterns by index for tooltip lookup
    const patternsByIndex = new Map<number, DetectedPattern[]>();
    patterns.forEach((p) => {
      const list = patternsByIndex.get(p.index) || [];
      list.push(p);
      patternsByIndex.set(p.index, list);
    });

    const cd = data.prices.map((p, i) => ({
      ...p,
      rsi: rsiValues[i],
      macd: macdResult.macd[i],
      macdSignal: macdResult.signal[i],
      macdHist: macdResult.histogram[i],
      bbUpper: bbResult.upper[i],
      bbMiddle: bbResult.middle[i],
      bbLower: bbResult.lower[i],
      patterns: patternsByIndex.get(i) || [],
    }));

    return { chartData: cd, allPatterns: patterns };
  }, [data?.prices]);

  // Notify parent of detected patterns
  useEffect(() => {
    onPatternsDetected?.(allPatterns);
  }, [allPatterns, onPatternsDetected]);

  // Notify parent of latest candle enriched data
  useEffect(() => {
    if (!onLatestCandleData || chartData.length === 0) {
      onLatestCandleData?.(null);
      return;
    }
    const last = chartData[chartData.length - 1];
    const prev = chartData.length >= 2 ? chartData[chartData.length - 2] : null;
    onLatestCandleData({
      date: last.date, open: last.open, high: last.high, low: last.low,
      close: last.close, volume: last.volume, patterns: last.patterns,
      rsi: last.rsi, macd: last.macd, macdSignal: last.macdSignal, macdHist: last.macdHist,
      bbUpper: last.bbUpper, bbMiddle: last.bbMiddle, bbLower: last.bbLower,
      prevClose: prev?.close ?? null, prevVolume: prev?.volume ?? null,
    });
  }, [chartData, onLatestCandleData]);

  // Filter patterns for chart annotations
  const filteredPatterns = useMemo(() => {
    if (patternFilter === 'all') return allPatterns;
    return allPatterns.filter((p) => p.sentiment === patternFilter);
  }, [allPatterns, patternFilter]);

  // Compute Y-axis domain with 5% padding
  const priceDomain = useMemo(() => {
    if (chartData.length === 0) return [0, 100];
    const lows = chartData.map((p) => p.low);
    const highs = chartData.map((p) => p.high);

    // Include Bollinger Bands in domain when active
    if (indicator === 'bollinger') {
      chartData.forEach((p) => {
        if (p.bbUpper != null) highs.push(p.bbUpper);
        if (p.bbLower != null) lows.push(p.bbLower);
      });
    }

    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const padding = (max - min) * 0.05 || 1;
    return [Math.floor(min - padding), Math.ceil(max + padding)];
  }, [chartData, indicator]);

  // Format X-axis ticks based on period
  const formatXTick = (dateStr: string) => {
    try {
      const d = parseISO(dateStr);
      if (period === '1W' || period === '1M') return format(d, 'MMM d');
      if (period === '3M' || period === '6M') return format(d, 'MMM d');
      return format(d, "MMM ''yy");
    } catch {
      return dateStr;
    }
  };

  const summary = data?.summary;
  const isPositive = summary ? summary.change >= 0 : true;

  // Dynamic bar width based on data density
  const barSize = chartData.length > 60 ? 2 : chartData.length > 30 ? 4 : 8;

  const INDICATORS: { label: string; value: Indicator }[] = [
    { label: 'None', value: 'none' },
    { label: 'RSI', value: 'rsi' },
    { label: 'MACD', value: 'macd' },
    { label: 'Bollinger', value: 'bollinger' },
  ];

  return (
    <div className={cn('card', className)}>
      {/* Header: Price + Change + Controls */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
        {/* Left: Price info */}
        <div>
          <div className="flex items-baseline gap-3">
            <h2 className="text-3xl font-bold text-neutral-900 dark:text-white">
              {summary ? formatCurrency(summary.current_price) : isLoading ? '---' : '--'}
            </h2>
            {summary && (
              <div className={cn(
                'flex items-center gap-1 text-sm font-semibold',
                isPositive ? 'text-green-600' : 'text-red-600'
              )}>
                {isPositive ? (
                  <TrendingUp className="w-4 h-4" />
                ) : (
                  <TrendingDown className="w-4 h-4" />
                )}
                <span>
                  {isPositive ? '+' : ''}{formatCurrency(summary.change)}
                </span>
                <span className="text-xs">
                  ({isPositive ? '+' : ''}{(summary.change_percent * 100).toFixed(2)}%)
                </span>
              </div>
            )}
          </div>
          {summary && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-neutral-500 dark:text-neutral-400">
              <span>High: <span className="font-medium text-neutral-700 dark:text-neutral-300">{formatCurrency(summary.period_high)}</span></span>
              <span>Low: <span className="font-medium text-neutral-700 dark:text-neutral-300">{formatCurrency(summary.period_low)}</span></span>
              <span>Avg Vol: <span className="font-medium text-neutral-700 dark:text-neutral-300">{formatLargeNumber(summary.avg_volume)}</span></span>
            </div>
          )}
        </div>

        {/* Right: Controls */}
        <div className="flex flex-col gap-2 sm:items-end">
          {/* Period selector */}
          <div className="flex flex-wrap gap-1 bg-neutral-100 dark:bg-neutral-700 p-1 rounded-lg">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                  period === p.value
                    ? 'bg-white dark:bg-neutral-600 text-neutral-900 dark:text-white shadow-sm'
                    : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200'
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
          {/* Chart mode + Indicator + Patterns */}
          <div className="flex flex-wrap gap-2">
            <div className="flex bg-neutral-100 dark:bg-neutral-700 p-1 rounded-lg">
              <button
                onClick={() => setChartMode('area')}
                title="Area chart"
                className={cn(
                  'p-1.5 rounded-md transition-all',
                  chartMode === 'area' ? 'bg-white dark:bg-neutral-600 shadow-sm text-neutral-900 dark:text-white' : 'text-neutral-400 dark:text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200'
                )}
              >
                <AreaChart className="w-4 h-4" />
              </button>
              <button
                onClick={() => setChartMode('candlestick')}
                title="Candlestick chart"
                className={cn(
                  'p-1.5 rounded-md transition-all',
                  chartMode === 'candlestick' ? 'bg-white dark:bg-neutral-600 shadow-sm text-neutral-900 dark:text-white' : 'text-neutral-400 dark:text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200'
                )}
              >
                <CandlestickChart className="w-4 h-4" />
              </button>
            </div>
            <div className="flex gap-1 bg-neutral-100 dark:bg-neutral-700 p-1 rounded-lg">
              {INDICATORS.map((ind) => (
                <button
                  key={ind.value}
                  onClick={() => setIndicator(ind.value)}
                  className={cn(
                    'px-2 py-1 text-xs font-medium rounded-md transition-all',
                    indicator === ind.value
                      ? 'bg-white dark:bg-neutral-600 text-neutral-900 dark:text-white shadow-sm'
                      : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200'
                  )}
                >
                  {ind.label}
                </button>
              ))}
            </div>
            {/* Patterns toggle */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => {
                  const next = !showPatterns;
                  setShowPatterns(next);
                  if (next) setChartMode('candlestick');
                }}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all border',
                  showPatterns
                    ? 'bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-700'
                    : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-500 dark:text-neutral-400 border-transparent hover:text-neutral-700 dark:hover:text-neutral-200'
                )}
              >
                <Scan className="w-3.5 h-3.5" />
                Patterns
                {allPatterns.length > 0 && (
                  <span className={cn(
                    'px-1.5 py-0.5 text-[10px] font-bold rounded-full',
                    showPatterns ? 'bg-purple-200 dark:bg-purple-800 text-purple-800 dark:text-purple-200' : 'bg-neutral-200 dark:bg-neutral-600 text-neutral-600 dark:text-neutral-300'
                  )}>
                    {allPatterns.length}
                  </span>
                )}
              </button>
              {showPatterns && (
                <select
                  value={patternFilter}
                  onChange={(e) => setPatternFilter(e.target.value as PatternFilter)}
                  className="text-xs bg-neutral-100 dark:bg-neutral-700 border border-neutral-200 dark:border-neutral-600 rounded-md px-2 py-1.5 text-neutral-600 dark:text-neutral-300"
                >
                  <option value="all">All</option>
                  <option value="bullish">Bullish</option>
                  <option value="bearish">Bearish</option>
                </select>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      {isLoading ? (
        <div className="animate-pulse">
          <div className="h-[300px] bg-neutral-100 dark:bg-neutral-700 rounded flex items-end justify-around p-4">
            {[...Array(12)].map((_, i) => (
              <div
                key={i}
                className="bg-neutral-200 dark:bg-neutral-600 rounded-t"
                style={{ height: `${20 + Math.random() * 60}%`, width: '6%' }}
              />
            ))}
          </div>
        </div>
      ) : error || chartData.length === 0 ? (
        <div className="flex items-center justify-center h-[300px] bg-neutral-50 dark:bg-neutral-800 rounded border-2 border-dashed border-neutral-200 dark:border-neutral-600">
          <div className="text-center">
            <p className="text-sm font-medium text-neutral-900 dark:text-white">No price data available</p>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
              Price data is ingested hourly. Check back soon.
            </p>
          </div>
        </div>
      ) : (
        <>
          {/* Main Price Chart */}
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
              <defs>
                <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor={isPositive ? '#10b981' : '#ef4444'}
                    stopOpacity={0.3}
                  />
                  <stop
                    offset="95%"
                    stopColor={isPositive ? '#10b981' : '#ef4444'}
                    stopOpacity={0.0}
                  />
                </linearGradient>
                <linearGradient id="bbFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.08} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.08} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" className="dark:stroke-neutral-600" vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={formatXTick}
                stroke="#737373"
                className="dark:stroke-neutral-400"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                yAxisId="price"
                domain={priceDomain}
                tickFormatter={(v: number) => `$${v}`}
                stroke="#737373"
                className="dark:stroke-neutral-400"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                width={60}
              />
              <YAxis
                yAxisId="volume"
                orientation="right"
                domain={[0, (dataMax: number) => dataMax * 4]}
                hide
              />
              <Tooltip content={<PriceTooltip indicator={indicator} />} />

              {/* Volume bars (always shown) */}
              <Bar
                yAxisId="volume"
                dataKey="volume"
                fill="#e5e7eb"
                className="dark:fill-neutral-600"
                opacity={0.5}
                barSize={barSize}
              />

              {/* Bollinger Bands overlay */}
              {indicator === 'bollinger' && (
                <>
                  <Area
                    yAxisId="price"
                    type="monotone"
                    dataKey="bbUpper"
                    stroke="none"
                    fill="url(#bbFill)"
                    dot={false}
                    activeDot={false}
                    connectNulls={false}
                  />
                  <Line
                    yAxisId="price"
                    type="monotone"
                    dataKey="bbUpper"
                    stroke="#94a3b8"
                    strokeWidth={1}
                    strokeDasharray="4 2"
                    dot={false}
                    activeDot={false}
                    connectNulls={false}
                  />
                  <Line
                    yAxisId="price"
                    type="monotone"
                    dataKey="bbMiddle"
                    stroke="#3b82f6"
                    strokeWidth={1.5}
                    dot={false}
                    activeDot={false}
                    connectNulls={false}
                  />
                  <Line
                    yAxisId="price"
                    type="monotone"
                    dataKey="bbLower"
                    stroke="#94a3b8"
                    strokeWidth={1}
                    strokeDasharray="4 2"
                    dot={false}
                    activeDot={false}
                    connectNulls={false}
                  />
                </>
              )}

              {/* Price: Area or Candlestick */}
              {chartMode === 'area' ? (
                <Area
                  yAxisId="price"
                  type="monotone"
                  dataKey="close"
                  stroke={isPositive ? '#10b981' : '#ef4444'}
                  strokeWidth={2}
                  fill="url(#priceGradient)"
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 2 }}
                />
              ) : (
                /* Candlestick via Bar with custom shape */
                <Bar
                  yAxisId="price"
                  dataKey="close"
                  barSize={barSize + 2}
                  shape={(props: any) => {
                    const { x, width, payload } = props;
                    if (!payload) return null;
                    const { open, close, high, low } = payload;
                    const isUp = close >= open;
                    const color = isUp ? '#10b981' : '#ef4444';

                    // Access the price axis from the chart
                    const yAxis = props.yAxis || props.background?.props?.yAxis;

                    // Fallback: compute pixel positions from domain + chart dimensions
                    const chartHeight = 300 - 10; // height minus margins
                    const [domMin, domMax] = priceDomain;
                    const range = domMax - domMin || 1;
                    const toY = (v: number) => 5 + (1 - (v - domMin) / range) * (chartHeight - 20);

                    const yHigh = toY(high);
                    const yLow = toY(low);
                    const yOpen = toY(open);
                    const yClose = toY(close);

                    const bodyTop = Math.min(yOpen, yClose);
                    const bodyHeight = Math.max(1, Math.abs(yOpen - yClose));
                    const centerX = x + width / 2;

                    return (
                      <g>
                        <line x1={centerX} y1={yHigh} x2={centerX} y2={yLow} stroke={color} strokeWidth={1} />
                        <rect
                          x={x + 1}
                          y={bodyTop}
                          width={Math.max(width - 2, 2)}
                          height={bodyHeight}
                          fill={color}
                          stroke={color}
                          strokeWidth={0.5}
                        />
                      </g>
                    );
                  }}
                />
              )}

              {/* Pattern annotation markers */}
              {showPatterns && chartMode === 'candlestick' && filteredPatterns.map((p, i) => (
                <ReferenceLine
                  key={`pat-${p.type}-${p.index}-${i}`}
                  yAxisId="price"
                  x={p.date}
                  stroke="none"
                  label={{
                    value: PATTERN_META[p.type]?.icon || '?',
                    position: 'top',
                    fill: PATTERN_META[p.type]?.color || '#737373',
                    fontSize: 14,
                    fontWeight: 'bold',
                    offset: 8,
                  }}
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>

          {/* RSI Sub-Chart */}
          {indicator === 'rsi' && (
            <div className="mt-2">
              <div className="text-xs font-medium text-neutral-500 dark:text-neutral-400 mb-1 ml-[70px]">RSI (14)</div>
              <ResponsiveContainer width="100%" height={120}>
                <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" className="dark:stroke-neutral-700" vertical={false} />
                  <XAxis dataKey="date" hide />
                  <YAxis
                    domain={[0, 100]}
                    ticks={[30, 50, 70]}
                    stroke="#a3a3a3"
                    className="dark:stroke-neutral-400"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                    width={60}
                  />
                  <Tooltip content={<IndicatorTooltip />} />
                  <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" strokeOpacity={0.6} />
                  <ReferenceLine y={30} stroke="#10b981" strokeDasharray="3 3" strokeOpacity={0.6} />
                  {/* Overbought zone */}
                  <Area
                    type="monotone"
                    dataKey={() => 100}
                    baseValue={70}
                    fill="#ef4444"
                    fillOpacity={0.05}
                    stroke="none"
                  />
                  {/* Oversold zone */}
                  <Area
                    type="monotone"
                    dataKey={() => 30}
                    baseValue={0}
                    fill="#10b981"
                    fillOpacity={0.05}
                    stroke="none"
                  />
                  <Line
                    type="monotone"
                    dataKey="rsi"
                    stroke="#8b5cf6"
                    strokeWidth={1.5}
                    dot={false}
                    connectNulls={false}
                    activeDot={{ r: 3 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* MACD Sub-Chart */}
          {indicator === 'macd' && (
            <div className="mt-2">
              <div className="text-xs font-medium text-neutral-500 dark:text-neutral-400 mb-1 ml-[70px]">MACD (12, 26, 9)</div>
              <ResponsiveContainer width="100%" height={130}>
                <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" className="dark:stroke-neutral-700" vertical={false} />
                  <XAxis dataKey="date" hide />
                  <YAxis
                    stroke="#a3a3a3"
                    className="dark:stroke-neutral-400"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                    width={60}
                    tickFormatter={(v: number) => v.toFixed(1)}
                  />
                  <Tooltip content={<IndicatorTooltip />} />
                  <ReferenceLine y={0} stroke="#d4d4d4" className="dark:stroke-neutral-600" strokeWidth={1} />
                  <Bar dataKey="macdHist" barSize={barSize}>
                    {chartData.map((entry, index) => (
                      <Cell
                        key={index}
                        fill={entry.macdHist != null && entry.macdHist >= 0 ? '#10b981' : '#ef4444'}
                        fillOpacity={0.6}
                      />
                    ))}
                  </Bar>
                  <Line
                    type="monotone"
                    dataKey="macd"
                    stroke="#3b82f6"
                    strokeWidth={1.5}
                    dot={false}
                    connectNulls={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="macdSignal"
                    stroke="#f97316"
                    strokeWidth={1.5}
                    dot={false}
                    connectNulls={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default PriceChart;
