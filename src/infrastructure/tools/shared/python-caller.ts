/**
 * Python bridge with TypeScript fallback and caching
 */
import { TS_FUNCTIONS } from "../../akshare-ts/index.js";
import { callPythonDaemon } from "../python-bridge.js";

// ===== 分级缓存 =====
const TTL_REALTIME = 5 * 60 * 1000;    // 实时价格：5分钟
const TTL_TECHNICAL = 10 * 60 * 1000;  // 技术/资金流：10分钟
const TTL_DAILY = 24 * 60 * 60 * 1000; // 财务/基本面：1天

const TTL: Record<string, number> = {
  // 实时行情
  get_stock_realtime_price: TTL_REALTIME,
  get_hk_stock_price: TTL_REALTIME,
  get_market_overview: TTL_REALTIME,
  get_stock_news: TTL_REALTIME,
  // 技术分析与资金流
  get_north_flow: TTL_TECHNICAL,
  get_sector_fund_flow: TTL_TECHNICAL,
  get_stock_fund_flow: TTL_TECHNICAL,
  get_market_margin: TTL_TECHNICAL,
  calculate_technical_indicators: TTL_TECHNICAL,
  calculate_buy_range: TTL_TECHNICAL,
  analyze_candlestick: TTL_TECHNICAL,
  get_lhb: 30 * 60 * 1000,
  get_announcements: 30 * 60 * 1000,
  // 财务与基本面
  get_stock_info: TTL_DAILY,
  get_hk_stock_info: TTL_DAILY,
  get_financial_indicators: TTL_DAILY,
  get_stock_valuation: TTL_DAILY,
  get_pe_percentile: TTL_DAILY,
  get_financial_statements: TTL_DAILY,
  get_insider_trades: TTL_DAILY,
  get_fund_holdings: TTL_DAILY,
  get_top_holders: TTL_DAILY,
  get_holder_changes: TTL_DAILY,
  get_margin_data: TTL_DAILY,
  get_top_fund_stocks: TTL_DAILY,
  get_macro_data: TTL_DAILY,
  get_sector_list: TTL_DAILY,
  get_concept_stocks: TTL_DAILY,
  screen_stocks_by_sector: TTL_DAILY,
  get_lhb_stock_stat: TTL_DAILY,
};
const DEFAULT_TTL = TTL_TECHNICAL;

interface CacheEntry { data: string; expiry: number; }
const cache = new Map<string, CacheEntry>();

export async function callPython(func: string, args: Record<string, unknown> = {}): Promise<string> {
  const cacheKey = `${func}:${JSON.stringify(args, Object.keys(args).sort())}`;
  const cached = cache.get(cacheKey);
  if (cached && cached.expiry > Date.now()) {
    return cached.data;
  }

  // ── TypeScript-native path (no Python subprocess) ──
  const tsFn = TS_FUNCTIONS[func];
  if (tsFn) {
    try {
      const result = await tsFn(args);
      const ttl = TTL[func] ?? DEFAULT_TTL;
      cache.set(cacheKey, { data: result, expiry: Date.now() + ttl });
      return result;
    } catch (e) {
      // Fall through to Python on TS failure
      const tsErr = e instanceof Error ? e.message : String(e);
      console.warn(`[akshare-ts] ${func} failed (${tsErr}), retrying via Python…`);
      // Mark that we fell back so downstream code (and agent) can be aware
      ;(args as any).__ts_fallback = tsErr;
    }
  }

  // ── Python fallback ────────────────────────────────
  const tsFallbackErr = (args as any).__ts_fallback as string | undefined;
  if (tsFallbackErr) {
    // Remove the internal marker before passing to Python
    const { __ts_fallback: _, ...cleanArgs } = args as any;
    args = cleanArgs;
  }
  try {
    const result = await callPythonDaemon(func, args);
    // Annotate Python result with fallback info so agent is aware
    let finalResult = result;
    if (tsFallbackErr) {
      try {
        const parsed = JSON.parse(result);
        finalResult = JSON.stringify({ ...parsed, _via_python_fallback: true });
      } catch {
        // result is not JSON (e.g. plain text), leave as-is
      }
    }
    const ttl = TTL[func] ?? DEFAULT_TTL;
    cache.set(cacheKey, { data: finalResult, expiry: Date.now() + ttl });
    return finalResult;
  } catch (error: unknown) {
    if (error instanceof Error) {
      const msg = error.message;
      return JSON.stringify({ error: `Python调用失败: ${msg}`, ts_error: tsFallbackErr || undefined, _no_operation_performed: true });
    }
    return JSON.stringify({ error: "Python调用失败（未知错误）", ts_error: tsFallbackErr || undefined, _no_operation_performed: true });
  }
}
