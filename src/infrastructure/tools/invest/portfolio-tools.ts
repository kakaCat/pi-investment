/**
 * Portfolio Tools - 持仓管理、复盘报告
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { PortfolioService } from "../../../services/portfolio/portfolio-service.js";
import { TradeService } from "../../../services/portfolio/trade-service.js";
import { chinaDate } from "../../../utils/china-time.js";
import { join } from "path";
import { readFileSync, existsSync } from "fs";
import { roundN, validatePositiveNumber } from "../shared/validators.js";

const PI_DIR = join(process.cwd(), ".pi-invest");
const _portfolioSvc = new PortfolioService(PI_DIR);

// ===== manage_portfolio =====
export const managePortfolioTool: ToolDefinition = {
  name: "manage_portfolio",
  label: "管理持仓",
  description:
    "Manage the user's local portfolio stored in .pi-invest/portfolio.json. " +
    "Actions:\n" +
    "  'get' — list raw holdings (symbol, quantity, avg_cost, notes)\n" +
    "  'get_with_pnl' — list holdings enriched with current price, today's change%, P&L amount and %\n" +
    "  'add' — record a NEW position or ADD SHARES to an existing one (weighted avg cost is auto-calculated)\n" +
    "  'sell' — record a SELL (减仓/清仓), auto-calculates P&L and writes to trades.json\n" +
    "  'update' — overwrite quantity/avg_cost directly (use to correct mistakes, not for adding shares)\n" +
    "  'remove' — delete a position entirely\n" +
    "When user says '记录持仓', '我持有', '加仓', '录入' → call 'add'. " +
    "When user says '卖出', '减仓', '清仓', '成交了' → call 'sell'. " +
    "When user asks to see holdings/P&L → call 'get_with_pnl'. " +
    "Portfolio data persists across sessions in .pi-invest/portfolio.json.",
  parameters: Type.Object({
    action: Type.Union(
      [Type.Literal("get"), Type.Literal("get_with_pnl"), Type.Literal("add"), Type.Literal("sell"), Type.Literal("update"), Type.Literal("remove")],
      { description: "Operation to perform" },
    ),
    symbol: Type.Optional(Type.String({ description: "Stock code — 6-digit A-share (e.g. '600519') or HK code (e.g. '09988'). Required for add/sell/update/remove." })),
    quantity: Type.Optional(Type.Integer({ description: "Number of shares (for add/sell/update)" })),
    avg_cost: Type.Optional(Type.Number({ description: "Average cost per share in CNY/HKD (for add/update)" })),
    price: Type.Optional(Type.Number({ description: "Sell price per share (for sell action only, e.g. 118.80)" })),
    name: Type.Optional(Type.String({ description: "Stock name (optional, will be auto-filled from market data if omitted)" })),
    market: Type.Optional(Type.Union([Type.Literal("A"), Type.Literal("HK")], { description: "Market: 'A' for A-share (default), 'HK' for Hong Kong" })),
    notes: Type.Optional(Type.String({ description: "Free-text notes, e.g. '分批建仓第1批' or '看好AI算力'" })),
    commission: Type.Optional(Type.Number({ description: "手续费（可选），默认 0。买入时会计入实际成本，如买入 100股@50元，手续费 5元，实际成本为 50.05元/股" })),
    stop_loss: Type.Optional(Type.Number({ description: "止损价（可选），买入时自动创建止损挂单，如 1620 表示跌到 1620 自动卖出" })),
    target_price: Type.Optional(Type.Number({ description: "目标价（可选），买入时自动创建止盈挂单，如 2160 表示涨到 2160 自动卖出" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const { action, symbol, quantity, avg_cost, price, name, market, notes, commission, stop_loss, target_price } = params;
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
        const qtyErr = validatePositiveNumber(quantity, "数量");
        if (qtyErr) return { content: [{ type: "text" as const, text: JSON.stringify({ error: qtyErr, _no_operation_performed: true }) }], details: undefined };
        const costErr = validatePositiveNumber(avg_cost, "成本价");
        if (costErr) return { content: [{ type: "text" as const, text: JSON.stringify({ error: costErr, _no_operation_performed: true }) }], details: undefined };

        const res = _portfolioSvc.add(symbol, quantity, avg_cost, commission || 0, name ?? "", market ?? "A", notes ?? "");

        // ✅ 优化1: 记录交易到 trades.json，保证数据一致性
        try {
          const ts = new TradeService(PI_DIR);
          ts.add(chinaDate(), symbol, name || symbol, "buy", quantity, avg_cost, commission || 0, market ?? "A", notes || "手动录入");
        } catch (e) {
          console.warn("交易记录失败:", e);
        }

        // ✅ 优化3: 自动创建止损/止盈挂单
        const ordersCreated: string[] = [];
        if (stop_loss || target_price) {
          try {
            const { OrderService } = await import("../../../services/order-service.js");
            const orderSvc = new OrderService(PI_DIR);

            if (stop_loss && stop_loss > 0) {
              const stopLossOrder = orderSvc.create({
                symbol,
                name: name || symbol,
                side: "sell",
                type: "stop_loss",
                price: stop_loss,
                quantity,
                market: market ?? "A",
                notes: `自动止损单（成本价 ${avg_cost}）`,
              });
              ordersCreated.push(`止损单 ${stop_loss}`);
            }

            if (target_price && target_price > avg_cost) {
              const targetOrder = orderSvc.create({
                symbol,
                name: name || symbol,
                side: "sell",
                type: "limit",
                price: target_price,
                quantity,
                market: market ?? "A",
                notes: `自动止盈单（成本价 ${avg_cost}）`,
              });
              ordersCreated.push(`止盈单 ${target_price}`);
            }
          } catch (e) {
            console.warn("创建挂单失败:", e);
          }
        }

        // 返回结果，包含挂单创建信息
        const resultWithOrders = {
          ...res,
          orders_created: ordersCreated.length > 0 ? ordersCreated : undefined,
          message: res.message + (ordersCreated.length > 0 ? `，已自动创建挂单: ${ordersCreated.join("、")}` : ""),
        };

        return { content: [{ type: "text" as const, text: JSON.stringify(resultWithOrders) }], details: undefined };
      }
      if (action === "sell") {
        if (!symbol || quantity == null || price == null) {
          return { content: [{ type: "text" as const, text: JSON.stringify({ error: "sell 需要 symbol, quantity, price（卖出均价）", _no_operation_performed: true }) }], details: undefined };
        }
        const qtyErr = validatePositiveNumber(quantity, "卖出数量");
        if (qtyErr) return { content: [{ type: "text" as const, text: JSON.stringify({ error: qtyErr, _no_operation_performed: true }) }], details: undefined };
        const priceErr = validatePositiveNumber(price, "卖出价格");
        if (priceErr) return { content: [{ type: "text" as const, text: JSON.stringify({ error: priceErr, _no_operation_performed: true }) }], details: undefined };

        // 使用服务层的 sell 方法
        const ts = new TradeService(PI_DIR);
        _portfolioSvc.setTradeService(ts);

        try {
          const result = _portfolioSvc.sell(symbol, quantity, price, commission || 0, notes || "");
          return {
            content: [{ type: "text" as const, text: JSON.stringify(result) }],
            details: undefined,
          };
        } catch (e) {
          return {
            content: [{ type: "text" as const, text: JSON.stringify({ error: e instanceof Error ? e.message : String(e), _no_operation_performed: true }) }],
            details: undefined,
          };
        }
      }
      if (action === "update") {
        if (!symbol) {
          return { content: [{ type: "text" as const, text: JSON.stringify({ error: "update 需要 symbol", _no_operation_performed: true }) }], details: undefined };
        }
        if (quantity != null) {
          const qtyErr = validatePositiveNumber(quantity, "数量");
          if (qtyErr) return { content: [{ type: "text" as const, text: JSON.stringify({ error: qtyErr, _no_operation_performed: true }) }], details: undefined };
        }
        if (avg_cost != null) {
          const costErr = validatePositiveNumber(avg_cost, "成本价");
          if (costErr) return { content: [{ type: "text" as const, text: JSON.stringify({ error: costErr, _no_operation_performed: true }) }], details: undefined };
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

// ===== get_review =====
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

export const portfolioTools: ToolDefinition[] = [
  managePortfolioTool,
  getReviewTool,
];
