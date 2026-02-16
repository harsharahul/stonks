/**
 * Candlestick Pattern Detection
 * Client-side pattern recognition from OHLCV data.
 */

export type PatternSentiment = 'bullish' | 'bearish' | 'neutral';
export type PatternReliability = 'low' | 'medium' | 'high';

export interface DetectedPattern {
  index: number;
  date: string;
  name: string;
  type: string;
  sentiment: PatternSentiment;
  reliability: PatternReliability;
  description: string;
  span: number;
}

export const PATTERN_META: Record<string, { icon: string; color: string }> = {
  doji:                 { icon: '✚', color: '#f59e0b' },
  hammer:              { icon: '⬆', color: '#10b981' },
  inverted_hammer:     { icon: '⇧', color: '#10b981' },
  shooting_star:       { icon: '★', color: '#ef4444' },
  marubozu:            { icon: '▮', color: '#6366f1' },
  bullish_engulfing:   { icon: '⊕', color: '#10b981' },
  bearish_engulfing:   { icon: '⊖', color: '#ef4444' },
  piercing_line:       { icon: '↗', color: '#10b981' },
  dark_cloud_cover:    { icon: '↘', color: '#ef4444' },
  morning_star:        { icon: '☀', color: '#10b981' },
  evening_star:        { icon: '☽', color: '#ef4444' },
  three_white_soldiers: { icon: '⫿', color: '#10b981' },
};

// --- Helpers ---

function bodySize(o: number, c: number): number {
  return Math.abs(c - o);
}

function range(h: number, l: number): number {
  return h - l;
}

function upperShadow(o: number, c: number, h: number): number {
  return h - Math.max(o, c);
}

function lowerShadow(o: number, c: number, l: number): number {
  return Math.min(o, c) - l;
}

function isBullish(o: number, c: number): boolean {
  return c > o;
}

function isBearish(o: number, c: number): boolean {
  return c < o;
}

function trendUp(prices: { close: number }[], i: number, lookback: number = 3): boolean {
  if (i < lookback) return false;
  for (let j = i - lookback; j < i; j++) {
    if (prices[j + 1].close <= prices[j].close) return false;
  }
  return true;
}

function trendDown(prices: { close: number }[], i: number, lookback: number = 3): boolean {
  if (i < lookback) return false;
  for (let j = i - lookback; j < i; j++) {
    if (prices[j + 1].close >= prices[j].close) return false;
  }
  return true;
}

// --- Pattern Detectors ---

interface Candle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

function detectDoji(c: Candle, i: number): DetectedPattern | null {
  const r = range(c.high, c.low);
  if (r === 0) return null;
  if (bodySize(c.open, c.close) <= r * 0.1) {
    return {
      index: i, date: c.date, name: 'Doji', type: 'doji',
      sentiment: 'neutral', reliability: 'low', span: 1,
      description: 'Market indecision — open and close nearly equal',
    };
  }
  return null;
}

function detectHammer(c: Candle, i: number, prices: Candle[]): DetectedPattern | null {
  const r = range(c.high, c.low);
  if (r === 0) return null;
  const body = bodySize(c.open, c.close);
  const lower = lowerShadow(c.open, c.close, c.low);
  const upper = upperShadow(c.open, c.close, c.high);

  if (body <= r * 0.35 && lower >= body * 2 && upper <= body * 0.3 && trendDown(prices, i)) {
    return {
      index: i, date: c.date, name: 'Hammer', type: 'hammer',
      sentiment: 'bullish', reliability: 'medium', span: 1,
      description: 'Potential reversal after downtrend — buyers pushed price up from lows',
    };
  }
  return null;
}

function detectInvertedHammer(c: Candle, i: number, prices: Candle[]): DetectedPattern | null {
  const r = range(c.high, c.low);
  if (r === 0) return null;
  const body = bodySize(c.open, c.close);
  const upper = upperShadow(c.open, c.close, c.high);
  const lower = lowerShadow(c.open, c.close, c.low);

  if (body <= r * 0.35 && upper >= body * 2 && lower <= body * 0.3 && trendDown(prices, i)) {
    return {
      index: i, date: c.date, name: 'Inverted Hammer', type: 'inverted_hammer',
      sentiment: 'bullish', reliability: 'medium', span: 1,
      description: 'Potential bullish reversal — buying pressure emerging after downtrend',
    };
  }
  return null;
}

function detectShootingStar(c: Candle, i: number, prices: Candle[]): DetectedPattern | null {
  const r = range(c.high, c.low);
  if (r === 0) return null;
  const body = bodySize(c.open, c.close);
  const upper = upperShadow(c.open, c.close, c.high);
  const lower = lowerShadow(c.open, c.close, c.low);

  if (body <= r * 0.35 && upper >= body * 2 && lower <= body * 0.3 && trendUp(prices, i)) {
    return {
      index: i, date: c.date, name: 'Shooting Star', type: 'shooting_star',
      sentiment: 'bearish', reliability: 'medium', span: 1,
      description: 'Potential reversal after uptrend — sellers rejected higher prices',
    };
  }
  return null;
}

