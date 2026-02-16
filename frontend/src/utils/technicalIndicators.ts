/**
 * Technical Indicator Calculations
 * All calculations run client-side from OHLCV data.
 */

export function calculateSMA(prices: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < prices.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += prices[j];
      result.push(sum / period);
    }
  }
  return result;
}

export function calculateEMA(prices: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  const k = 2 / (period + 1);

  for (let i = 0; i < prices.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else if (i === period - 1) {
      // Seed with SMA
      let sum = 0;
      for (let j = 0; j < period; j++) sum += prices[j];
      result.push(sum / period);
    } else {
      const prev = result[i - 1]!;
      result.push(prices[i] * k + prev * (1 - k));
    }
  }
  return result;
}

export function calculateRSI(closes: number[], period: number = 14): (number | null)[] {
  const result: (number | null)[] = [];

  if (closes.length < period + 1) {
    return closes.map(() => null);
  }

  // Calculate initial gains and losses
  const changes: number[] = [];
  for (let i = 1; i < closes.length; i++) {
    changes.push(closes[i] - closes[i - 1]);
  }

  // First value: average gain/loss over initial period
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 0; i < period; i++) {
    if (changes[i] > 0) avgGain += changes[i];
    else avgLoss += Math.abs(changes[i]);
  }
  avgGain /= period;
  avgLoss /= period;

  // First period entries are null
  result.push(null); // index 0 (no change)
  for (let i = 0; i < period - 1; i++) result.push(null);

  // RSI at index=period
  const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  result.push(100 - 100 / (1 + rs));

  // Wilder's smoothing for remaining
  for (let i = period; i < changes.length; i++) {
    const gain = changes[i] > 0 ? changes[i] : 0;
    const loss = changes[i] < 0 ? Math.abs(changes[i]) : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
    result.push(rsi);
  }

  return result;
}

export interface MACDResult {
  macd: (number | null)[];
  signal: (number | null)[];
  histogram: (number | null)[];
}

export function calculateMACD(
  closes: number[],
  fast: number = 12,
  slow: number = 26,
  signalPeriod: number = 9
): MACDResult {
  const emaFast = calculateEMA(closes, fast);
  const emaSlow = calculateEMA(closes, slow);

  // MACD line = EMA fast - EMA slow
  const macdLine: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (emaFast[i] !== null && emaSlow[i] !== null) {
      macdLine.push(emaFast[i]! - emaSlow[i]!);
    } else {
      macdLine.push(null);
    }
  }

  // Signal line = EMA of MACD values
  const validMacd = macdLine.filter((v): v is number => v !== null);
  const signalEma = calculateEMA(validMacd, signalPeriod);

  // Map signal back to full-length array
  const signalLine: (number | null)[] = [];
  const histogram: (number | null)[] = [];
  let validIdx = 0;

  for (let i = 0; i < closes.length; i++) {
    if (macdLine[i] !== null) {
      const sig = signalEma[validIdx] ?? null;
      signalLine.push(sig);
      histogram.push(sig !== null ? macdLine[i]! - sig : null);
      validIdx++;
    } else {
      signalLine.push(null);
      histogram.push(null);
    }
  }

  return { macd: macdLine, signal: signalLine, histogram };
}

export interface BollingerBandsResult {
  upper: (number | null)[];
  middle: (number | null)[];
  lower: (number | null)[];
}

export function calculateBollingerBands(
  closes: number[],
  period: number = 20,
  stdDevMultiplier: number = 2
): BollingerBandsResult {
  const middle = calculateSMA(closes, period);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];

  for (let i = 0; i < closes.length; i++) {
    if (middle[i] === null) {
      upper.push(null);
      lower.push(null);
    } else {
      // Calculate standard deviation over period
      let sumSq = 0;
      for (let j = i - period + 1; j <= i; j++) {
        const diff = closes[j] - middle[i]!;
        sumSq += diff * diff;
      }
      const stdDev = Math.sqrt(sumSq / period);
      upper.push(middle[i]! + stdDevMultiplier * stdDev);
      lower.push(middle[i]! - stdDevMultiplier * stdDev);
    }
  }

  return { upper, middle, lower };
}
