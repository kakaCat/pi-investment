/**
 * Market Overview Tools - 市场概览、板块、宏观数据
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { callPython } from "../shared/python-caller.js";

// ===== get_market_overview =====
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

// ===== get_sector_list =====
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

// ===== get_concept_stocks =====
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

// ===== get_macro_data =====
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

// ===== get_north_flow =====
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

// ===== get_sector_fund_flow =====
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

// ===== get_market_margin =====
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

export const marketTools: ToolDefinition[] = [
  getMarketOverviewTool,
  getSectorListTool,
  getConceptStocksTool,
  getMacroDataTool,
  getNorthFlowTool,
  getSectorFundFlowTool,
  getMarketMarginTool,
  getMarketNewsTool,
  getHotStocksTool,
];
