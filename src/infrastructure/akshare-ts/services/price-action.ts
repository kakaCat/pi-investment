/**
 * Price action analysis service
 */

import { fetchSinaKlines, klinesToNumbers, cleanSymbol } from "../../data-sources/sina.js";
import {
  rollingMean, swingLevels, obv, atr, kdj, cci, rsi, lastNum,
} from "../../data-sources/technical.js";
import { today } from "../../data-sources/http-client.js";
import { r2 } from "../shared.js";

/**
 * analyze_price_action - 走势分析（趋势、支撑阻力、突破信号、成交量、动量）
 */
export async function analyze_price_action(symbol: string, period = 60): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const lookback = Math.max(60, Math.min(period, 250));
    const bars = await fetchSinaKlines(clean, 240, lookback);
    if (bars.length < 60) return JSON.stringify({ error: "历史数据不足60天，无法进行走势分析", symbol: clean });

    const { high, low, close, volume } = klinesToNumbers(bars);
    const n = close.length;
    const ma5v = lastNum(rollingMean(close, 5)) ?? close[n - 1];
    const ma20v = lastNum(rollingMean(close, 20)) ?? close[n - 1];
    const ma60v = n >= 60 ? (lastNum(rollingMean(close, 60)) ?? close[n - 1]) : close[n - 1];
    const cur = close[n - 1];
    const prev = close[n - 2] ?? cur;

    const periodReturn = r2((cur - close[0]) / close[0] * 100);
    const trendDirection =
      cur > ma20v && ma20v >= ma60v && periodReturn > 5 ? "上升" :
      cur < ma20v && ma20v <= ma60v && periodReturn < -5 ? "下降" :
      "震荡";

    const swings = swingLevels(high, low, 3, 3);
    const supportLevels = Array.from(new Set(
      swings.lows.map(level => r2(level.price)).filter(level => level < cur),
    )).sort((a, b) => b - a).slice(0, 3);
    const resistanceLevels = Array.from(new Set(
      swings.highs.map(level => r2(level.price)).filter(level => level > cur),
    )).sort((a, b) => a - b).slice(0, 3);

    if (!supportLevels.length) supportLevels.push(r2(Math.min(ma20v, ma60v, cur * 0.95)));
    if (!resistanceLevels.length) resistanceLevels.push(r2(Math.max(ma20v, ma60v, cur * 1.05)));

    const recentHigh = Math.max(...high.slice(-20, -1));
    const recentLow = Math.min(...low.slice(-20, -1));
    const vol5Avg = volume.slice(-6, -1).reduce((sum, v) => sum + v, 0) / Math.max(1, Math.min(5, volume.length - 1));
    const vol20Avg = volume.slice(-21, -1).reduce((sum, v) => sum + v, 0) / Math.max(1, Math.min(20, volume.length - 1));
    const latestVolume = volume[n - 1];
    const volRatio5 = vol5Avg > 0 ? r2(latestVolume / vol5Avg) : 1;
    const volRatio20 = vol20Avg > 0 ? r2(latestVolume / vol20Avg) : 1;
    const volumeChangePct = vol5Avg > 0 ? r2((latestVolume - vol5Avg) / vol5Avg * 100) : 0;

    const obvArr = obv(close, volume);
    const obvTrend = obvArr[n - 1] >= obvArr[Math.max(0, n - 5)] ? "上升" : "下降";
    const atrArr = atr(high, low, close, 14);
    const atrLast = r2(atrArr[n - 1]);
    const { k, d, j } = kdj(high, low, close);
    const cciArr = cci(high, low, close, 20);

    const breakoutSignal =
      cur > recentHigh * 1.005 && prev <= recentHigh && volRatio5 >= 1.2
        ? { signal: "向上突破", confirmed: true, reference_level: r2(recentHigh), reason: "价格突破近20日高点且放量" }
        : cur < recentLow * 0.995 && prev >= recentLow && volRatio5 >= 1.2
        ? { signal: "向下跌破", confirmed: true, reference_level: r2(recentLow), reason: "价格跌破近20日低点且放量" }
        : { signal: "未突破", confirmed: false, reference_level: cur >= prev ? r2(recentHigh) : r2(recentLow), reason: "价格仍处于区间内运行" };

    return JSON.stringify({
      symbol: clean,
      period_days: lookback,
      current_price: r2(cur),
      trend: {
        direction: trendDirection,
        period_return_pct: periodReturn,
        short_term: ma5v > ma20v ? "偏强" : "偏弱",
        medium_term: ma20v > ma60v ? "偏强" : "偏弱",
        ma_values: { ma5: r2(ma5v), ma20: r2(ma20v), ma60: r2(ma60v) },
      },
      support_levels: supportLevels,
      resistance_levels: resistanceLevels,
      volume_analysis: {
        latest_volume: r2(latestVolume),
        avg_volume_5d: r2(vol5Avg),
        avg_volume_20d: r2(vol20Avg),
        volume_change_pct: volumeChangePct,
        volume_ratio_5d: volRatio5,
        volume_ratio_20d: volRatio20,
        obv_trend: obvTrend,
        status: volRatio5 >= 1.5 ? "放量" : volRatio5 <= 0.8 ? "缩量" : "平稳",
      },
      breakout_signal: breakoutSignal,
      momentum: {
        kdj: { k: r2(k[n - 1]), d: r2(d[n - 1]), j: r2(j[n - 1]) },
        cci: r2(lastNum(cciArr)),
        rsi_14: r2(lastNum(rsi(close, 14))),
      },
      volatility: {
        atr_14: atrLast,
        atr_pct: cur > 0 ? r2(atrLast / cur * 100) : 0,
      },
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}
