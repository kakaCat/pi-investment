/**
 * Investment Tools - A股投资工具集
 *
 * 通过 Python/akshare 桥接获取实时股票数据、财务指标、技术分析等。
 * 每个工具调用 callPython() 执行 python/akshare_bridge.py 中对应函数。
 */
import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { exec } from "child_process";
import { promisify } from "util";
import * as path from "path";
import { fileURLToPath } from "url";
import { TS_FUNCTIONS } from "../akshare-ts/index.js";
import { PortfolioService } from "../../services/portfolio/portfolio-service.js";
import { join } from "path";
import { readFileSync, existsSync } from "fs";
import { chinaDate } from "../../utils/china-time.js";
import { callPythonDaemon } from "./python-bridge.js";

const execAsync = promisify(exec);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pythonScript = path.resolve(__dirname, "..", "..", "..", "python", "akshare_bridge.py");

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
      // If no Python fallback exists, surface the TS error immediately
      if (!pythonScript) {
        return JSON.stringify({ error: `TS函数执行失败: ${tsErr}`, func });
      }
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

type Market = "ashare" | "hk" | "invalid";

/**
 * 检测股票代码所属市场。
 * - "ashare": 6位数字 A 股（可带 sh/sz/bj 前缀）
 * - "hk":     1-5位数字港股（可带 .HK 后缀）
 * - "invalid": 无法识别（美股、新加坡等不支持的市场）
 */
export function detectMarket(symbol: string): Market {
  const s = symbol.trim();
  // 明确的非支持市场
  if (/\.(US|SG|L|T)$/i.test(s)) return "invalid";
  // 港股：含 .HK 后缀，或纯1-5位数字
  if (/\.HK$/i.test(s)) return "hk";
  const noPrefix = s.replace(/^(sh|sz|bj)/i, "").trim();
  if (/^\d{6}$/.test(noPrefix)) return "ashare";
  if (/^\d{1,5}$/.test(s)) return "hk";
  return "invalid";
}

/**
 * 校验仅限A股的工具（财务报表、技术分析等数据源不支持港股）。
 * 返回 null 表示合法A股；返回错误 JSON 字符串表示不合法。
 */
export function requireAshare(symbol: string): string | null {
  const market = detectMarket(symbol);
  if (market === "ashare") return null;
  if (market === "hk") {
    return JSON.stringify({
      error: `本功能暂不支持港股代码 "${symbol}"。财务报表、技术分析、估值、选股等功能仅支持A股（6位数字）。港股可使用 get_stock_price / get_stock_info / get_stock_history 查询行情。`,
      unsupported_for_hk: true,
    });
  }
  return JSON.stringify({
    error: `不支持的股票代码 "${symbol}"。本系统支持A股（6位数字，如 600519）和港股（1-5位数字，如 9988 或 9988.HK）。`,
    invalid_format: true,
  });
}

