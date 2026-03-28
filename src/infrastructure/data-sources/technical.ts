/**
 * Technical indicators — pure math, no external dependencies
 *
 * Matches Python pandas implementations in akshare_bridge.py:
 *   - EMA: ewm(span, adjust=False)
 *   - RSI: rolling(14).mean() on gains/losses
 *   - Bollinger std: ddof=1 (sample std)
 */

// ── Basic rolling ──────────────────────────────────────────────────────────

export function rollingMean(data: number[], period: number): (number | null)[] {
  return data.map((_, i) => {
    if (i + 1 < period) return null;
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += data[j];
    return sum / period;
  });
}

export function rollingStd(data: number[], period: number): (number | null)[] {
  return data.map((_, i) => {
    if (i + 1 < period) return null;
    const slice = data.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    // ddof=1 (sample std, matching pandas default)
    const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / (period - 1);
    return Math.sqrt(variance);
  });
}

// ── EMA (ewm, adjust=False) ────────────────────────────────────────────────

export function ema(data: number[], span: number): number[] {
  const alpha = 2 / (span + 1);
  const result: number[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i === 0) {
      result.push(data[0]);
    } else {
      result.push(alpha * data[i] + (1 - alpha) * result[i - 1]);
    }
  }
  return result;
}

// ── RSI ────────────────────────────────────────────────────────────────────

export function rsi(close: number[], period = 14): (number | null)[] {
  if (close.length < period + 1) return close.map(() => null);

  const gains: number[] = [0];
  const losses: number[] = [0];
  for (let i = 1; i < close.length; i++) {
    const diff = close[i] - close[i - 1];
    gains.push(diff > 0 ? diff : 0);
    losses.push(diff < 0 ? -diff : 0);
  }

  // Rolling mean of gains/losses (matches pandas rolling(14).mean())
  const avgGain = rollingMean(gains, period);
  const avgLoss = rollingMean(losses, period);

  return close.map((_, i) => {
    if (avgGain[i] === null || avgLoss[i] === null) return null;
    const g = avgGain[i]!;
    const l = avgLoss[i]!;
    if (l === 0) return 100;
    return 100 - 100 / (1 + g / l);
  });
}

// ── MACD ───────────────────────────────────────────────────────────────────

export interface MacdResult {
  dif: number[]; dea: number[]; histogram: number[];
}

export function macd(close: number[], fast = 12, slow = 26, signal = 9): MacdResult {
  const ema12 = ema(close, fast);
  const ema26 = ema(close, slow);
  const dif = ema12.map((v, i) => v - ema26[i]);
  const dea = ema(dif, signal);
  const histogram = dif.map((v, i) => (v - dea[i]) * 2);
  return { dif, dea, histogram };
}

// ── Bollinger Bands ────────────────────────────────────────────────────────

export interface BollingerResult {
  upper: (number | null)[]; mid: (number | null)[]; lower: (number | null)[];
}

export function bollinger(close: number[], period = 20, stdDev = 2): BollingerResult {
  const mid = rollingMean(close, period);
  const std = rollingStd(close, period);
  return {
    upper: mid.map((m, i) => m !== null && std[i] !== null ? m + stdDev * std[i]! : null),
    mid,
    lower: mid.map((m, i) => m !== null && std[i] !== null ? m - stdDev * std[i]! : null),
  };
}

// ── Last value helpers ─────────────────────────────────────────────────────

export function lastNum(arr: (number | null)[]): number | null {
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i] !== null) return arr[i];
  }
  return null;
}

export function roundN(v: number | null, decimals = 4): number | null {
  if (v === null) return null;
  const f = Math.pow(10, decimals);
  return Math.round(v * f) / f;
}

// ── KDJ ────────────────────────────────────────────────────────────────────

export interface KdjResult {
  k: number[]; d: number[]; j: number[];
}

/**
 * KDJ (Stochastic Oscillator, Chinese version)
 * n=9, m1=3, m2=3 matches most A-share charting platforms.
 * Initial K/D seed = 50.
 */
