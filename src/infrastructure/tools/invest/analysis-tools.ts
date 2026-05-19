/**
 * Analysis Tools - 技术分析、估值、质量评分、买入区间
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { callPython } from "../shared/python-caller.js";
import { requireAshare } from "../shared/validators.js";

// ===== analyze_technical =====
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

// ===== get_buy_range =====
export const getBuyRangeTool: ToolDefinition = {
  name: "get_buy_range",
  label: "计算买入区间",
  description:
    "⚠️ PRICE REFERENCE ONLY - NOT A BUY SIGNAL. Calculate technical support levels (MA20/MA60/20-day low/Bollinger lower) " +
    "and fundamental support (PE-based fair value) to suggest buy price range. " +
    "Returns safe_buy, ideal_buy, stop_loss, target_price with AUTOMATIC risk validation and Kelly position sizing. " +
    "CRITICAL LIMITATIONS: (1) Does NOT check trend direction - may suggest buying in downtrends; " +
    "(2) Does NOT validate fundamental quality - may suggest buying garbage stocks; " +
    "(3) Does NOT consider market environment - may suggest buying in bear markets; " +
    "(4) Assumes support levels hold - they often fail in trending markets; " +
    "(5) PE valuation fails for loss-making, cyclical, or fraudulent companies. " +
    "REQUIRED WORKFLOW: MUST call analyze_stock_quant (score ≥60) + get_quality_score (≥70) + analyze_price_action (trend check) BEFORE using this tool. " +
    "This tool only answers 'at what price' - NOT 'should I buy'. Use for price execution after decision is made.",
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

// ===== get_valuation =====
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

// ===== get_pe_percentile =====
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

// ===== get_quality_score =====
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

// ===== get_exit_plan =====
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

export const analysisTools: ToolDefinition[] = [
  analyzeTechnicalTool,
  analyzePriceActionTool,
  analyzeCandlestickTool,
  getBuyRangeTool,
  getValuationTool,
  getPePercentileTool,
  getQualityScoreTool,
  getExitPlanTool,
  comparePeersTool,
];