function detectMarubozu(c: Candle, i: number): DetectedPattern | null {
  const r = range(c.high, c.low);
  if (r === 0) return null;
  const body = bodySize(c.open, c.close);

  if (body >= r * 0.9) {
    const sentiment: PatternSentiment = isBullish(c.open, c.close) ? 'bullish' : 'bearish';
    return {
      index: i, date: c.date, name: 'Marubozu', type: 'marubozu',
      sentiment, reliability: 'medium', span: 1,
      description: `Strong ${sentiment} candle with almost no wicks — strong conviction`,
    };
  }
  return null;
}

function detectBullishEngulfing(prev: Candle, curr: Candle, i: number): DetectedPattern | null {
  if (
    isBearish(prev.open, prev.close) &&
    isBullish(curr.open, curr.close) &&
    curr.open <= prev.close &&
    curr.close >= prev.open
  ) {
    return {
      index: i, date: curr.date, name: 'Bullish Engulfing', type: 'bullish_engulfing',
      sentiment: 'bullish', reliability: 'high', span: 2,
      description: 'Green candle completely engulfs prior red candle — strong reversal signal',
    };
  }
  return null;
}

function detectBearishEngulfing(prev: Candle, curr: Candle, i: number): DetectedPattern | null {
  if (
    isBullish(prev.open, prev.close) &&
    isBearish(curr.open, curr.close) &&
    curr.open >= prev.close &&
    curr.close <= prev.open
  ) {
    return {
      index: i, date: curr.date, name: 'Bearish Engulfing', type: 'bearish_engulfing',
      sentiment: 'bearish', reliability: 'high', span: 2,
      description: 'Red candle completely engulfs prior green candle — strong reversal signal',
    };
  }
  return null;
}

function detectPiercingLine(prev: Candle, curr: Candle, i: number): DetectedPattern | null {
  if (
    isBearish(prev.open, prev.close) &&
    isBullish(curr.open, curr.close) &&
    curr.open < prev.low &&
    curr.close > prev.close + bodySize(prev.open, prev.close) * 0.5 &&
    curr.close < prev.open
  ) {
    return {
      index: i, date: curr.date, name: 'Piercing Line', type: 'piercing_line',
      sentiment: 'bullish', reliability: 'medium', span: 2,
      description: 'Opens below prior low, closes above 50% of prior body — bullish reversal',
    };
  }
  return null;
}

function detectDarkCloudCover(prev: Candle, curr: Candle, i: number): DetectedPattern | null {
  if (
    isBullish(prev.open, prev.close) &&
    isBearish(curr.open, curr.close) &&
    curr.open > prev.high &&
    curr.close < prev.open + bodySize(prev.open, prev.close) * 0.5 &&
    curr.close > prev.open
  ) {
    return {
      index: i, date: curr.date, name: 'Dark Cloud Cover', type: 'dark_cloud_cover',
      sentiment: 'bearish', reliability: 'medium', span: 2,
      description: 'Opens above prior high, closes below 50% of prior body — bearish reversal',
    };
  }
  return null;
}

function detectMorningStar(a: Candle, b: Candle, c: Candle, i: number): DetectedPattern | null {
  const aBody = bodySize(a.open, a.close);
  const bBody = bodySize(b.open, b.close);
  const bRange = range(b.high, b.low);

  if (
    isBearish(a.open, a.close) &&
    aBody > 0 &&
    bBody <= bRange * 0.3 && // small body (doji/spinning top)
    isBullish(c.open, c.close) &&
    c.close > a.close + aBody * 0.5
  ) {
    return {
      index: i, date: c.date, name: 'Morning Star', type: 'morning_star',
      sentiment: 'bullish', reliability: 'high', span: 3,
      description: 'Three-candle bullish reversal — bearish, indecision, then strong bullish',
    };
  }
  return null;
}

function detectEveningStar(a: Candle, b: Candle, c: Candle, i: number): DetectedPattern | null {
  const aBody = bodySize(a.open, a.close);
  const bBody = bodySize(b.open, b.close);
  const bRange = range(b.high, b.low);

  if (
    isBullish(a.open, a.close) &&
    aBody > 0 &&
    bBody <= bRange * 0.3 &&
    isBearish(c.open, c.close) &&
    c.close < a.open + aBody * 0.5
  ) {
    return {
      index: i, date: c.date, name: 'Evening Star', type: 'evening_star',
      sentiment: 'bearish', reliability: 'high', span: 3,
      description: 'Three-candle bearish reversal — bullish, indecision, then strong bearish',
    };
  }
  return null;
}

