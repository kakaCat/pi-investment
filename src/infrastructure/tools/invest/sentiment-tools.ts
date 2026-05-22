/**
 * Sentiment Tools - 资金流向、龙虎榜、持股分析
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { requireAshare } from "../shared/validators.js";
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

// ===== get_stock_fund_flow =====
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
    const result = await callQuantSysDaemon("get_stock_fund_flow", args as any);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_lhb =====
export const getLhbTool: ToolDefinition = {
  name: "get_lhb",
  label: "龙虎榜",
  description:
    "Dragon-Tiger List (龙虎榜) data with two modes depending on whether symbol is provided. " +
    "Without symbol: returns today's榜单 (top 30 entries) — stocks that hit circuit breakers or had unusual volume, " +
    "with net buy/sell amounts. Use to spot what hot money is chasing today. " +
    "With symbol: returns that stock's appearance statistics over a period — count, cumulative net buy, seat breakdown (institutional vs retail). " +
    "Institutional seats buying = strong signal; multiple retail seats selling = distribution warning. " +
    "Returns {error} if no data is available for the requested date or symbol. " +
    "\n\n⚠️ TIMEOUT FALLBACK: If this tool times out (>120s), use WebFetch instead:\n" +
    "- URL: https://data.eastmoney.com/stock/lhb.html (东方财富龙虎榜)\n" +
    "- Prompt: 'Extract today's Dragon-Tiger List data: top 20 stocks with code, name, close price, change %, net buy amount, and listing reason'\n" +
    "- Alternative: http://data.10jqka.com.cn/market/longhu/ (同花顺龙虎榜)",
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
    const result = await callQuantSysDaemon("get_lhb", args);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_insider_trades =====
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
    const result = await callQuantSysDaemon("get_insider_trades", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_fund_holdings =====
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
    const result = await callQuantSysDaemon("get_fund_holdings", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_top_fund_stocks =====
export const getTopFundStocksTool: ToolDefinition = {
  name: "get_top_fund_stocks",
  label: "基金重仓股排行",
  description:
    "Get ranking of stocks most widely held by funds — the 'smart money' consensus picks. " +
    "Use for stock discovery: stocks appearing here have passed institutional due diligence. " +
    "Combine with valuation tools to find quality stocks at reasonable prices.",
  parameters: Type.Object({}),
  execute: async () => {
    const result = await callQuantSysDaemon("get_top_fund_stocks");
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_top_holders =====
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
    const result = await callQuantSysDaemon("get_top_holders", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_holder_changes =====
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
    const result = await callQuantSysDaemon("get_holder_changes", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_margin_data =====
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
    const result = await callQuantSysDaemon("get_margin_data", { symbol: params.symbol });
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

export const sentimentTools: ToolDefinition[] = [
  getStockFundFlowTool,
  getLhbTool,
  getInsiderTradesTool,
  getFundHoldingsTool,
  getTopFundStocksTool,
  getTopHoldersTool,
  getHolderChangesTool,
  getMarginDataTool,
];
