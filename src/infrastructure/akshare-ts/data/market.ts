/**
 * Market data layer - real-time prices, historical data, and basic info
 */

import {
  fetchSinaAShareRealtime, fetchSinaIndices, fetchSinaHKRealtime,
  parseSinaAShare, parseSinaHK, cleanSymbol as cleanSymbolInternal, sinaSymbol, hkCode,
} from "../../data-sources/sina.js";

// Re-export cleanSymbol for use by other modules
export { cleanSymbol } from "../../data-sources/sina.js";
import { fetchPeData, fetchStockInfo, fetchSectorList } from "../../data-sources/eastmoney.js";
import { fetchHkHistory } from "../../data-sources/stooq.js";
import { safeFloat, today, nowStr } from "../../data-sources/http-client.js";
import { r2, callPythonBridge, getKlineCache } from "../shared.js";

// ─── A股实时行情 ───────────────────────────────────────────────────────────

export async function get_stock_realtime_price(symbol: string): Promise<string> {
  const clean = cleanSymbolInternal(symbol);
  try {
    const [text, peData] = await Promise.all([
      fetchSinaAShareRealtime([sinaSymbol(clean)]),
      fetchPeData(clean),
    ]);
    const parsed = parseSinaAShare(text);
    if (!parsed) return JSON.stringify({ error: `未找到: ${clean}`, symbol: clean });

    const price = safeFloat(parsed.price);
    const prevClose = safeFloat(parsed.prevClose);
    const changeAmt = r2(price - prevClose);
    const changePct = prevClose ? r2((price - prevClose) / prevClose * 100) : 0;

    return JSON.stringify({
      symbol: clean, name: parsed.name,
      price, change_pct: changePct, change_amount: changeAmt,
      volume: safeFloat(parsed.volume, 0),
      amount: safeFloat(parsed.amount, 0),
      high: safeFloat(parsed.high), low: safeFloat(parsed.low),
      open: safeFloat(parsed.open), prev_close: prevClose,
      turnover_rate: 0,
      pe_dynamic: peData.pe_ttm ?? 0,
      pb: peData.pb ?? 0,
      market_cap_billion: peData.market_cap_billion ?? 0,
      data_date: `${parsed.date} ${parsed.time}`,
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

// ─── A股历史行情 ───────────────────────────────────────────────────────────

export async function get_stock_history(
  symbol: string,
  period = "daily",
  start?: string,
  end?: string,
  _adjust = "qfq",
  _skip_cache = false,
): Promise<string> {
  const clean = cleanSymbolInternal(symbol);

  // ─── 数据库缓存优先 ────────────────────────────────
  if (period === "daily" && !_skip_cache) {
    const startDate = start || "2023-01-01";
    const endDate = end || today();
    try {
      // KlineCacheService.getHistory 会在缺失时调用此函数（带 _skip_cache=true）
      const data = await getKlineCache().getHistory(clean, startDate, endDate);
      if (data && data.length > 0) {
        return JSON.stringify({
          symbol: clean,
          period,
          count: data.length,
          data,
          data_date: data[data.length - 1].date,
          _source: "cache"
        });
      }
    } catch (e) {
      console.warn(`[akshare-ts] Cache read failed for ${clean}:`, e);
    }
  }

  // ─── 网络获取 (通过 Python 桥) ──────────────────────
  try {
    const args = {
      symbol: clean,
      period,
      start_date: start,
      end_date: end,
      adjust: _adjust
    };
    // 直接调用 callPython 避免 TS 函数递归
    const raw = await callPythonBridge("get_stock_history", args);
    return JSON.stringify(raw);
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

// ─── A股基本信息 ───────────────────────────────────────────────────────────

export async function get_stock_info(symbol: string, saveToMemory = false): Promise<string> {
  const clean = cleanSymbolInternal(symbol);

  try {
    const [info, priceJson, peData] = await Promise.all([
      fetchStockInfo(clean),
      get_stock_realtime_price(clean),
      fetchPeData(clean),
    ]);
    const rt = JSON.parse(priceJson);

    const result = {
      symbol: clean,
      name: info.name || rt.name || clean,
      sector: info.sector || "",
      pe_ttm: peData.pe_ttm ?? rt.pe_dynamic ?? 0,
      pb: peData.pb ?? rt.pb ?? 0,
      market_cap_billion: peData.market_cap_billion ?? rt.market_cap_billion ?? 0,
      total_shares: (info as any).regCapital ?? "",
      circulating_shares: "",
      listed_date: (info as any).listedDate ?? (info as any).listed_date ?? "",
      data_date: today(),
    };

    return JSON.stringify(result);
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

// ─── 大盘概览 ──────────────────────────────────────────────────────────────

export async function get_market_overview(): Promise<string> {
  try {
    const text = await fetchSinaIndices();
    const names = ["上证指数", "深证成指", "创业板指", "沪深300", "中证500"];
    const lines = text.split("\n").map(l => l.trim()).filter(Boolean);

    const indices: Record<string, { price: number; change_pct: number }> = {};
    for (let i = 0; i < Math.min(names.length, lines.length); i++) {
      const content = lines[i].match(/"([^"]*)"/)?.[1] ?? "";
      const fields = content.split(",");
      if (fields.length < 4) continue;
      const prevClose = safeFloat(fields[2]);
      const price = safeFloat(fields[3]);
      const changePct = prevClose ? r2((price - prevClose) / prevClose * 100) : 0;
      indices[names[i]] = { price, change_pct: changePct };
    }
    return JSON.stringify({ indices, data_date: today() });
  } catch (e) {
    return JSON.stringify({ error: String(e) });
  }
}

// ─── 板块列表 ──────────────────────────────────────────────────────────────

export async function get_sector_list(): Promise<string> {
  try {
    const sectors = await fetchSectorList();
    if (sectors.length > 0) {
      const data = sectors.map(s => ({ name: s.name, code: s.code, count: 0, change_pct: s.changePct }));
      return JSON.stringify({ count: data.length, data, data_date: today() });
    }
    return JSON.stringify({ error: "板块数据暂时不可用", count: 0, data: [] });
  } catch (e) {
    return JSON.stringify({ error: String(e), count: 0, data: [] });
  }
}

// ─── 港股实时行情 ──────────────────────────────────────────────────────────

export async function get_hk_stock_price(symbol: string): Promise<string> {
  const code = hkCode(symbol);
  try {
    const text = await fetchSinaHKRealtime([code]);
    const parsed = parseSinaHK(text);
    if (!parsed) return JSON.stringify({ error: `未找到港股: ${code}`, symbol: code });
    return JSON.stringify({
      symbol: code, name: parsed.name,
      price: safeFloat(parsed.price), change_pct: safeFloat(parsed.changePct),
      change_amount: safeFloat(parsed.changeAmount),
      volume: safeFloat(parsed.volume, 0), amount: safeFloat(parsed.amount, 0),
      high: safeFloat(parsed.high), low: safeFloat(parsed.low),
      open: safeFloat(parsed.open), prev_close: safeFloat(parsed.prevClose),
      market: "HK", data_date: nowStr(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: code });
  }
}

// ─── 港股基本信息 ──────────────────────────────────────────────────────────

export async function get_hk_stock_info(symbol: string): Promise<string> {
  const code = hkCode(symbol);
  try {
    const priceJson = await get_hk_stock_price(code);
    const rt = JSON.parse(priceJson);
    if (rt.error) return priceJson;
    return JSON.stringify({
      symbol: code, name: rt.name, market: "HK",
      price: rt.price, change_pct: rt.change_pct,
      pe_ttm: 0, pb: 0, market_cap_billion: 0,
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: code });
  }
}

// ─── 港股历史行情 ──────────────────────────────────────────────────────────

export async function get_hk_stock_history(
  symbol: string,
  period = "daily",
): Promise<string> {
  const code = hkCode(symbol);
  const intervalMap: Record<string, "d" | "w" | "m"> = { daily: "d", weekly: "w", monthly: "m" };
  const interval = intervalMap[period] ?? "d";
  try {
    const bars = await fetchHkHistory(code, interval, 60);
    if (!bars.length) return JSON.stringify({ error: `无历史数据: ${symbol}`, symbol: code });
    let prevClose: number | null = null;
    const data = bars.map(b => {
      const changePct = prevClose ? r2((b.close - prevClose) / prevClose * 100) : 0;
      prevClose = b.close;
      return { date: b.date, open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume, change_pct: changePct };
    });
    const dataDate = bars[bars.length - 1].date; // 使用最后一根K线的日期
    return JSON.stringify({ symbol: code, period, count: data.length, market: "HK", data, data_date: dataDate });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: code });
  }
}
