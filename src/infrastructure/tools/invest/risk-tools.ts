/**
 * Risk Management Tools - 风控工具
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { callPython } from "../shared/python-caller.js";
import { requireAshare } from "../shared/validators.js";

export const checkTradeRiskTool: ToolDefinition = {
  name: "check_trade_risk",
  label: "交易风控检查",
  description:
    "Execute pre-trade risk checks before recommending buy/sell. " +
    "Validates against 7 rules: blacklist, ST stocks, position limits (10%), " +
    "sector concentration (30%), max drawdown (20%), daily trade limit, liquidity. " +
    "Returns pass/warning/reject with specific violations and adjusted_shares if position limit exceeded. " +
    "Use when: 1) user asks 'can I buy X', 2) before finalizing buy recommendations, " +
    "3) checking existing position risk. " +
    "Note: get_buy_range already includes automatic risk check, so only call this explicitly " +
    "for manual verification or existing positions.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    action: Type.String({ description: "'buy' or 'sell'" }),
    price: Type.Number({ description: "Trade price in CNY" }),
    shares: Type.Integer({ description: "Number of shares to trade" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("check_trade_risk", params);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

export const calculatePositionSizeTool: ToolDefinition = {
  name: "calculate_position_size",
  label: "Kelly仓位计算",
  description:
    "Calculate optimal position size using Kelly Criterion. " +
    "Uses historical win_rate and profit_loss_ratio if ≥10 trades exist for this symbol, " +
    "otherwise defaults to conservative values (50% win rate, 1.5 profit/loss ratio). " +
    "Returns suggested shares (100-share lots), position_pct, position_value, and kelly_params " +
    "showing data source. " +
    "Use when: 1) user asks 'how much should I buy', 2) you need scientific position sizing " +
    "beyond fixed percentages. " +
    "signal_strength (0-1) adjusts position based on signal quality: strong signals = 0.8-1.0, weak = 0.5-0.7.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    price: Type.Number({ description: "Current price in CNY" }),
    signal_strength: Type.Optional(Type.Number({ description: "Signal quality 0-1, default 1.0" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("calculate_position_size", params);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

export const calculateStopLossTool: ToolDefinition = {
  name: "calculate_stop_loss",
  label: "动态止损计算",
  description:
    "Calculate stop-loss price using hybrid strategy: fixed stop (-8%) when unprofitable, " +
    "trailing stop (-10% from peak) when profit >5%. " +
    "Returns stop_loss_price, stop_loss_pct, method (fixed/trailing), and reason explaining the choice. " +
    "Use when: 1) recommending buy entry with stop-loss, 2) user asks 'where should I set stop-loss', " +
    "3) reviewing existing positions. " +
    "Requires entry_price; current_price and highest_price are optional but improve accuracy for existing positions.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    entry_price: Type.Number({ description: "Entry/buy price in CNY" }),
    current_price: Type.Optional(Type.Number({ description: "Current price (optional, fetched if omitted)" })),
    highest_price: Type.Optional(Type.Number({ description: "Highest price since entry (optional)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("calculate_stop_loss", params);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

export const riskTools: ToolDefinition[] = [
  checkTradeRiskTool,
  calculatePositionSizeTool,
  calculateStopLossTool,
];