export function kdj(
  high: number[], low: number[], close: number[],
  n = 9, m1 = 3, m2 = 3,
): KdjResult {
  const len = close.length;
  const k: number[] = new Array(len).fill(50);
  const d: number[] = new Array(len).fill(50);
  const j: number[] = new Array(len);

  for (let i = 0; i < len; i++) {
    const start = Math.max(0, i - n + 1);
    const hiSlice = high.slice(start, i + 1);
    const loSlice = low.slice(start, i + 1);
    const hh = Math.max(...hiSlice);
    const ll = Math.min(...loSlice);
    const rsv = hh === ll ? 50 : ((close[i] - ll) / (hh - ll)) * 100;

    k[i] = i === 0 ? rsv : (1 / m1) * rsv + ((m1 - 1) / m1) * k[i - 1];
    d[i] = i === 0 ? k[i] : (1 / m2) * k[i] + ((m2 - 1) / m2) * d[i - 1];
    j[i] = 3 * k[i] - 2 * d[i];
  }
  return { k, d, j };
}

// ── ATR (Wilder's smoothing) ────────────────────────────────────────────────

/**
 * Average True Range using Wilder's smoothing (alpha = 1/period).
 * First ATR is simple mean of first `period` TRs.
 */
export function atr(high: number[], low: number[], close: number[], period = 14): number[] {
  const len = close.length;
  const tr: number[] = [high[0] - low[0]];
  for (let i = 1; i < len; i++) {
    tr.push(Math.max(high[i] - low[i], Math.abs(high[i] - close[i - 1]), Math.abs(low[i] - close[i - 1])));
  }

  const result: number[] = new Array(len).fill(0);
  // seed with simple mean
  const seed = tr.slice(0, period).reduce((a, b) => a + b, 0) / period;
  result[period - 1] = seed;
  for (let i = period; i < len; i++) {
    result[i] = (result[i - 1] * (period - 1) + tr[i]) / period;
  }
  return result;
}

// ── OBV (On-Balance Volume) ────────────────────────────────────────────────

export function obv(close: number[], volume: number[]): number[] {
  const len = close.length;
  const result: number[] = new Array(len).fill(0);
  result[0] = volume[0];
  for (let i = 1; i < len; i++) {
    if (close[i] > close[i - 1]) result[i] = result[i - 1] + volume[i];
    else if (close[i] < close[i - 1]) result[i] = result[i - 1] - volume[i];
    else result[i] = result[i - 1];
  }
  return result;
}

// ── CCI ────────────────────────────────────────────────────────────────────

/**
 * Commodity Channel Index using typical price = (H+L+C)/3
 */
export function cci(high: number[], low: number[], close: number[], period = 20): (number | null)[] {
  const tp = close.map((c, i) => (high[i] + low[i] + c) / 3);
  const maTp = rollingMean(tp, period);
  return tp.map((t, i) => {
    if (maTp[i] === null) return null;
    const slice = tp.slice(Math.max(0, i - period + 1), i + 1);
    const md = slice.reduce((sum, v) => sum + Math.abs(v - maTp[i]!), 0) / slice.length;
    return md === 0 ? 0 : (t - maTp[i]!) / (0.015 * md);
  });
}

// ── K线形态识别 ────────────────────────────────────────────────────────────

export interface CandlestickPattern {
  date: string;
  pattern: string;
  type: "bullish" | "bearish" | "neutral";
  strength: "strong" | "moderate";
}

/**
 * Detect candlestick patterns in the last `lookback` candles.
 * Recognized patterns: 锤子线, 上吊线, 看涨吞没, 看跌吞没, 十字星, 孕线, 启明星, 黄昏星
 */
