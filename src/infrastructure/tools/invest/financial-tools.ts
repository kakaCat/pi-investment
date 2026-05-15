/**
 * Financial Tools - 财务报表、财务指标
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { callPython } from "../shared/python-caller.js";
import { requireAshare, detectMarket } from "../shared/validators.js";

// ===== get_financial_data =====
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

// ===== get_financial_statements =====
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

// ===== get_hk_financials =====
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

// ===== get_hk_analysis =====
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

export const financialTools: ToolDefinition[] = [
  getFinancialDataTool,
  getFinancialStatementsTool,
  getHkFinancialsTool,
  getHkAnalysisTool,
];
