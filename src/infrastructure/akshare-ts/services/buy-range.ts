/**
 * Buy range calculation service
 */

import { fetchSinaKlines, klinesToNumbers, cleanSymbol } from "../../data-sources/sina.js";
import { rollingMean, bollinger, lastNum } from "../../data-sources/technical.js";
import { r2 } from "../shared.js";

export async function calculate_buy_range(symbol: string, current_price?: number): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const bars = await fetchSinaKlines(clean, 240, 90);
    if (!bars.length) return JSON.stringify({ error: `无历史数据: ${clean}`, symbol: clean });

    const { close, low } = klinesToNumbers(bars);
    const n = close.length;
    const dataDate = bars[n - 1].day; // 使用最后一根K线的日期

    const curPrice = current_price ?? close[n - 1];
    const ma20v = lastNum(rollingMean(close, 20)) ?? curPrice * 0.95;
    const ma60v = n >= 60 ? (lastNum(rollingMean(close, 60)) ?? ma20v * 0.95) : ma20v * 0.95;
    const recentLow = Math.min(...low.slice(-20));
    const bbLower = lastNum(bollinger(close).lower) ?? curPrice * 0.9;

    const techSupports = [ma20v, ma60v, recentLow, bbLower].sort((a, b) => a - b);
    const techSupport = (techSupports[0] + techSupports[1]) / 2;

    const idealBuy = r2(techSupport);
    const safeBuy = r2(techSupports[0]);
    const stopLoss = r2(safeBuy * 0.92);
    const target = r2(idealBuy + (idealBuy - stopLoss) * 2);

    let advice: string;
    if (curPrice <= idealBuy) {
      advice = `当前价${curPrice}已在买入区间内，可分批建仓: 安全价${safeBuy}(买40%), 理想价${idealBuy}(买40%), 留10%等更低价. 止损位${stopLoss}`;
    } else if (curPrice <= ma20v * 1.05) {
      advice = `当前价${curPrice}接近支撑区，可在${idealBuy}~${safeBuy}区间分批买入(30%/40%/30%). 止损位${stopLoss}, 目标价${target}`;
    } else {
      advice = `当前价${curPrice}高于支撑区(${idealBuy})，建议等待回调至${idealBuy}附近再建仓. 若追入，止损位${stopLoss}, 目标价${target}`;
    }

    return JSON.stringify({
      symbol: clean, current_price: r2(curPrice),
      safe_buy: safeBuy, ideal_buy: idealBuy, stop_loss: stopLoss, target_price: target,
      support_levels: { ma20: r2(ma20v), ma60: r2(ma60v), recent_low_20d: r2(recentLow), bollinger_lower: r2(bbLower) },
      advice, data_date: dataDate,
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}