export function candlestickPatterns(
  dates: string[],
  open: number[], high: number[], low: number[], close: number[],
  lookback = 10,
): CandlestickPattern[] {
  const n = close.length;
  const start = Math.max(2, n - lookback);
  const results: CandlestickPattern[] = [];

  // Helper: determine if the prior trend is up or down using 5-bar MA slope
  const priorTrend = (i: number): "up" | "down" => {
    const window = Math.min(i, 5);
    if (window < 2) return "up";
    const avg = close.slice(i - window, i).reduce((a, b) => a + b, 0) / window;
    return close[i - 1] > avg ? "up" : "down";
  };

  for (let i = start; i < n; i++) {
    const o = open[i], h = high[i], l = low[i], c = close[i];
    const body = Math.abs(c - o);
    const range = h - l;
    const upperShadow = h - Math.max(o, c);
    const lowerShadow = Math.min(o, c) - l;
    const bodyMid = (o + c) / 2;
    const isBullish = c > o;

    // 十字星 (Doji): body < 0.3% of price
    if (body / c < 0.003 && range > 0) {
      results.push({ date: dates[i], pattern: "十字星", type: "neutral", strength: "moderate" });
      continue;
    }

    // 锤子线 / 上吊线: lower shadow > 2x body, upper shadow < 0.3x body, body in upper 1/3
    if (range > 0 && lowerShadow > 2 * body && upperShadow < 0.3 * body && (h - Math.max(o, c)) / range < 0.33) {
      const trend = priorTrend(i);
      if (trend === "down") {
        results.push({ date: dates[i], pattern: "锤子线", type: "bullish", strength: "strong" });
      } else {
        results.push({ date: dates[i], pattern: "上吊线", type: "bearish", strength: "moderate" });
      }
      continue;
    }

    // 流星线 (Shooting star): upper shadow > 2x body, lower shadow < 0.3x body
    if (range > 0 && upperShadow > 2 * body && lowerShadow < 0.3 * body && priorTrend(i) === "up") {
      results.push({ date: dates[i], pattern: "流星线", type: "bearish", strength: "strong" });
      continue;
    }

    if (i >= 1) {
      const po = open[i - 1], pc = close[i - 1];
      const prevBody = Math.abs(pc - po);

      // 吞没形态 (Engulfing)
      if (prevBody > 0 && body > prevBody) {
        const prevBearish = pc < po;
        const prevBullish = pc > po;
        if (isBullish && prevBearish && o <= pc && c >= po) {
          results.push({ date: dates[i], pattern: "看涨吞没", type: "bullish", strength: "strong" });
          continue;
        }
        if (!isBullish && prevBullish && o >= pc && c <= po) {
          results.push({ date: dates[i], pattern: "看跌吞没", type: "bearish", strength: "strong" });
          continue;
        }
      }

      // 孕线 (Harami): small body inside prev body
      const prevBodyTop = Math.max(po, pc);
      const prevBodyBot = Math.min(po, pc);
      if (prevBody > 0 && body < prevBody * 0.5 && Math.max(o, c) < prevBodyTop && Math.min(o, c) > prevBodyBot) {
        const type = priorTrend(i) === "down" ? "bullish" : "bearish";
        results.push({ date: dates[i], pattern: "孕线", type, strength: "moderate" });
        continue;
      }
    }

    // 启明星 / 黄昏星 (Morning/Evening Star): 3-bar pattern
    if (i >= 2) {
      const o0 = open[i - 2], c0 = close[i - 2];
      const o1 = open[i - 1], c1 = close[i - 1];
      const body0 = Math.abs(c0 - o0);
      const body1 = Math.abs(c1 - o1);
      const body2 = body;
      // Morning star: big down bar, small middle bar (gap down), big up bar
      if (c0 < o0 && body0 > body1 * 2 && body2 > body1 * 2 && isBullish &&
          Math.max(o1, c1) < Math.min(o0, c0) * 1.01 && c > bodyMid) {
        results.push({ date: dates[i], pattern: "启明星", type: "bullish", strength: "strong" });
        continue;
      }
      // Evening star: big up bar, small middle bar (gap up), big down bar
      if (c0 > o0 && body0 > body1 * 2 && body2 > body1 * 2 && !isBullish &&
          Math.min(o1, c1) > Math.max(o0, c0) * 0.99 && c < (open[i - 2] + close[i - 2]) / 2) {
        results.push({ date: dates[i], pattern: "黄昏星", type: "bearish", strength: "strong" });
        continue;
      }
    }
  }

  return results;
}

// ── 趋势线识别 ─────────────────────────────────────────────────────────────

