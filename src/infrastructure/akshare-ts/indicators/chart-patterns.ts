/**
 * Chart pattern recognition and candlestick analysis
 */

import {
  candlestickPatterns, trendLines, fibonacci, priceGaps,
} from "../../data-sources/technical.js";
import { fetchSinaKlines, klinesToNumbers, cleanSymbol } from "../../data-sources/sina.js";
import { safeFloat, today } from "../../data-sources/http-client.js";
import { r2 } from "../shared.js";

/**
 * analyze_candlestick - K线形态识别
 *
 * 分析K线形态、趋势线、斐波那契回调位和跳空缺口
 */
export async function analyze_candlestick(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const bars = await fetchSinaKlines(clean, 240, 120);
    if (bars.length < 30) return JSON.stringify({ error: "历史数据不足，无法进行K线形态分析", symbol: clean });

    const { high, low, close } = klinesToNumbers(bars);
    const open = bars.map(b => safeFloat(b.open));
    const dates = bars.map(b => b.day);
    const n = close.length;
    const curPrice = r2(close[n - 1]);

    // 1. K线形态
    const patterns = candlestickPatterns(dates, open, high, low, close, 10);

    // 2. 趋势线
    const lines = trendLines(high, low, close, 5, 60);

    // 3. 斐波那契
    const fib = fibonacci(high, low, close, 60);

    // 4. 缺口
    const gaps = priceGaps(dates, high, low, 0.5, 60);

    // 生成摘要
    const parts: string[] = [];
    if (patterns.length > 0) {
      const latest = patterns[patterns.length - 1];
      parts.push(`最近出现${latest.pattern}（${latest.type === "bullish" ? "看涨" : latest.type === "bearish" ? "看跌" : "中性"}信号）`);
    }
    if (fib.nearestLevel) {
      parts.push(`价格在斐波那契${fib.nearestLevel.label}回调位(${fib.nearestLevel.price})附近`);
    }
    const breakingLines = lines.filter(l => l.isBreaking);
    if (breakingLines.length > 0) {
      const bl = breakingLines[0];
      parts.push(`正在突破${bl.type === "resistance" ? "阻力" : "支撑"}趋势线(${bl.currentValue})`);
    }
    const unfilledGaps = gaps.filter(g => !g.filled);
    if (unfilledGaps.length > 0) {
      parts.push(`存在${unfilledGaps.length}个未回补跳空缺口（最近：${unfilledGaps[unfilledGaps.length - 1].date} ${unfilledGaps[unfilledGaps.length - 1].type === "gap_up" ? "跳空向上" : "跳空向下"}${unfilledGaps[unfilledGaps.length - 1].gapPct}%）`);
    }
    const summary = parts.length > 0 ? parts.join("，") + "。" : "未检测到显著K线形态信号。";

    return JSON.stringify({
      symbol: clean,
      current_price: curPrice,
      patterns,
      trend_lines: lines,
      fibonacci: fib,
      gaps,
      summary,
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}
