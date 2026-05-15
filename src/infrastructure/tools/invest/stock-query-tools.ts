/**
 * Stock Query Tools - 股票信息、价格、历史行情
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { callPython } from "../shared/python-caller.js";
import { detectMarket } from "../shared/validators.js";

// ===== get_stock_info =====
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

// ===== get_stock_price =====
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

// ===== get_stock_history =====
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

// ===== get_stock_news =====
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
    const args: Record<string, unknown> = { symbol: params.symbol };
    if (params.num !== undefined) args.num = params.num;
    const result = await callPython("get_stock_news", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_announcements =====
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
    const result = await callPython("get_announcements", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

export const stockQueryTools: ToolDefinition[] = [
  getStockInfoTool,
  getStockPriceTool,
  getStockHistoryTool,
  getStockNewsTool,
  getAnnouncementsTool,
];
