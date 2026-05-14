/**
 * AkShare-TS — TypeScript-native market data
 *
 * Drop-in replacement for the Python akshare_bridge functions that only
 * require Sina / Eastmoney / stooq HTTP APIs.
 *
 * Functions returning JSON strings matching the Python bridge output format.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { execFile } from "child_process";
import { promisify } from "util";
import { fileURLToPath } from "url";
import { memoryService } from "../../services/data/cache-service.js";
import { stockMemoryService } from "../../services/data/stock-memory-service.js";
import {
  fetchSinaAShareRealtime, fetchSinaHKRealtime, fetchSinaIndices,
  fetchSinaKlines, klinesToNumbers,
  parseSinaAShare, parseSinaHK, cleanSymbol, sinaSymbol, hkCode,
} from "../data-sources/sina.js";
import { fetchPeData, fetchStockInfo, fetchSectorList } from "../data-sources/eastmoney.js";
import { fetchHkHistory } from "../data-sources/stooq.js";
import {
  rollingMean, rsi as calcRsi, macd as calcMacd, bollinger, lastNum, roundN,
  kdj as calcKdj, atr as calcAtr, obv as calcObv, cci as calcCci, swingLevels,
  candlestickPatterns, trendLines, fibonacci, priceGaps,
} from "../data-sources/technical.js";
import { safeFloat, today, nowStr } from "../data-sources/http-client.js";
import { StockDBService, KlineCacheService } from "../../services/data/stock-db-index.js";
import { callPythonDaemon } from "../tools/python-bridge.js";

// ─── Shared Services (懒加载避免循环依赖) ──────────────────────────────────
const piDir = ".pi-invest";
let _stockDB: StockDBService | null = null;
let _klineCache: KlineCacheService | null = null;

function getStockDB() {
  if (!_stockDB) _stockDB = new StockDBService(piDir);
  return _stockDB;
}

function getKlineCache() {
  if (!_klineCache) _klineCache = new KlineCacheService(getStockDB());
  return _klineCache;
}

// ─── Helpers ───────────────────────────────────────────────────────────────

const execFileAsync = promisify(execFile);
const __dirname = fileURLToPath(new URL(".", import.meta.url));

function r2(v: number | null): number { return roundN(v, 2) ?? 0; }
function r4(v: number | null): number { return roundN(v, 4) ?? 0; }

type JsonRecord = Record<string, unknown>;

async function callPythonBridge(func: string, args: Record<string, unknown> = {}): Promise<JsonRecord> {
  const result = await callPythonDaemon(func, args);
  return JSON.parse(result) as JsonRecord;
}

function toNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value === "string") {
    const raw = value.trim();
    const unit = raw.includes("亿") ? 1e8 : raw.includes("万") ? 1e4 : 1;
    const cleaned = raw.replace(/,/g, "").replace(/%/g, "").replace(/[^\d.-]/g, "");
    const num = Number.parseFloat(cleaned);
    return Number.isFinite(num) ? num * unit : 0;
  }
  return 0;
}

function findNumber(record: JsonRecord, keys: readonly string[]): number {
  for (const key of keys) {
    if (key in record && record[key] != null && `${record[key]}` !== "") {
      return toNumber(record[key]);
    }
  }
  return 0;
}

function findString(record: JsonRecord, keys: readonly string[]): string {
  for (const key of keys) {
    if (key in record && record[key] != null && `${record[key]}`.trim() !== "") {
      return String(record[key]).trim();
    }
  }
  return "";
}

function median(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function normalizeHolderName(name: string): string {
  return name.replace(/\s+/g, "").replace(/[（(].*?[）)]/g, "").trim();
}

function computeQuarterEnds(limit = 8): string[] {
  const [year, month, day] = today().split("-").map(Number);
  const quarterEnds = [
    { month: 3, day: 31, suffix: "0331" },
    { month: 6, day: 30, suffix: "0630" },
    { month: 9, day: 30, suffix: "0930" },
    { month: 12, day: 31, suffix: "1231" },
  ];

  const result: string[] = [];
  let currentYear = year;
  while (result.length < limit) {
    for (let i = quarterEnds.length - 1; i >= 0 && result.length < limit; i--) {
      const end = quarterEnds[i];
      if (
        currentYear === year &&
        (month < end.month || (month === end.month && day <= end.day))
      ) {
        continue;
      }
      result.push(`${currentYear}${end.suffix}`);
    }
    currentYear -= 1;
  }
  return result;
}

export function getQualityRating(score: number): "优秀" | "良好" | "一般" | "较差" {
  if (score >= 80) return "优秀";
  if (score >= 65) return "良好";
  if (score >= 50) return "一般";
  return "较差";
}

// ─── A股实时行情 ───────────────────────────────────────────────────────────

export async function get_stock_realtime_price(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
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
  const clean = cleanSymbol(symbol);

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
  const clean = cleanSymbol(symbol);

  // 先查记忆
  const cached = stockMemoryService.get(clean);

  try {
    const [info, priceJson, peData] = await Promise.all([
      cached ? Promise.resolve(cached) : fetchStockInfo(clean),
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

    // 只在明确需要时保存到记忆
    if (saveToMemory && !cached) {
      stockMemoryService.add({
        symbol: clean,
        name: result.name,
        sector: result.sector,
        listed_date: result.listed_date,
      });
    }

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

// ─── 技术指标 ──────────────────────────────────────────────────────────────

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

// ─── 买入区间 ──────────────────────────────────────────────────────────────

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

// ─── 估值 ─────────────────────────────────────────────────────────────────

export async function get_stock_valuation(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    // Fallback to Python akshare (network restrictions on TS sources)
    return JSON.stringify(await callPythonBridge("get_stock_valuation", { symbol: clean }));
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

// ─── PE历史分位数 ──────────────────────────────────────────────────────────

export async function get_pe_percentile(symbol: string, years = 3): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    // Use Python bridge for PE data (network restrictions on TS sources)
    return JSON.stringify(await callPythonBridge("get_pe_percentile", { symbol: clean, years }));
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

function extractStatementRows(payload: JsonRecord, sectionKey: string): JsonRecord[] {
  const section = payload[sectionKey];
  if (section && typeof section === "object" && !Array.isArray(section)) {
    const data = (section as JsonRecord).data;
    if (Array.isArray(data)) return data as JsonRecord[];
  }
  const direct = payload.data;
  return Array.isArray(direct) ? direct as JsonRecord[] : [];
}

export async function get_quality_score(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const [financials, incomePayload, cashPayload] = await Promise.all([
      callPythonBridge("get_financial_indicators", { symbol: clean }),
      callPythonBridge("get_income_statement", { symbol: clean, recent_n: 8 }),
      callPythonBridge("get_cash_flow", { symbol: clean, recent_n: 8 }),
    ]);

    if (financials.error) return JSON.stringify(financials);

    const finRows = Array.isArray(financials.data)
      ? financials.data as JsonRecord[]
      : Array.isArray(financials.quarters)
      ? financials.quarters as JsonRecord[]
      : [];
    if (!finRows.length) return JSON.stringify({ error: `无财务数据: ${clean}`, symbol: clean });

    const incomeRows = extractStatementRows(incomePayload, "income_statement");
    const cashRows = extractStatementRows(cashPayload, "cash_flow");
    const latest = finRows[0];
    const latestIncome = incomeRows[0] ?? {};
    const latestCash = cashRows[0] ?? {};

    const roe = findNumber(latest, ["roe", "净资产收益率(%)", "加权净资产收益率(%)"]);
    const grossMargin = findNumber(latest, ["gross_margin", "销售毛利率(%)", "毛利率"]);
    const debtRatio = findNumber(latest, ["debt_ratio", "资产负债率(%)"]);

    const roeSeries = finRows
      .slice(0, 4)
      .map(row => findNumber(row, ["roe", "净资产收益率(%)", "加权净资产收益率(%)"]))
      .filter(v => v !== 0);
    const latestRevenue = findNumber(latestIncome, ["营业总收入", "营业收入"]);
    const previousRevenue = incomeRows
      .slice(1)
      .map(row => findNumber(row, ["营业总收入", "营业收入"]))
      .find(v => v > 0) ?? 0;
    const revenueGrowth = previousRevenue > 0 ? r2((latestRevenue - previousRevenue) / previousRevenue * 100) : 0;

    const operatingCashFlow = findNumber(latestCash, [
      "经营活动产生的现金流量净额",
      "经营活动现金流量净额",
      "经营现金流量净额",
    ]);
    const netProfit = findNumber(latestIncome, [
      "净利润",
      "归属于母公司股东的净利润",
      "归母净利润",
      "净利润(含少数股东损益)",
    ]);
    const cashFlowCoverage = netProfit !== 0 ? r2(operatingCashFlow / Math.abs(netProfit) * 100) : 0;
    const recentCashFlowPositive = cashRows
      .slice(0, 3)
      .map(row => findNumber(row, [
        "经营活动产生的现金流量净额",
        "经营活动现金流量净额",
        "经营现金流量净额",
      ]))
      .filter(v => v !== 0);
    const positiveCashFlowCount = recentCashFlowPositive.filter(v => v > 0).length;

    let roeScore = roe >= 20 ? 23 : roe >= 15 ? 20 : roe >= 10 ? 15 : roe >= 5 ? 8 : roe > 0 ? 3 : 0;
    if (roeSeries.length >= 3) {
      if (roeSeries[0] >= roeSeries[1] && roeSeries[1] >= roeSeries[2]) roeScore += 2;
      else if (roeSeries[0] < roeSeries[1] && roeSeries[1] < roeSeries[2]) roeScore -= 2;
    }
    roeScore = Math.max(0, Math.min(25, roeScore));

    const grossMarginScore =
      grossMargin >= 50 ? 20 :
      grossMargin >= 35 ? 16 :
      grossMargin >= 20 ? 11 :
      grossMargin >= 10 ? 6 : 2;

    const debtScore =
      debtRatio <= 30 ? 15 :
      debtRatio <= 45 ? 12 :
      debtRatio <= 60 ? 8 :
      debtRatio <= 75 ? 4 : 0;

    let cashFlowScore =
      operatingCashFlow > 0 && cashFlowCoverage >= 120 ? 20 :
      operatingCashFlow > 0 && cashFlowCoverage >= 100 ? 17 :
      operatingCashFlow > 0 && cashFlowCoverage >= 70 ? 13 :
      operatingCashFlow > 0 ? 8 : 0;
    if (positiveCashFlowCount >= 2) cashFlowScore = Math.min(20, cashFlowScore + 2);

    const revenueGrowthScore =
      revenueGrowth >= 25 ? 20 :
      revenueGrowth >= 15 ? 16 :
      revenueGrowth >= 5 ? 11 :
      revenueGrowth >= 0 ? 7 :
      revenueGrowth >= -10 ? 3 : 0;

    const totalScore = Math.max(0, Math.min(100, roeScore + grossMarginScore + debtScore + cashFlowScore + revenueGrowthScore));
    const rating = getQualityRating(totalScore);

    return JSON.stringify({
      symbol: clean,
      score: totalScore,
      rating,
      dimensions: {
        roe: {
          value_pct: r2(roe),
          score: roeScore,
          weight: 25,
          trend: roeSeries.length >= 3
            ? (roeSeries[0] >= roeSeries[1] && roeSeries[1] >= roeSeries[2] ? "改善" : roeSeries[0] < roeSeries[1] && roeSeries[1] < roeSeries[2] ? "走弱" : "波动")
            : "数据不足",
        },
        gross_margin: { value_pct: r2(grossMargin), score: grossMarginScore, weight: 20 },
        debt_ratio: { value_pct: r2(debtRatio), score: debtScore, weight: 15 },
        cash_flow: {
          operating_cash_flow: r2(operatingCashFlow),
          net_profit: r2(netProfit),
          cash_conversion_pct: r2(cashFlowCoverage),
          score: cashFlowScore,
          weight: 20,
        },
        revenue_growth: {
          latest_revenue: r2(latestRevenue),
          previous_revenue: r2(previousRevenue),
          growth_pct: r2(revenueGrowth),
          score: revenueGrowthScore,
          weight: 20,
        },
      },
      summary: totalScore >= 80 ? "盈利质量与成长性较强" : totalScore >= 65 ? "基本面较稳健" : totalScore >= 50 ? "基本面中性" : "基本面偏弱需谨慎",
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

export async function get_stock_fund_flow(symbol: string, days = 5): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const payload = await callPythonBridge("get_stock_fund_flow", { symbol: clean });
    if (payload.error) return JSON.stringify(payload);

    const rows = Array.isArray(payload.data) ? payload.data as JsonRecord[] : [];
    const selected = rows.slice(-Math.max(1, Math.min(days, rows.length)));
    if (!selected.length) return JSON.stringify({ error: `无资金流向数据: ${clean}`, symbol: clean });

    const categories = {
      main_force: {
        label: "主力",
        amountKeys: ["主力净流入-净额", "主力净流入", "主力净额"],
        ratioKeys: ["主力净流入-净占比", "主力净流入净占比", "主力净占比"],
      },
      large_order: {
        label: "大单",
        amountKeys: ["大单净流入-净额", "大单净流入", "大单净额"],
        ratioKeys: ["大单净流入-净占比", "大单净流入净占比", "大单净占比"],
      },
      medium_order: {
        label: "中单",
        amountKeys: ["中单净流入-净额", "中单净流入", "中单净额"],
        ratioKeys: ["中单净流入-净占比", "中单净流入净占比", "中单净占比"],
      },
      small_order: {
        label: "小单",
        amountKeys: ["小单净流入-净额", "小单净流入", "小单净额"],
        ratioKeys: ["小单净流入-净占比", "小单净流入净占比", "小单净占比"],
      },
    } as const;

    const totals = Object.fromEntries(
      Object.entries(categories).map(([key, meta]) => {
        const net = selected.reduce((sum, row) => sum + findNumber(row, meta.amountKeys), 0);
        const ratioValues = selected
          .map(row => findNumber(row, meta.ratioKeys))
          .filter(v => v !== 0);
        return [key, {
          label: meta.label,
          net_inflow: r2(net),
          avg_ratio_pct: ratioValues.length ? r2(ratioValues.reduce((sum, v) => sum + v, 0) / ratioValues.length) : 0,
        }];
      }),
    ) as Record<string, { label: string; net_inflow: number; avg_ratio_pct: number }>;

    const trackedBase = Object.values(totals).reduce((sum, item) => sum + Math.abs(item.net_inflow), 0);
    for (const item of Object.values(totals)) {
      (item as JsonRecord).ratio_pct = trackedBase > 0 ? r2(item.net_inflow / trackedBase * 100) : 0;
      (item as JsonRecord).direction = item.net_inflow >= 0 ? "流入" : "流出";
    }

    const dominantCategory = Object.entries(totals)
      .sort(([, a], [, b]) => Math.abs(b.net_inflow) - Math.abs(a.net_inflow))[0];

    return JSON.stringify({
      symbol: clean,
      days: selected.length,
      categories: totals,
      dominant_force: dominantCategory ? {
        key: dominantCategory[0],
        label: dominantCategory[1].label,
        net_inflow: dominantCategory[1].net_inflow,
      } : null,
      daily_dates: selected.map(row => findString(row, ["日期", "date"])).filter(Boolean),
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

async function fetchTopHolderSnapshot(symbol: string, reportDate: string): Promise<{
  report_date: string;
  holders: Array<{ holder_name: string; normalized_name: string; shares: number; ratio_pct: number }>;
} | null> {
  const payload = await callPythonBridge("get_top_holders", { symbol, date: reportDate });
  if (payload.error) return null;
  const rows = Array.isArray(payload.data) ? payload.data as JsonRecord[] : [];
  if (!rows.length) return null;

  const holders = rows.map(row => {
    const holderName = findString(row, ["股东名称", "股东名次", "股东", "name"]);
    return {
      holder_name: holderName,
      normalized_name: normalizeHolderName(holderName),
      shares: findNumber(row, ["持股数", "持股数量", "持股总数", "持股数量(股)", "期末持股-数量"]),
      ratio_pct: findNumber(row, ["占总股本持股比例", "持股比例", "持股比例(%)", "总股本占比"]),
    };
  }).filter(holder => holder.holder_name);

  return holders.length ? { report_date: reportDate, holders } : null;
}

export async function get_holder_changes(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const quarterEnds = computeQuarterEnds(8);
    const snapshots: Array<Awaited<ReturnType<typeof fetchTopHolderSnapshot>>> = [];

    for (const quarterEnd of quarterEnds) {
      const snapshot = await fetchTopHolderSnapshot(clean, quarterEnd);
      if (snapshot) snapshots.push(snapshot);
      if (snapshots.length >= 2) break;
    }

    if (snapshots.length < 2 || !snapshots[0] || !snapshots[1]) {
      return JSON.stringify({ error: `无法获取最近两个季度的十大股东数据: ${clean}`, symbol: clean });
    }

    const [latest, previous] = snapshots as [
      { report_date: string; holders: Array<{ holder_name: string; normalized_name: string; shares: number; ratio_pct: number }> },
      { report_date: string; holders: Array<{ holder_name: string; normalized_name: string; shares: number; ratio_pct: number }> },
    ];

    const previousMap = new Map(previous.holders.map(holder => [holder.normalized_name, holder]));
    const latestMap = new Map(latest.holders.map(holder => [holder.normalized_name, holder]));

    const newHolders: JsonRecord[] = [];
    const reducedHolders: JsonRecord[] = [];
    const increasedHolders: JsonRecord[] = [];
    const exitedHolders: JsonRecord[] = [];

    for (const holder of latest.holders) {
      const prev = previousMap.get(holder.normalized_name);
      if (!prev) {
        newHolders.push({
          holder_name: holder.holder_name,
          current_shares: r2(holder.shares),
          current_ratio_pct: r2(holder.ratio_pct),
        });
        continue;
      }
      const shareChange = holder.shares - prev.shares;
      const ratioChange = holder.ratio_pct - prev.ratio_pct;
      const item = {
        holder_name: holder.holder_name,
        previous_shares: r2(prev.shares),
        current_shares: r2(holder.shares),
        share_change: r2(shareChange),
        previous_ratio_pct: r2(prev.ratio_pct),
        current_ratio_pct: r2(holder.ratio_pct),
        ratio_change_pct: r2(ratioChange),
      };
      if (shareChange < 0 || ratioChange < 0) reducedHolders.push(item);
      else if (shareChange > 0 || ratioChange > 0) increasedHolders.push(item);
    }

    for (const holder of previous.holders) {
      if (!latestMap.has(holder.normalized_name)) {
        exitedHolders.push({
          holder_name: holder.holder_name,
          previous_shares: r2(holder.shares),
          previous_ratio_pct: r2(holder.ratio_pct),
        });
      }
    }

    reducedHolders.sort((a, b) => Math.abs(toNumber(b.ratio_change_pct)) - Math.abs(toNumber(a.ratio_change_pct)));
    increasedHolders.sort((a, b) => Math.abs(toNumber(b.ratio_change_pct)) - Math.abs(toNumber(a.ratio_change_pct)));

    return JSON.stringify({
      symbol: clean,
      comparison_quarters: {
        latest: latest.report_date,
        previous: previous.report_date,
      },
      new_holders: newHolders,
      reduced_holders: reducedHolders,
      increased_holders: increasedHolders,
      exited_holders: exitedHolders,
      summary: {
        new_count: newHolders.length,
        reduced_count: reducedHolders.length,
        increased_count: increasedHolders.length,
        exited_count: exitedHolders.length,
      },
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

// ─── 止盈计划 ─────────────────────────────────────────────────────────────

export async function get_exit_plan(symbol: string, buy_price: number, shares = 100): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const priceJson = await get_stock_realtime_price(clean);
    const rt = JSON.parse(priceJson);
    if (rt.error) return priceJson;
    const curPrice: number = rt.price;
    const pe: number = rt.pe_dynamic ?? 0;

    let tC: number, tM: number, tA: number;
    if (pe > 0 && curPrice > 0) {
      const eps = curPrice / pe;
      const basePe = Math.min(pe, 28.5);
      tC = r2(eps * basePe * 1.2);
      tM = r2(eps * basePe * 1.5);
      tA = r2(eps * basePe * 2.0);
    } else {
      tC = r2(buy_price * 1.20);
      tM = r2(buy_price * 1.40);
      tA = r2(buy_price * 1.60);
    }

    const pnlPct = r2((curPrice - buy_price) / buy_price * 100);
    const pnlAmt = r2((curPrice - buy_price) * shares);
    const plan: string[] = [];
    if (curPrice >= tC) plan.push(`已达保守目标(${tC})，建议卖出30%`);
    if (curPrice >= tM) plan.push(`已达中等目标(${tM})，建议再卖40%`);
    if (curPrice >= tA) plan.push(`已达激进目标(${tA})，建议清仓剩余30%`);
    if (!plan.length) {
      const pctToTarget = r2((tC - curPrice) / curPrice * 100);
      plan.push(`距保守目标(${tC})还有${pctToTarget}%，继续持有`);
    }

    return JSON.stringify({
      symbol: clean, name: rt.name, buy_price, current_price: curPrice, shares,
      pnl_pct: pnlPct, pnl_amount: pnlAmt,
      targets: { conservative: tC, moderate: tM, aggressive: tA },
      sell_plan: plan, data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

// ─── 持仓管理 ─────────────────────────────────────────────────────────────

const portfolioPath = join(process.cwd(), ".pi-invest", "portfolio.json");

interface PortfolioData {
  holdings: Array<{ symbol: string; quantity: number; avg_cost: number; notes: string; added_date: string; name?: string }>;
  last_updated: string;
}

function loadPortfolio(): PortfolioData {
  if (!existsSync(portfolioPath)) return { holdings: [], last_updated: "" };
  return JSON.parse(readFileSync(portfolioPath, "utf-8")) as PortfolioData;
}

function savePortfolio(data: PortfolioData): void {
  mkdirSync(join(process.cwd(), ".pi-invest"), { recursive: true });
  writeFileSync(portfolioPath, JSON.stringify(data, null, 2), "utf-8");
}

export function manage_portfolio(
  action: string,
  symbol?: string,
  quantity?: number,
  avg_cost?: number,
  notes = "",
): string {
  try {
    const data = loadPortfolio();
    if (action === "get") return JSON.stringify(data);

    if (action === "add" && symbol) {
      const existing = data.holdings.find(h => h.symbol === symbol);
      if (existing) {
        if (quantity !== undefined) existing.quantity = quantity;
        if (avg_cost !== undefined) existing.avg_cost = avg_cost;
        existing.notes = notes;
      } else {
        data.holdings.push({ symbol, quantity: quantity ?? 0, avg_cost: avg_cost ?? 0, notes, added_date: today() });
      }
      data.last_updated = nowStr();
      savePortfolio(data);
      return JSON.stringify({ success: true, message: `已添加/更新 ${symbol}` });
    }

    if (action === "remove" && symbol) {
      data.holdings = data.holdings.filter(h => h.symbol !== symbol);
      data.last_updated = nowStr();
      savePortfolio(data);
      return JSON.stringify({ success: true, message: `已删除 ${symbol}` });
    }

    return JSON.stringify({ error: `未知操作: ${action}` });
  } catch (e) {
    return JSON.stringify({ error: String(e) });
  }
}

// ─── 走势深度分析 ──────────────────────────────────────────────────────────

/**
 * analyze_price_action — 股票走势深度量化分析
 *
 * 获取近260天日线（含约1年），计算：
 *   - 多周期趋势（5/20/60日）
 *   - KDJ / CCI / ATR
 *   - OBV量能趋势 + 量比
 *   - Swing高低点（关键支撑阻力位）
 *   - 52周高低点与距离
 *   - 近期连续涨跌天数 + 最大回撤
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

    const obvArr = calcObv(close, volume);
    const obvTrend = obvArr[n - 1] >= obvArr[Math.max(0, n - 5)] ? "上升" : "下降";
    const atrArr = calcAtr(high, low, close, 14);
    const atrLast = r2(atrArr[n - 1]);
    const { k, d, j } = calcKdj(high, low, close);
    const cciArr = calcCci(high, low, close, 20);

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
        rsi_14: r2(lastNum(calcRsi(close, 14))),
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

// ─── K线形态综合分析 ───────────────────────────────────────────────────────

/**
 * analyze_candlestick — K线形态识别 + 趋势线 + 斐波那契回调 + 缺口识别
 *
 * 获取 120 根日线，运行4项分析，返回结构化信号 JSON。
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

// ─── 同行业横向对比 ────────────────────────────────────────────────────────

export async function compare_peers(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    // 1. 获取目标股票基本信息（行业）
    const infoRaw = await get_stock_info(clean);
    const info = JSON.parse(infoRaw);
    if (info.error) return JSON.stringify({ error: info.error, symbol: clean });

    const sector: string = info.sector ?? info.industry ?? "";
    if (!sector) return JSON.stringify({ error: `无法获取 ${clean} 的行业信息`, symbol: clean });

    // 2. 获取同行业股票列表
    const sectorRaw = await get_sector_list();
    const sectorData = JSON.parse(sectorRaw);
    // sector_list 返回 { sectors: [...] } 或数组
    const sectors: Array<{ name: string; code?: string }> = Array.isArray(sectorData)
      ? sectorData
      : (sectorData.sectors ?? []);

    // 找匹配的板块名（模糊匹配）
    const matched = sectors.find(s => s.name && (s.name.includes(sector) || sector.includes(s.name)));
    const sectorName = matched?.name ?? sector;

    // 3. 并行：目标股票实时价
    const targetPriceRaw = await get_stock_realtime_price(clean);

    const targetPrice = JSON.parse(targetPriceRaw);

    // 4. 组装目标股信息
    const targetPE = safeFloat(info.pe ?? info.pe_dynamic ?? 0);
    const targetPB = safeFloat(info.pb ?? 0);
    const targetMktCap = safeFloat(info.market_cap_billion ?? info.total_market_cap ?? 0);
    const targetCurPrice = safeFloat(targetPrice.price ?? targetPrice.current_price ?? 0);
    const targetChangePct = safeFloat(targetPrice.change_pct ?? 0);

    return JSON.stringify({
      symbol: clean,
      name: info.name ?? clean,
      sector: sectorName,
      target: {
        symbol: clean,
        name: info.name ?? clean,
        current_price: targetCurPrice,
        change_pct: targetChangePct,
        pe: targetPE,
        pb: targetPB,
        market_cap_billion: targetMktCap,
        roe: safeFloat(info.roe ?? 0),
        gross_margin: safeFloat(info.gross_margin ?? 0),
      },
      peers_note: `同行业（${sectorName}）对比数据需调用 screen_stocks_quality("${sectorName}") 获取，` +
        `本工具已返回目标股基础数据，Agent 可并行调用 screen_stocks_quality 补充对比。`,
      usage_hint: `推荐工作流：1）已有目标股数据（见 target 字段）；2）调用 screen_stocks_quality(sector="${sectorName}") 拿同行 Top 10；3）对比 PE/ROE/毛利率/市值。`,
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

// ─── Function registry ─────────────────────────────────────────────────────

type TsFn = (args: Record<string, unknown>) => Promise<string> | string;

export const TS_FUNCTIONS: Record<string, TsFn> = {
  get_stock_realtime_price: (a) => get_stock_realtime_price(a.symbol as string),
  get_stock_history: (a) => get_stock_history(a.symbol as string, a.period as string | undefined, a.start_date as string | undefined, a.end_date as string | undefined, undefined, a._skip_cache as boolean | undefined),
  get_stock_info: (a) => get_stock_info(a.symbol as string),
  get_market_overview: () => get_market_overview(),
  get_sector_list: () => get_sector_list(),
  get_hk_stock_price: (a) => get_hk_stock_price(a.symbol as string),
  get_hk_stock_info: (a) => get_hk_stock_info(a.symbol as string),
  get_hk_stock_history: (a) => get_hk_stock_history(a.symbol as string, a.period as string | undefined),
  calculate_technical_indicators: (a) => calculate_technical_indicators(a.symbol as string),
  calculate_buy_range: (a) => calculate_buy_range(a.symbol as string, a.current_price as number | undefined),
  get_stock_valuation: (a) => get_stock_valuation(a.symbol as string),
  get_pe_percentile: (a) => get_pe_percentile(a.symbol as string, a.years as number | undefined),
  // get_quality_score: removed - use Python version directly
  get_stock_fund_flow: (a) => get_stock_fund_flow(a.symbol as string, a.days as number | undefined),
  get_holder_changes: (a) => get_holder_changes(a.symbol as string),
  get_exit_plan: (a) => get_exit_plan(a.symbol as string, a.buy_price as number, a.shares as number | undefined),
  analyze_price_action: (a) => analyze_price_action(a.symbol as string, a.period as number | undefined),
  analyze_candlestick: (a) => analyze_candlestick(a.symbol as string),
  compare_peers: (a) => compare_peers(a.symbol as string),
  manage_portfolio: (a) => manage_portfolio(
    a.action as string, a.symbol as string | undefined,
    a.quantity as number | undefined, a.avg_cost as number | undefined,
    a.notes as string | undefined,
  ),
};