export interface TrendLine {
  type: "support" | "resistance";
  slope: number;
  currentValue: number;
  touchCount: number;
  r2: number;
  isBreaking: boolean;
}

/** Least-squares linear regression over indexed points. Returns {slope, intercept, r2} */
function linReg(points: Array<[number, number]>): { slope: number; intercept: number; r2: number } {
  const n = points.length;
  if (n < 2) return { slope: 0, intercept: points[0]?.[1] ?? 0, r2: 0 };
  let sx = 0, sy = 0, sxy = 0, sx2 = 0, sy2 = 0;
  for (const [x, y] of points) { sx += x; sy += y; sxy += x * y; sx2 += x * x; sy2 += y * y; }
  const slope = (n * sxy - sx * sy) / (n * sx2 - sx * sx);
  const intercept = (sy - slope * sx) / n;
  const yMean = sy / n;
  const ssTot = sy2 - n * yMean * yMean;
  const ssRes = points.reduce((acc, [x, y]) => acc + (y - (slope * x + intercept)) ** 2, 0);
  const r2 = ssTot > 0 ? Math.max(0, 1 - ssRes / ssTot) : 0;
  return { slope, intercept, r2 };
}

/**
 * Identify dominant support and resistance trend lines from recent swing levels.
 * Uses window=5 swing detection and last `lookback` bars.
 */
export function trendLines(
  high: number[], low: number[], close: number[],
  window = 5, lookback = 60,
): TrendLine[] {
  const n = close.length;
  const start = Math.max(window, n - lookback);
  const curPrice = close[n - 1];

  // Collect swing highs and lows in the lookback window
  const swingHighs: Array<[number, number]> = [];
  const swingLows: Array<[number, number]> = [];
  for (let i = start + window; i < n - window; i++) {
    const hi = high.slice(i - window, i + window + 1);
    const lo = low.slice(i - window, i + window + 1);
    if (high[i] === Math.max(...hi)) swingHighs.push([i, high[i]]);
    if (low[i] === Math.min(...lo)) swingLows.push([i, low[i]]);
  }

  const lines: TrendLine[] = [];

  for (const [pts, type] of [[swingHighs, "resistance"], [swingLows, "support"]] as const) {
    if (pts.length < 2) continue;
    const { slope, intercept, r2: r2Val } = linReg(pts);
    const currentValue = slope * (n - 1) + intercept;
    // touchCount: points within 1% of trend line
    const touchCount = pts.filter(([x, y]) => Math.abs(y - (slope * x + intercept)) / y < 0.01).length;
    const breakThreshold = 0.01; // 1%
    const isBreaking = type === "resistance"
      ? curPrice > currentValue * (1 + breakThreshold)
      : curPrice < currentValue * (1 - breakThreshold);

    lines.push({
      type,
      slope: Math.round(slope * 10000) / 10000,
      currentValue: Math.round(currentValue * 100) / 100,
      touchCount,
      r2: Math.round(r2Val * 1000) / 1000,
      isBreaking,
    });
  }

  return lines;
}

// ── 斐波那契回调位 ─────────────────────────────────────────────────────────

export interface FibLevel {
  level: number;
  price: number;
  label: string;
  isNearCurrent: boolean;
}

/**
 * Compute Fibonacci retracement levels from swing high/low in the last `lookback` bars.
 */
