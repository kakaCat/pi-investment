/**
 * Technical indicators calculation layer
 */

import {
  rollingMean, rsi as calcRsi, macd as calcMacd, bollinger, lastNum,
  kdj as calcKdj, atr as calcAtr, obv as calcObv, cci as calcCci,
} from "../../data-sources/technical.js";
import { klinesToNumbers, cleanSymbol } from "../../data-sources/sina.js";
import { get_stock_history, get_stock_realtime_price } from "../data/market.js";
import { r2, r4 } from "../shared.js";
import { today } from "../../data-sources/http-client.js";

export async function calculate_technical_indicators(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    // 1. 获取历史 K 线 (优先从数据库缓存获取最近 120 天数据)
    const historyJson = await get_stock_history(clean, "daily", undefined, undefined);
    const historyRes = JSON.parse(historyJson);
    if (historyRes.error) return historyJson;
    let bars = historyRes.data || [];

    // 2. 获取实时价格 (用于补充最新的当日报价)
    const realtimeJson = await get_stock_realtime_price(clean);
    const rt = JSON.parse(realtimeJson);

    // 3. 混合模式：如果实时日期比缓存日期更新，则将实时报价追加为最新的一根 K 线
    const todayStr = today();
    const lastBar = bars.length > 0 ? bars[bars.length - 1] : null;

    // 只在实时报价本身也是今日数据时才追加合成 K 线，
    // 避免周末/节假日/盘前用前一交易日收盘价创建错误的"今日"K 线
    const rtDate = (rt?.data_date || rt?.date || rt?.time)?.slice(0, 10);
    const rtIsToday = rtDate === todayStr;
    if (rt && rt.price && rtIsToday && (!lastBar || lastBar.date < todayStr)) {
      // 避免重复添加 (比如今天还没收盘，但缓存里已经有了今天的懒加载数据)
      const currentBar = {
        day: todayStr, // SinaKlines 内部使用 day 字段
        date: todayStr,
        open: rt.open || rt.price,
        high: rt.high || rt.price,
        low: rt.low || rt.price,
        close: rt.price,
        volume: rt.volume || 0,
        _is_realtime: true
      };
      bars.push(currentBar);
    }

    if (bars.length < 30) return JSON.stringify({ error: "历史数据不足", symbol: clean });

    const { close } = klinesToNumbers(bars);
    const n = close.length;
    const dataDate = bars[n - 1].date || bars[n - 1].day;

    const ma5  = r2(lastNum(rollingMean(close, 5)));
    const ma10 = r2(lastNum(rollingMean(close, 10)));
    const ma20 = r2(lastNum(rollingMean(close, 20)));
    const ma60 = n >= 60 ? r2(lastNum(rollingMean(close, 60))) : null;

    const { dif, dea, histogram } = calcMacd(close);
    const rsiArr = calcRsi(close, 14);
    const bb = bollinger(close);

    const curPrice = close[n - 1];
    const rsiVal = r2(lastNum(rsiArr));
    const difLast = r4(dif[n - 1]);
    const deaLast = r4(dea[n - 1]);
    const histLast = r4(histogram[n - 1]);

    const signals: string[] = [];
    if (ma5 && ma20 && curPrice > ma5 && ma5 > ma20) signals.push("短期多头排列");
    else if (ma5 && ma20 && curPrice < ma5 && ma5 < ma20) signals.push("短期空头排列");
    if (ma60 !== null) {
      if (curPrice > ma60) signals.push("站上60日均线");
      else signals.push("跌破60日均线");
    }
    if (rsiVal !== null) {
      if (rsiVal > 70) signals.push("RSI超买");
      else if (rsiVal < 30) signals.push("RSI超卖");
    }
    signals.push(difLast > deaLast ? "MACD金叉" : "MACD死叉");

    return JSON.stringify({
      symbol: clean, current_price: r2(curPrice),
      ma: { ma5, ma10, ma20, ma60 },
      // Also expose flat fields for compatibility
      ma5, ma10, ma20, ma60,
      macd: { dif: difLast, dea: deaLast, histogram: histLast },
      macd_histogram: histLast,
      rsi_14: rsiVal, rsi: rsiVal,
      bollinger: {
        upper: r2(lastNum(bb.upper)),
        mid: r2(lastNum(bb.mid)),
        lower: r2(lastNum(bb.lower)),
      },
      signals,
      data_date: dataDate,
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}