// ===== 1. get_stock_info =====
export const getStockInfoTool: ToolDefinition = {
  name: "get_stock_info",
  label: "查询股票信息",
  description:
    "Get basic profile for a stock: name, sector/market, PE, PB, market cap, and (for A-shares) total shares, circulating shares, listing date. " +
    "Supports both A-shares (6-digit codes, e.g. 600519) and HK stocks (1-5 digit codes, e.g. 9988 or 9988.HK). " +
    "Use as the first step of any stock research to understand what the company does and its scale. " +
    "Returns {error} if the code is invalid or the stock is not found — do not proceed with analysis in that case. " +
    "Not for real-time price (use get_stock_price) or financial ratios (use get_financial_data).",
  parameters: Type.Object({
    symbol: Type.String({ description: "A-share 6-digit code (e.g. '600519') or HK stock 1-5 digit code (e.g. '9988' or '9988.HK'). US/other market codes are not supported." }),
  }),
  execute: async (_toolCallId, params: any) => {
    const market = detectMarket(params.symbol);
    if (market === "invalid") {
      return { content: [{ type: "text" as const, text: JSON.stringify({ error: `不支持的股票代码 "${params.symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`, invalid_format: true }) }], details: undefined };
    }
    const func = market === "hk" ? "get_hk_stock_info" : "get_stock_info";
    const result = await callPython(func, { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 2. get_stock_price =====
export const getStockPriceTool: ToolDefinition = {
  name: "get_stock_price",
  label: "查询实时股价",
  description:
    "Get real-time market snapshot for a stock: current price, change %, high/low, volume, turnover rate, PE, PB, and market cap. " +
    "Supports both A-shares (6-digit codes) and HK stocks (1-5 digit codes or with .HK suffix). " +
    "Always call this tool for current price — never substitute training data for live prices. " +
    "If this tool returns {error}, tell the user '无法获取实时价格，请稍后重试' and stop. " +
    "Not for historical prices (use get_stock_history) or financial ratios (use get_financial_data).",
  parameters: Type.Object({
    symbol: Type.String({ description: "A-share 6-digit code (e.g. '600519') or HK 1-5 digit code (e.g. '9988' or '9988.HK'). US/other market codes are not supported." }),
  }),
  execute: async (_toolCallId, params: any) => {
    const market = detectMarket(params.symbol);
    if (market === "invalid") {
      return { content: [{ type: "text" as const, text: JSON.stringify({ error: `不支持的股票代码 "${params.symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`, invalid_format: true }) }], details: undefined };
    }
    const func = market === "hk" ? "get_hk_stock_price" : "get_stock_realtime_price";
    const result = await callPython(func, { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 3. get_stock_history =====
export const getStockHistoryTool: ToolDefinition = {
  name: "get_stock_history",
  label: "查询历史行情",
  description:
    "Get historical OHLCV data (open, high, low, close, volume, change %) for a stock, up to 60 data points. " +
    "Default window is 90 days daily, forward-adjusted (前复权). Supports A-shares and HK stocks. " +
    "Use for trend analysis and technical context — not for current price (use get_stock_price instead). " +
    "Returns {error} if the stock has no trading data in the requested date range.",
  parameters: Type.Object({
    symbol: Type.String({ description: "A-share 6-digit code (e.g. '600519') or HK 1-5 digit code (e.g. '9988' or '9988.HK')" }),
    period: Type.Optional(Type.String({ description: "Aggregation period: 'daily', 'weekly', 'monthly' (default: 'daily')" })),
    start_date: Type.Optional(Type.String({ description: "Start date in YYYYMMDD format (default: 90 days ago)" })),
    end_date: Type.Optional(Type.String({ description: "End date in YYYYMMDD format (default: today)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const market = detectMarket(params.symbol);
    if (market === "invalid") {
      return { content: [{ type: "text" as const, text: JSON.stringify({ error: `不支持的股票代码 "${params.symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`, invalid_format: true }) }], details: undefined };
    }
    const func = market === "hk" ? "get_hk_stock_history" : "get_stock_history";
    const args: Record<string, unknown> = { symbol: params.symbol };
    if (params.period) args.period = params.period;
    if (params.start_date) args.start_date = params.start_date;
    if (params.end_date) args.end_date = params.end_date;
    const result = await callPython(func, args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 4. get_financial_data =====
export const getFinancialDataTool: ToolDefinition = {
  name: "get_financial_data",
  label: "查询财务指标",
  description:
    "Get key financial ratios for the last 4 quarters: ROE, gross margin, net margin, debt ratio, current ratio. " +
    "Use for quick profitability and solvency screening — ideal first filter before deep analysis. " +
    "For full line-item statements, use get_income_statement, get_balance_sheet, or get_cash_flow instead. " +
    "Returns {error} if the company has no published financial data.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("get_financial_indicators", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 5. screen_stocks =====
export const screenStocksTool: ToolDefinition = {
  name: "screen_stocks",
  label: "板块选股",
  description:
    "Screen stocks in an industry sector, sorted by market cap descending. Optionally filter by max PE. " +
    "Use to find investment candidates in a sector — follow up with get_financial_data on top results to verify fundamentals. " +
    "Prefer get_sector_list first if you are unsure of the exact sector name (names must match exactly, e.g. '白酒', '银行', '新能源车'). " +
    "Returns {error} if the sector name is not recognized.",
  parameters: Type.Object({
    sector: Type.String({ description: "Industry sector name in Chinese (must match exactly), e.g. '白酒', '银行', '新能源车'. Use get_sector_list to find valid names." }),
    min_roe: Type.Optional(Type.Number({ description: "Minimum ROE % filter, e.g. 15 (not yet active in backend)" })),
    max_pe: Type.Optional(Type.Number({ description: "Exclude stocks with PE above this value, e.g. 30. Leave empty to include all." })),
    limit: Type.Optional(Type.Integer({ description: "Max results to return (default 20)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const args: Record<string, unknown> = { sector: params.sector };
    if (params.min_roe !== undefined) args.min_roe = params.min_roe;
    if (params.max_pe !== undefined) args.max_pe = params.max_pe;
    if (params.limit !== undefined) args.limit = params.limit;
    const result = await callPython("screen_stocks_by_sector", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 6. get_sector_list =====
export const getSectorListTool: ToolDefinition = {
  name: "get_sector_list",
  label: "查询行业板块",
  description:
    "List all A-share industry sectors with stock count and today's change %. " +
    "Use before screen_stocks to verify the exact Chinese sector name. " +
    "Also useful for spotting which sectors are outperforming or underperforming the market today.",
  parameters: Type.Object({}),
  execute: async () => {
    const result = await callPython("get_sector_list");
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 7. get_stock_news =====
export const getStockNewsTool: ToolDefinition = {
  name: "get_stock_news",
  label: "查询个股新闻",
  description:
    "Get recent news headlines for a stock: title, publish date, and source. " +
    "Use to identify recent catalysts, policy changes, or sentiment before making a recommendation. " +
    "IMPORTANT: symbol is required — do NOT call this tool without a 6-digit code. " +
    "If you only have a stock name (e.g. '中国石油'), call get_stock_info first to resolve the symbol. " +
    "Returns {error} if no news is found. For most queries 5–10 items is sufficient (default 10).",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'. MUST be provided — resolve via get_stock_info if unknown." }),
    num: Type.Optional(Type.Integer({ description: "Number of news items to return (default 10)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const args: Record<string, unknown> = { symbol: params.symbol };
    if (params.num !== undefined) args.num = params.num;
    const result = await callPython("get_stock_news", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 7b. screen_stocks_quality =====
export const screenStocksQualityTool: ToolDefinition = {
  name: "screen_stocks_quality",
  label: "选股+质量评分",
  description:
    "Screen stocks by sector AND quality score in one call — more efficient than calling screen_stocks then get_quality_score separately. " +
    "Fetches up to 30 candidates from the sector, scores each on fundamentals (ROE/debt/margins), filters by min_score, and returns top results sorted by score. " +
    "Returns symbol, name, PE, price, score (0-100), grade, ROE, debt_ratio, gross_margin for each candidate. " +
    "Use this instead of screen_stocks for Path D (stock screening) — it saves multiple tool calls. " +
    "min_score default 50; set to 65 for stricter filtering (grade B+). " +
    "Returns {error} if sector data is unavailable.",
  parameters: Type.Object({
    sector: Type.String({ description: "Sector name, e.g. '白酒' or '新能源'" }),
    min_score: Type.Optional(Type.Integer({ description: "Minimum quality score to include (default 50, range 0-100)" })),
    max_pe: Type.Optional(Type.Number({ description: "Maximum PE ratio filter" })),
    limit: Type.Optional(Type.Integer({ description: "Max results to return (default 10)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const args: Record<string, unknown> = { sector: params.sector };
    if (params.min_score !== undefined) args.min_score = params.min_score;
    if (params.max_pe !== undefined) args.max_pe = params.max_pe;
    if (params.limit !== undefined) args.limit = params.limit;
    const result = await callPython("screen_stocks_quality", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 8. get_concept_stocks =====
export const getConceptStocksTool: ToolDefinition = {
  name: "get_concept_stocks",
  label: "查询概念板块成分股",
  description:
    "Get all stocks in a concept/theme: code, name, price, change %, and market cap. " +
    "Use for thematic investing when the user asks about a trend (e.g. AI, 芯片, 新能源车). " +
    "Concept name must be in Chinese and match exactly — if empty results, try a variant name. " +
    "Not for industry sectors (use get_sector_list + screen_stocks instead).",
  parameters: Type.Object({
    concept: Type.String({ description: "Concept/theme name in Chinese, e.g. '人工智能', '芯片概念', '新能源汽车'. Must match the exact concept name." }),
  }),
  execute: async (_toolCallId, params: any) => {
    const result = await callPython("get_concept_stocks", { concept: params.concept });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 9. analyze_technical =====
export const analyzeTechnicalTool: ToolDefinition = {
  name: "analyze_technical",
  label: "技术分析",
  description:
    "Run technical analysis on a stock: MA (5/10/20/60), MACD, RSI-14, Bollinger Bands, and auto-detected signals. " +
    "Returns actionable signals such as '短期多头排列', 'MACD金叉', 'RSI超买'. " +
    "Use for entry/exit timing alongside fundamentals — not as a standalone buy/sell signal. " +
    "Requires at least 30 days of history. Returns {error} if data is insufficient.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("calculate_technical_indicators", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 10. get_buy_range =====
export const getBuyRangeTool: ToolDefinition = {
  name: "get_buy_range",
  label: "计算买入区间",
  description:
    "Calculate optimal buy price range from four support levels: MA20, MA60, 20-day low, Bollinger lower band. " +
    "Returns safe_buy (lowest support), ideal_buy (avg of two lowest supports), stop_loss (safe_buy × 0.95), target_price (1:2 risk/reward), and a phased buying advice. " +
    "Advice distinguishes three cases: current price already in buy zone / approaching support / needs to wait for pullback. " +
    "Call after get_stock_price so you have current price context. " +
    "Returns {error} if fewer than 20 trading days of history are available.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    current_price: Type.Optional(Type.Number({ description: "Override current price in CNY (auto-fetched from history if omitted)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const args: Record<string, unknown> = { symbol: params.symbol };
    if (params.current_price !== undefined) args.current_price = params.current_price;
    const result = await callPython("calculate_buy_range", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 11. get_valuation =====
export const getValuationTool: ToolDefinition = {
  name: "get_valuation",
  label: "估值分析",
  description:
    "Analyze valuation using PE, PB, and Graham fair value (EPS × (8.5 + 2g), with g fixed at 10%). " +
    "Returns valuation_status ('cheap' PE<15 / 'fair' / 'expensive' PE>40), PE, PB, and fair_value_estimate. " +
    "Use to judge entry price relative to intrinsic value — interpret fair_value_estimate cautiously for cyclicals and high-growth stocks where 10% growth assumption may not apply. " +
    "Returns {error} if real-time data is unavailable.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("get_stock_valuation", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 11b. get_pe_percentile =====
export const getPePercentileTool: ToolDefinition = {
  name: "get_pe_percentile",
  label: "PE历史分位数",
  description:
    "Calculate where the current PE stands in its own N-year history (0% = historical low, 100% = historical high). " +
    "Returns current_pe, history_high_pe, history_low_pe, history_median_pe, and pe_percentile. " +
    "Prefer this over get_valuation for timing decisions — a stock with PE<15 but at 90th percentile is NOT cheap. " +
    "Use alongside get_valuation: get_valuation tells you absolute cheapness, get_pe_percentile tells you relative cheapness. " +
    "Returns {error} if fewer than 60 days of history are available or if the stock has negative earnings.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    years: Type.Optional(Type.Integer({ description: "Years of history to use for percentile calculation (default 3, max 5)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const args: Record<string, unknown> = { symbol: params.symbol };
    if (params.years !== undefined) args.years = params.years;
    const result = await callPython("get_pe_percentile", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 11c. get_quality_score =====
export const getQualityScoreTool: ToolDefinition = {
  name: "get_quality_score",
  label: "基本面质量评分",
  description:
    "Score a company's quality from 0 to 100 based on ROE, gross margin, debt ratio, operating cash flow, and revenue growth. " +
    "Returns total score, Chinese rating (优秀/良好/一般/较差), and per-dimension scores. " +
    "Use as a first filter before deep analysis — lower scores mean weaker profitability or cash quality. " +
    "Prefer calling this before get_valuation or get_pe_percentile to avoid wasting calls on low-quality companies. " +
    "Returns {error} if financial data is unavailable.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("get_quality_score", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 11d. get_exit_plan =====
export const getExitPlanTool: ToolDefinition = {
  name: "get_exit_plan",
  label: "止盈计划",
  description:
    "Calculate a three-tier profit-taking plan for a position based on fundamental fair value. " +
    "Returns three target prices: conservative (fair PE × 1.2, sell 30%), moderate (fair PE × 1.5, sell 40%), aggressive (fair PE × 2.0, sell 30%). " +
    "Also returns current P&L (pnl_pct, pnl_amount) and a sell_plan with actionable advice based on where current price stands relative to targets. " +
    "Use when the user asks 'should I sell', 'what's my target price', or 'how much profit have I made'. " +
    "Falls back to buy_price × 1.2/1.4/1.6 if PE data is unavailable. " +
    "Returns {error} if real-time price is unavailable.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    buy_price: Type.Number({ description: "Your average cost / buy price" }),
    shares: Type.Optional(Type.Integer({ description: "Number of shares held (default 100), used to calculate P&L amount" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const args: Record<string, unknown> = { symbol: params.symbol, buy_price: params.buy_price };
    if (params.shares !== undefined) args.shares = params.shares;
    const result = await callPython("get_exit_plan", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 12. get_macro_data =====
export const getMacroDataTool: ToolDefinition = {
  name: "get_macro_data",
  label: "查询宏观数据",
  description:
    "Get Chinese macro indicators. Pass indicators array to select specific data; omit to get all three. " +
    "Available indicators: 'pmi' (manufacturing PMI, >50=expansion, last 6 months), 'cpi' (YoY inflation, last 6 months), " +
    "'gdp' (quarterly growth rate, last 8 quarters). " +
    "Returns arrays of recent data points with dates. Data updated to 2025-09 (PMI/CPI) and 2025-07 (GDP). " +
    "Use for top-down analysis before stock picking, or when the user asks about macro environment.",
  parameters: Type.Object({
    indicators: Type.Optional(Type.Array(Type.String(), {
      description: "Subset to fetch, e.g. ['pmi','cpi']. Omit to fetch all three: pmi, cpi, gdp.",
    })),
  }),
  execute: async (_toolCallId, params: any) => {
    const args: Record<string, unknown> = {};
    if (params.indicators?.length) args.indicators = params.indicators;
    const result = await callPython("get_macro_data", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 13. get_north_flow =====
export const getNorthFlowTool: ToolDefinition = {
  name: "get_north_flow",
  label: "查询北向资金",
  description:
    "Get 10-day northbound capital (沪深港通) net inflow in billions CNY. Positive = buying; negative = selling. " +
    "Sustained inflows over 5+ days signal foreign institutional confidence — a strong bullish indicator. " +
    "Use alongside get_market_overview for a complete market sentiment picture. " +
    "Returns {error} if northbound flow data is unavailable.",
  parameters: Type.Object({}),
  execute: async () => {
    const result = await callPython("get_north_flow");
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 14. get_market_overview =====
export const getMarketOverviewTool: ToolDefinition = {
  name: "get_market_overview",
  label: "大盘概览",
  description:
    "Get a snapshot of 5 major A-share indices: SSE Composite (上证), SZSE Component (深证成指), " +
    "ChiNext (创业板), CSI 300 (沪深300), CSI 500 (中证500) — price and change % for each. " +
    "Call this first to gauge overall market direction before analyzing individual stocks. " +
    "Returns {error} if market data is unavailable (e.g. outside trading hours).",
  parameters: Type.Object({}),
  execute: async () => {
    const result = await callPython("get_market_overview");
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ── shared PortfolioService instance ──────────────────────────────────────
const _portfolioSvc = new PortfolioService(join(process.cwd(), ".pi-invest"));

// ===== 15. manage_portfolio =====
export const managePortfolioTool: ToolDefinition = {
  name: "manage_portfolio",
  label: "管理持仓",
  description:
    "Manage the user's local portfolio stored in .pi-invest/portfolio.json. " +
    "Actions:\n" +
    "  'get' — list raw holdings (symbol, quantity, avg_cost, notes)\n" +
    "  'get_with_pnl' — list holdings enriched with current price, today's change%, P&L amount and %\n" +
    "  'add' — record a NEW position or ADD SHARES to an existing one (weighted avg cost is auto-calculated)\n" +
    "  'update' — overwrite quantity/avg_cost directly (use to correct mistakes, not for adding shares)\n" +
    "  'remove' — delete a position entirely\n" +
    "When user says '记录持仓', '我持有', '加仓', '录入' → call 'add'. " +
    "When user asks to see holdings/P&L → call 'get_with_pnl'. " +
    "Portfolio data persists across sessions in .pi-invest/portfolio.json.",
  parameters: Type.Object({
    action: Type.Union(
      [Type.Literal("get"), Type.Literal("get_with_pnl"), Type.Literal("add"), Type.Literal("update"), Type.Literal("remove")],
      { description: "Operation to perform" },
    ),
    symbol: Type.Optional(Type.String({ description: "Stock code — 6-digit A-share (e.g. '600519') or HK code (e.g. '09988'). Required for add/update/remove." })),
    quantity: Type.Optional(Type.Integer({ description: "Number of shares (for add/update)" })),
    avg_cost: Type.Optional(Type.Number({ description: "Average cost per share in CNY/HKD (for add/update)" })),
    name: Type.Optional(Type.String({ description: "Stock name (optional, will be auto-filled from market data if omitted)" })),
    market: Type.Optional(Type.Union([Type.Literal("A"), Type.Literal("HK")], { description: "Market: 'A' for A-share (default), 'HK' for Hong Kong" })),
    notes: Type.Optional(Type.String({ description: "Free-text notes, e.g. '分批建仓第1批' or '看好AI算力'" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const { action, symbol, quantity, avg_cost, name, market, notes } = params;
    try {
      if (action === "get") {
        const data = _portfolioSvc.load();
        return { content: [{ type: "text" as const, text: JSON.stringify(data) }], details: undefined };
      }
      if (action === "get_with_pnl") {
        const snapshot = await _portfolioSvc.getWithPnL();
        return { content: [{ type: "text" as const, text: JSON.stringify(snapshot) }], details: undefined };
      }
      if (action === "add") {
        if (!symbol || quantity == null || avg_cost == null) {
          return { content: [{ type: "text" as const, text: JSON.stringify({ error: "add 需要 symbol, quantity, avg_cost", _no_operation_performed: true }) }], details: undefined };
        }
        const res = _portfolioSvc.add(symbol, quantity, avg_cost, name ?? "", market ?? "A", notes ?? "");
        return { content: [{ type: "text" as const, text: JSON.stringify(res) }], details: undefined };
      }
      if (action === "update") {
        if (!symbol) {
          return { content: [{ type: "text" as const, text: JSON.stringify({ error: "update 需要 symbol", _no_operation_performed: true }) }], details: undefined };
        }
        const res = _portfolioSvc.update(symbol, quantity, avg_cost, name, notes);
        return { content: [{ type: "text" as const, text: JSON.stringify(res) }], details: undefined };
      }
      if (action === "remove") {
        if (!symbol) {
          return { content: [{ type: "text" as const, text: JSON.stringify({ error: "remove 需要 symbol", _no_operation_performed: true }) }], details: undefined };
        }
        const res = _portfolioSvc.remove(symbol);
        return { content: [{ type: "text" as const, text: JSON.stringify(res) }], details: undefined };
      }
      return { content: [{ type: "text" as const, text: JSON.stringify({ error: `未知操作: ${action}`, valid_actions: ["get", "get_with_pnl", "add", "update", "remove"], _no_operation_performed: true }) }], details: undefined };
    } catch (e) {
      return { content: [{ type: "text" as const, text: JSON.stringify({ error: String(e), _no_operation_performed: true }) }], details: undefined };
    }
  },
};

// ===== 15b. get_review =====
export const getReviewTool: ToolDefinition = {
  name: "get_review",
  label: "查看复盘",
  description:
    "Read stored daily review reports from .pi-invest/reviews/. " +
    "Actions: 'today' — show today's review if exists; 'list' — list recent review dates; 'read' — read a specific date's review. " +
    "Use this when user says '查看复盘', '今天复盘', '看复盘报告', or before running a new review to check if it was already done.",
  parameters: Type.Object({
    action: Type.Union(
      [Type.Literal("today"), Type.Literal("list"), Type.Literal("read")],
      { description: "'today' — today's review; 'list' — last 7 reviews; 'read' — specific date" },
    ),
    date: Type.Optional(Type.String({ description: "Date in YYYY-MM-DD format (for 'read' action)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const reviewsDir = join(process.cwd(), ".pi-invest", "reviews");
    const { action, date } = params;
    try {
      if (action === "today" || action === "read") {
        const d = date ?? chinaDate();
        const f = join(reviewsDir, `${d}.md`);
        if (!existsSync(f)) {
          return { content: [{ type: "text" as const, text: JSON.stringify({ found: false, date: d, message: `${d} 暂无复盘记录` }) }], details: undefined };
        }
        const content = readFileSync(f, "utf-8");
        return { content: [{ type: "text" as const, text: content }], details: undefined };
      }
      if (action === "list") {
        const { readdirSync, statSync } = await import("fs");
        if (!existsSync(reviewsDir)) {
          return { content: [{ type: "text" as const, text: JSON.stringify({ count: 0, reviews: [], message: `复盘目录不存在: ${reviewsDir}，尚未生成过复盘报告` }) }], details: undefined };
        }
        const files = readdirSync(reviewsDir).filter(f => f.endsWith(".md")).sort().reverse().slice(0, 7);
        const list = files.map(f => ({ date: f.replace(".md", ""), size: statSync(join(reviewsDir, f)).size }));
        return { content: [{ type: "text" as const, text: JSON.stringify({ count: list.length, reviews: list }) }], details: undefined };
      }
      return { content: [{ type: "text" as const, text: JSON.stringify({ error: `未知操作: ${action}`, valid_actions: ["today", "list", "read"], _no_operation_performed: true }) }], details: undefined };
    } catch (e) {
      return { content: [{ type: "text" as const, text: JSON.stringify({ error: String(e), _no_operation_performed: true }) }], details: undefined };
    }
  },
};

// ===== 16. get_financial_statements =====
export const getFinancialStatementsTool: ToolDefinition = {
  name: "get_financial_statements",
  label: "财务报表",
  description:
    "Get detailed financial statements for an A-share company. Use statement parameter to select which table(s) to fetch. " +
    "'income' — P&L: revenue, gross profit, operating profit, net income, EPS. " +
    "'balance' — Balance sheet: total assets, cash, inventory, total liabilities, shareholders equity. " +
    "'cashflow' — Cash flow: operating CF, investing CF, financing CF, free cash flow (operating CF − capex). " +
    "'all' (default) — all three tables in one call. " +
    "Prefer 'all' for deep analysis; prefer a single statement when you only need one dimension (e.g. 'cashflow' to check earnings quality). " +
    "Free cash flow is the truest measure of cash generation — strong net income with negative operating CF is a key red flag. " +
    "Returns {error} if financial reports are not available for this stock.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    statement: Type.Optional(Type.String({ description: "'income', 'balance', 'cashflow', or 'all' (default)" })),
    recent_n: Type.Optional(Type.Integer({ description: "Number of recent quarterly periods to return (default 8)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const args: Record<string, unknown> = { symbol: params.symbol, statement: params.statement ?? "all" };
    if (params.recent_n !== undefined) args.recent_n = params.recent_n;
    const result = await callPython("get_financial_statements", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 19. get_insider_trades =====
export const getInsiderTradesTool: ToolDefinition = {
  name: "get_insider_trades",
  label: "高管增减持",
  description:
    "Get recent insider trading records: person name, title, transaction date, shares changed, average price, and transaction value. " +
    "Large buying by CEO/Chairman is a strong bullish signal; steady selling by multiple insiders over months warrants caution. " +
    "Use as a supplementary signal — not a standalone buy/sell indicator. " +
    "Returns {error} if no insider trading data is found for this stock.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("get_insider_trades", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 20. get_lhb =====
export const getLhbTool: ToolDefinition = {
  name: "get_lhb",
  label: "龙虎榜",
  description:
    "Dragon-Tiger List (龙虎榜) data with two modes depending on whether symbol is provided. " +
    "Without symbol: returns today's榜单 (top 30 entries) — stocks that hit circuit breakers or had unusual volume, " +
    "with net buy/sell amounts. Use to spot what hot money is chasing today. " +
    "With symbol: returns that stock's appearance statistics over a period — count, cumulative net buy, seat breakdown (institutional vs retail). " +
    "Institutional seats buying = strong signal; multiple retail seats selling = distribution warning. " +
    "Returns {error} if no data is available for the requested date or symbol.",
  parameters: Type.Object({
    symbol: Type.Optional(Type.String({ description: "6-digit A-share code. Omit to get today's full榜单; provide to get per-stock statistics." })),
    date: Type.Optional(Type.String({ description: "Date in YYYYMMDD format for榜单 mode (default: yesterday). Ignored when symbol is provided." })),
    period: Type.Optional(Type.String({ description: "Statistics period for per-stock mode: 近一月 (default) / 近三月 / 近六月 / 近一年." })),
  }),
  execute: async (_toolCallId, params: any) => {
    const args: Record<string, unknown> = {};
    if (params.symbol) {
      const err = requireAshare(params.symbol);
      if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
      args.symbol = params.symbol;
    }
    if (params.date) args.date = params.date;
    if (params.period) args.period = params.period;
    const result = await callPython("get_lhb", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 22. get_fund_holdings =====
export const getFundHoldingsTool: ToolDefinition = {
  name: "get_fund_holdings",
  label: "基金持仓",
  description:
    "Get list of funds holding a specific stock, with shares held and % of float. " +
    "High institutional ownership from quality funds = validation of long-term value. " +
    "Sudden drop in fund count across quarters = smart money exiting — red flag.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("get_fund_holdings", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 23. get_top_fund_stocks =====
export const getTopFundStocksTool: ToolDefinition = {
  name: "get_top_fund_stocks",
  label: "基金重仓股排行",
  description:
    "Get ranking of stocks most widely held by funds — the 'smart money' consensus picks. " +
    "Use for stock discovery: stocks appearing here have passed institutional due diligence. " +
    "Combine with valuation tools to find quality stocks at reasonable prices.",
  parameters: Type.Object({}),
  execute: async () => {
    const result = await callPython("get_top_fund_stocks");
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 24. get_top_holders =====
export const getTopHoldersTool: ToolDefinition = {
  name: "get_top_holders",
  label: "前十大股东",
  description:
    "Get top 10 shareholders: name, shares held, ownership %, and change vs prior period. " +
    "State-owned or institutional majority = stable; concentrated retail ownership = higher volatility risk. " +
    "Increasing holdings by major shareholders = bullish; decreasing = caution.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("get_top_holders", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 25. get_holder_changes =====
export const getHolderChangesTool: ToolDefinition = {
  name: "get_holder_changes",
  label: "十大股东变化",
  description:
    "Compare top 10 shareholders across the most recent 2 available quarters. " +
    "Returns new holders, reduced holders, increased holders, exited holders, and holding-ratio changes. " +
    "Useful for spotting whether key shareholders are adding, reducing, or rotating out.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("get_holder_changes", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 26. get_margin_data =====
export const getMarginDataTool: ToolDefinition = {
  name: "get_margin_data",
  label: "融资融券",
  description:
    "Get margin trading data for a stock: margin balance (融资余额), short balance (融券余额), " +
    "margin buy amount, and short sell volume over last 10 days. " +
    "Rising margin balance = leveraged bulls increasing — momentum signal but also risk amplifier.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("get_margin_data", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 27. get_market_margin =====
export const getMarketMarginTool: ToolDefinition = {
  name: "get_market_margin",
  label: "全市场融资融券",
  description:
    "Get overall market margin balance trend (last 10 days). " +
    "Total margin > 1.8T CNY = market leverage high = correction risk elevated. " +
    "Use alongside get_market_overview for macro risk assessment.",
  parameters: Type.Object({}),
  execute: async () => {
    const result = await callPython("get_market_margin");
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 31. get_announcements =====
export const getAnnouncementsTool: ToolDefinition = {
  name: "get_announcements",
  label: "个股公告",
  description:
    "Get recent company announcements (last 20): title, date, and type (earnings, dividend, restructuring, etc.). " +
    "Always check announcements before making buy/sell decisions — material events move prices significantly. " +
    "Earnings warnings, major shareholder reductions, and regulatory investigations are key risk flags.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("get_announcements", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_market_news =====
export const getMarketNewsTool: ToolDefinition = {
  name: "get_market_news",
  label: "财经市场新闻",
  description:
    "Get comprehensive market news from multiple sources: Caixin (财新, in-depth financial analysis) and CCTV News (新闻联播, policy/macro signals). " +
    "Use to understand current macro environment, policy direction, and major financial events. " +
    "Best used at the start of a session or when asked about market trends. " +
    "Returns caixin (财经深度) and cctv (政策宏观) sections with title, content summary.",
  parameters: Type.Object({
    num: Type.Optional(Type.Integer({ description: "Number of items per source (default 20)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const args: Record<string, unknown> = {};
    if (params?.num !== undefined) args.num = params.num;
    const result = await callPython("get_market_news", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_hot_stocks =====
export const getHotStocksTool: ToolDefinition = {
  name: "get_hot_stocks",
  label: "热搜股票",
  description:
    "Get today's hot search stock ranking from Baidu (百度股市通). " +
    "Shows which stocks retail investors are most actively searching — useful for gauging market sentiment and identifying trending topics. " +
    "market: 'A股' (default), '港股', '美股', or '全部'.",
  parameters: Type.Object({
    market: Type.Optional(Type.String({ description: "Market filter: 'A股' (default), '港股', '美股', '全部'" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const args: Record<string, unknown> = { market: params?.market ?? "A股" };
    const result = await callPython("get_hot_stocks", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 32. get_sector_fund_flow =====
export const getSectorFundFlowTool: ToolDefinition = {
  name: "get_sector_fund_flow",
  label: "行业资金流向",
  description:
    "Get today's sector fund flow ranking: which industries are seeing net inflows vs outflows. " +
    "Top inflow sectors = market rotation target = consider stocks in those sectors. " +
    "Use before stock screening to identify which sectors have momentum.",
  parameters: Type.Object({}),
  execute: async () => {
    const result = await callPython("get_sector_fund_flow");
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== 33. get_stock_fund_flow =====
export const getStockFundFlowTool: ToolDefinition = {
  name: "get_stock_fund_flow",
  label: "个股资金流向",
  description:
    "Analyze stock fund flow over the recent N days. " +
    "Returns main-force / large-order / medium-order / small-order net inflows and ratios. " +
    "Useful for checking whether recent trading is dominated by institutional buying or retail flow.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code" }),
    days: Type.Optional(Type.Integer({ description: "Number of recent trading days to aggregate (default 5)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const args: Record<string, unknown> = { symbol: params.symbol };
    if (params.days !== undefined) args.days = params.days;
    const result = await callPython("get_stock_fund_flow", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== analyze_candlestick =====
export const analyzeCandlestickTool: ToolDefinition = {
  name: "analyze_candlestick",
  label: "K线形态分析",
  description:
    "K线形态综合分析：识别蜡烛图形态（锤子线、吞没、十字星、启明星等）、趋势线支撑/阻力、斐波那契回调位（23.6%~78.6%）、跳空缺口（是否回补）。 " +
    "返回 patterns（形态列表）、trend_lines（趋势线）、fibonacci（回调位）、gaps（缺口）、summary（中文摘要）。 " +
    "当用户问K线形态、蜡烛图信号、趋势线突破、斐波那契支撑位、跳空缺口时调用此工具。 " +
    "仅支持A股（6位数字代码）。需要至少30天历史数据。",
  parameters: Type.Object({
    symbol: Type.String({ description: "6位A股代码，如 '600519'" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("analyze_candlestick", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== analyze_price_action =====
export const analyzePriceActionTool: ToolDefinition = {
  name: "analyze_price_action",
  label: "走势深度分析",
  description:
    "Deep technical analysis of recent price action. " +
    "Returns trend (上升/下降/震荡), support levels, resistance levels, volume changes, and breakout signal. " +
    "Use this tool when analyzing entry timing, trend strength, or price structure. " +
    "Only supports A-share (6-digit codes). Requires at least 60 days of history.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    period: Type.Optional(Type.Integer({ description: "Lookback window in trading days (default 60)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const args: Record<string, unknown> = { symbol: params.symbol };
    if (params.period !== undefined) args.period = params.period;
    const result = await callPython("analyze_price_action", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== HK: get_hk_financials =====
export const getHkFinancialsTool: ToolDefinition = {
  name: "get_hk_financials",
  label: "港股财务数据",
  description:
    "Get HK stock financial data: income statement (revenue, net profit, net margin) and balance sheet (assets, liabilities, debt ratio) for last 4 annual periods. " +
    "Use for HK stocks when get_financial_data is unavailable (A-share only). " +
    "Returns {error} if the stock has no published data on akshare. " +
    "Only supports HK stock codes (1-5 digit or .HK suffix).",
  parameters: Type.Object({
    symbol: Type.String({ description: "HK stock code, e.g. '9988' or '9988.HK'" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const market = detectMarket(params.symbol);
    if (market !== "hk") {
      return { content: [{ type: "text" as const, text: JSON.stringify({ error: "get_hk_financials 仅支持港股代码（1-5位数字或含.HK后缀）" }) }], details: undefined };
    }
    const result = await callPython("get_hk_financials", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== HK: get_hk_analysis =====
export const getHkAnalysisTool: ToolDefinition = {
  name: "get_hk_analysis",
  label: "港股综合分析",
  description:
    "Comprehensive analysis for HK stocks: real-time price, 20/60-day MA trend, recent high/low, and financial data (if available). " +
    "Use this as the primary deep-analysis tool for HK stocks — it replaces the A-share Path C workflow. " +
    "Clearly lists which data is NOT available for HK (PE percentile, LHB, north flow, margin). " +
    "IMPORTANT: If this tool returns data, use ONLY that data in your analysis — do not supplement with training knowledge. " +
    "Returns {error} if real-time price cannot be fetched.",
  parameters: Type.Object({
    symbol: Type.String({ description: "HK stock code, e.g. '9988' or '9988.HK'" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const market = detectMarket(params.symbol);
    if (market !== "hk") {
      return { content: [{ type: "text" as const, text: JSON.stringify({ error: "get_hk_analysis 仅支持港股代码（1-5位数字或含.HK后缀）" }) }], details: undefined };
    }
    const result = await callPython("get_hk_analysis", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== compare_peers =====
export const comparePeersTool: ToolDefinition = {
  name: "compare_peers",
  label: "同行业横向对比",
  description:
    "Compare a stock against its sector peers. Returns the target stock's key metrics (PE, PB, ROE, gross margin, market cap) " +
    "and the sector name to use with screen_stocks_quality for peer comparison. " +
    "Use when the user asks 'how does XX compare to its peers', 'is XX cheap relative to sector', or 'which stock in XX sector is best'. " +
    "Recommended workflow: 1) call compare_peers(symbol) → get target metrics + sector name; " +
    "2) call screen_stocks_quality(sector) in parallel → get peer list with scores; " +
    "3) combine into a comparison table (PE/ROE/gross margin/market cap/quality score). " +
    "Only supports A-share (6-digit codes).",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("compare_peers", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== Export all investment tools =====
export const investTools: ToolDefinition[] = [
  // Market overview — start here
  getMarketOverviewTool,
  // Individual stock research
  getStockInfoTool,
  getStockPriceTool,
  getStockHistoryTool,
  getFinancialDataTool,
  getStockNewsTool,
  // HK-specific analysis
  getHkAnalysisTool,
  getHkFinancialsTool,
  // Analysis
  analyzeTechnicalTool,
  analyzePriceActionTool,
  analyzeCandlestickTool,
  getValuationTool,
  getPePercentileTool,
  getQualityScoreTool,
  getBuyRangeTool,
  getExitPlanTool,
  // Screening & discovery
  getSectorListTool,
  screenStocksTool,
  screenStocksQualityTool,
  getConceptStocksTool,
  comparePeersTool,
  // Macro & sentiment
  getMacroDataTool,
  getNorthFlowTool,
  // Market sentiment & flow
  getSectorFundFlowTool,
  getMarketMarginTool,
  // Individual stock — smart money signals
  getStockFundFlowTool,
  getLhbTool,
  getFundHoldingsTool,
  getTopHoldersTool,
  getHolderChangesTool,
  getMarginDataTool,
  getInsiderTradesTool,
  // Institutional consensus
  getTopFundStocksTool,
  // Corporate events
  getAnnouncementsTool,
  // News & sentiment
  getMarketNewsTool,
  getHotStocksTool,
  // Portfolio & reviews
  managePortfolioTool,
  getReviewTool,
  // Financial statements
  getFinancialStatementsTool,
];

/**
 * 统一的工具调用接口（供 Worker 使用）
 */
export async function callInvestTool(toolName: string, params: any): Promise<string> {
  const tool = investTools.find(t => t.name === toolName);
  if (!tool) {
    throw new Error(`Unknown tool: ${toolName}`);
  }

  // 直接调用 execute，类型断言避免类型检查问题
  const result = await (tool.execute as any)("worker-call", params);

  // 提取文本内容
  if (result.content && Array.isArray(result.content)) {
    const textBlock = result.content.find((c: any) => c.type === "text");
    if (textBlock && "text" in textBlock) {
      return textBlock.text;
    }
  }

  return JSON.stringify(result);
}