export function fibonacci(
  high: number[], low: number[], close: number[],
  lookback = 60,
): {
  swingHigh: number;
  swingLow: number;
  direction: "retracing_up" | "retracing_down";
  levels: FibLevel[];
  nearestLevel: FibLevel | null;
} {
  const n = close.length;
  const slice = Math.min(lookback, n);
  const hiSlice = high.slice(n - slice);
  const loSlice = low.slice(n - slice);
  const swingHigh = Math.max(...hiSlice);
  const swingLow = Math.min(...loSlice);
  const curPrice = close[n - 1];
  const midPoint = (swingHigh + swingLow) / 2;
  const direction: "retracing_up" | "retracing_down" = curPrice >= midPoint ? "retracing_down" : "retracing_up";
  const range = swingHigh - swingLow;

  const fibRatios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
  const levels: FibLevel[] = fibRatios.map(r => {
    const price = direction === "retracing_down"
      ? swingHigh - r * range
      : swingLow + (1 - r) * range;
    const priceFmt = Math.round(price * 100) / 100;
    const isNearCurrent = Math.abs(curPrice - priceFmt) / curPrice < 0.02;
    return { level: r, price: priceFmt, label: `${(r * 100).toFixed(1)}%`, isNearCurrent };
  });

  const nearest = levels.reduce((best, lv) =>
    Math.abs(lv.price - curPrice) < Math.abs(best.price - curPrice) ? lv : best,
  );

  return { swingHigh: Math.round(swingHigh * 100) / 100, swingLow: Math.round(swingLow * 100) / 100, direction, levels, nearestLevel: nearest };
}

// ── 缺口识别 ───────────────────────────────────────────────────────────────

export interface PriceGap {
  date: string;
  type: "gap_up" | "gap_down";
  gapSize: number;
  gapPct: number;
  filled: boolean;
  fillDate?: string;
}

/**
 * Identify price gaps (跳空缺口) in the last `lookback` bars.
 * minGapPct: minimum gap size as percentage of price.
 */
export function priceGaps(
  dates: string[], high: number[], low: number[],
  minGapPct = 0.5,
  lookback = 60,
): PriceGap[] {
  const n = dates.length;
  const start = Math.max(1, n - lookback);
  const gaps: PriceGap[] = [];

  for (let i = start; i < n; i++) {
    const prevHigh = high[i - 1];
    const prevLow = low[i - 1];
    const curLow = low[i];
    const curHigh = high[i];

    // Gap up: today's low > yesterday's high
    if (curLow > prevHigh) {
      const gapSize = Math.round((curLow - prevHigh) * 100) / 100;
      const gapPct = Math.round((gapSize / prevHigh) * 10000) / 100;
      if (gapPct >= minGapPct) {
        // Check if filled: any subsequent bar closes into the gap [prevHigh, curLow]
        let filled = false;
        let fillDate: string | undefined;
        for (let j = i + 1; j < n; j++) {
          if (low[j] <= prevHigh) {
            filled = true;
            fillDate = dates[j];
            break;
          }
        }
        gaps.push({ date: dates[i], type: "gap_up", gapSize, gapPct, filled, fillDate });
      }
    }

    // Gap down: today's high < yesterday's low
    if (curHigh < prevLow) {
      const gapSize = Math.round((prevLow - curHigh) * 100) / 100;
      const gapPct = Math.round((gapSize / prevLow) * 10000) / 100;
      if (gapPct >= minGapPct) {
        let filled = false;
        let fillDate: string | undefined;
        for (let j = i + 1; j < n; j++) {
          if (high[j] >= prevLow) {
            filled = true;
            fillDate = dates[j];
            break;
          }
        }
        gaps.push({ date: dates[i], type: "gap_down", gapSize, gapPct, filled, fillDate });
      }
    }
  }

  return gaps;
}

// ── Swing Highs/Lows ───────────────────────────────────────────────────────

export interface SwingLevel { index: number; price: number; type: "high" | "low" }

/**
 * Find recent N swing highs and lows using a lookaround window.
 * Returns results in descending order by index (most recent first).
 */
export function swingLevels(
  high: number[], low: number[],
  window = 3, maxCount = 3,
): { highs: SwingLevel[]; lows: SwingLevel[] } {
  const len = high.length;
  const highs: SwingLevel[] = [];
  const lows: SwingLevel[] = [];

  for (let i = window; i < len - window; i++) {
    const hiSlice = high.slice(i - window, i + window + 1);
    const loSlice = low.slice(i - window, i + window + 1);
    if (high[i] === Math.max(...hiSlice)) highs.push({ index: i, price: high[i], type: "high" });
    if (low[i] === Math.min(...loSlice)) lows.push({ index: i, price: low[i], type: "low" });
  }

  return {
    highs: highs.reverse().slice(0, maxCount),
    lows: lows.reverse().slice(0, maxCount),
  };
}