function detectThreeWhiteSoldiers(a: Candle, b: Candle, c: Candle, i: number): DetectedPattern | null {
  if (
    isBullish(a.open, a.close) &&
    isBullish(b.open, b.close) &&
    isBullish(c.open, c.close) &&
    b.open >= a.open && b.open <= a.close && // opens within prev body
    c.open >= b.open && c.open <= b.close &&
    b.close > a.close && // each closes at new high
    c.close > b.close
  ) {
    return {
      index: i, date: c.date, name: 'Three White Soldiers', type: 'three_white_soldiers',
      sentiment: 'bullish', reliability: 'high', span: 3,
      description: 'Three consecutive green candles with ascending closes — strong bullish momentum',
    };
  }
  return null;
}

// --- Candle Classification ---

export interface LatestCandleData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  patterns: DetectedPattern[];
  rsi: number | null;
  macd: number | null;
  macdSignal: number | null;
  macdHist: number | null;
  bbUpper: number | null;
  bbMiddle: number | null;
  bbLower: number | null;
  prevClose: number | null;
  prevVolume: number | null;
}

export type CandleBodyType =
  | 'strong_bullish' | 'bullish' | 'weak_bullish'
  | 'doji'
  | 'weak_bearish' | 'bearish' | 'strong_bearish';

export function classifyCandle(
  o: number, h: number, l: number, c: number
): { type: CandleBodyType; label: string; bodyPct: number; upperWickPct: number; lowerWickPct: number } {
  const r = h - l;
  if (r === 0) return { type: 'doji', label: 'Doji', bodyPct: 0, upperWickPct: 0, lowerWickPct: 0 };

  const body = Math.abs(c - o);
  const bodyPct = Math.round((body / r) * 100);
  const upperWickPct = Math.round(((h - Math.max(o, c)) / r) * 100);
  const lowerWickPct = Math.round(((Math.min(o, c) - l) / r) * 100);
  const isUp = c >= o;

  let type: CandleBodyType;
  let label: string;

  if (bodyPct <= 10) {
    type = 'doji';
    label = 'Doji';
  } else if (isUp) {
    if (bodyPct >= 80) { type = 'strong_bullish'; label = 'Strong Bullish'; }
    else if (bodyPct >= 40) { type = 'bullish'; label = 'Bullish'; }
    else { type = 'weak_bullish'; label = 'Weak Bullish'; }
  } else {
    if (bodyPct >= 80) { type = 'strong_bearish'; label = 'Strong Bearish'; }
    else if (bodyPct >= 40) { type = 'bearish'; label = 'Bearish'; }
    else { type = 'weak_bearish'; label = 'Weak Bearish'; }
  }

  return { type, label, bodyPct, upperWickPct, lowerWickPct };
}

// --- Main Detection ---

export function detectPatterns(
  prices: Array<{ date: string; open: number; high: number; low: number; close: number }>
): DetectedPattern[] {
  const patterns: DetectedPattern[] = [];
  if (prices.length < 2) return patterns;

  for (let i = 0; i < prices.length; i++) {
    const c = prices[i];

    // Single candle patterns
    const doji = detectDoji(c, i);
    if (doji) patterns.push(doji);

    const hammer = detectHammer(c, i, prices);
    if (hammer) patterns.push(hammer);

    const invertedHammer = detectInvertedHammer(c, i, prices);
    if (invertedHammer) patterns.push(invertedHammer);

    const shootingStar = detectShootingStar(c, i, prices);
    if (shootingStar) patterns.push(shootingStar);

    const marubozu = detectMarubozu(c, i);
    if (marubozu) patterns.push(marubozu);

    // Two candle patterns
    if (i >= 1) {
      const prev = prices[i - 1];

      const bullEng = detectBullishEngulfing(prev, c, i);
      if (bullEng) patterns.push(bullEng);

      const bearEng = detectBearishEngulfing(prev, c, i);
      if (bearEng) patterns.push(bearEng);

      const piercing = detectPiercingLine(prev, c, i);
      if (piercing) patterns.push(piercing);

      const darkCloud = detectDarkCloudCover(prev, c, i);
      if (darkCloud) patterns.push(darkCloud);
    }

    // Three candle patterns
    if (i >= 2) {
      const a = prices[i - 2];
      const b = prices[i - 1];

      const morningStar = detectMorningStar(a, b, c, i);
      if (morningStar) patterns.push(morningStar);

      const eveningStar = detectEveningStar(a, b, c, i);
      if (eveningStar) patterns.push(eveningStar);

      const soldiers = detectThreeWhiteSoldiers(a, b, c, i);
      if (soldiers) patterns.push(soldiers);
    }
  }

  return patterns;
}
