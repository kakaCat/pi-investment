/**
 * HK Stock Tools — 港股专用工具
 *
 * 新增工具通过 quant CLI 后端链路提供数据
 * 注册方式：在 invest-tools.ts 的 investTools 数组中加入 hkTools
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import {
  getHkHotRankViaQuantCli,
  getHkMarketOverviewViaQuantCli,
  getHkSouthFlowViaQuantCli,
  getHkTechnicalViaQuantCli,
} from "../../quant/hk-query-cli-adapter.js";

// ===== get_hk_market_overview =====
export const getHkMarketOverviewTool: ToolDefinition = {
  name: "get_hk_market_overview",
  label: "港股大盘概览",
  description:
    "Get real-time quotes for 3 major HK indices: Hang Seng Index (恒生指数), " +
    "HSCEI (国企指数/恒生中国企业指数), and Hang Seng Tech Index (恒生科技指数) — " +
    "current price, change, and change % for each. " +
    "Call this first to gauge HK market direction before analyzing individual HK stocks. " +
    "Data source: Sina Finance (same upstream as A-share market overview). " +
    "Returns {error} if market data is unavailable (e.g. outside trading hours).",
  parameters: Type.Object({}),
  execute: async () => {
    const result = await getHkMarketOverviewViaQuantCli();
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_hk_south_flow =====
export const getHkSouthFlowTool: ToolDefinition = {
  name: "get_hk_south_flow",
  label: "南向资金（港股通）",
  description:
    "Get 10-day southbound capital (港股通/南向资金) net inflow in billions CNY. " +
    "Positive = mainland capital buying HK stocks; negative = mainland capital selling HK stocks. " +
    "Sustained southbound inflows over 5+ days signal mainland institutional confidence in HK market. " +
    "This is the HK-side equivalent of get_north_flow (northbound/北向资金). " +
    "Use alongside get_hk_market_overview for a complete HK market sentiment picture. " +
    "Returns {error} if southbound flow data is unavailable.",
  parameters: Type.Object({}),
  execute: async () => {
    const result = await getHkSouthFlowViaQuantCli();
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_hk_technical =====
export const getHkTechnicalTool: ToolDefinition = {
  name: "get_hk_technical",
  label: "港股技术分析",
  description:
    "Run technical analysis on a HK stock: MA (5/10/20/60), MACD, RSI-14, Bollinger Bands, " +
    "and auto-detected signals. " +
    "Returns actionable signals such as '多头排列', 'MACD金叉', 'RSI超买'. " +
    "Use for entry/exit timing alongside fundamentals — not as a standalone buy/sell signal. " +
    "Requires at least 30 days of history. " +
    "Only supports HK stock codes (1-5 digit or .HK suffix). " +
    "Returns {error} if data is insufficient.",
  parameters: Type.Object({
    symbol: Type.String({ description: "HK stock code, e.g. '9988' or '9988.HK' or '00700'" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const result = await getHkTechnicalViaQuantCli(params.symbol);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== get_hk_hot_rank =====
export const getHkHotRankTool: ToolDefinition = {
  name: "get_hk_hot_rank",
  label: "港股人气排行",
  description:
    "Get today's HK stock popularity ranking from East Money (东方财富港股人气榜). " +
    "Shows which HK stocks retail investors are most actively关注 — useful for gauging market sentiment " +
    "and identifying trending topics in the HK market. " +
    "Returns top stocks sorted by popularity rank, with price and change %. " +
    "This is the HK-side equivalent of get_hot_stocks(market='港股'). " +
    "Returns {error} if ranking data is unavailable.",
  parameters: Type.Object({}),
  execute: async () => {
    const result = await getHkHotRankViaQuantCli();
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== Export all HK tools =====
export const hkTools: ToolDefinition[] = [
  getHkMarketOverviewTool,
  getHkSouthFlowTool,
  getHkTechnicalTool,
  getHkHotRankTool,
];
