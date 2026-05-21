/**
 * Screening Tools - 选股、板块筛选
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import {
  screenStocksBySectorViaQuantCli,
  screenStocksQualityViaQuantCli,
} from "../../quant/screening-query-cli-adapter.js";

// ===== screen_stocks =====
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
    const result = await screenStocksBySectorViaQuantCli(args as any);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

// ===== screen_stocks_quality =====
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
    const result = await screenStocksQualityViaQuantCli(args as any);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

export const screeningTools: ToolDefinition[] = [
  screenStocksTool,
  screenStocksQualityTool,
];
