/**
 * Check Pending Orders Tool - 挂单检查与自动成交
 *
 * 工作流:
 *   1. 调用 OrderService.checkAndFillOrders() 执行检查和成交
 *   2. 格式化输出结果
 *
 * 业务逻辑已移至 OrderService.checkAndFillOrders()
 */

import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { OrderService } from "../../services/order-service.js";
import { PortfolioService } from "../../services/portfolio/portfolio-service.js";
import { TradeService } from "../../services/portfolio/trade-service.js";
import { chinaDate } from "../../utils/china-time.js";

const PI_DIR = ".pi-invest";

// ─── 工具函数 ──────────────────────────────────────────────────────────────

function fmtPrice(v: number): string {
  return `¥${v.toFixed(2)}`;
}

function fmtPct(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

// ─── 渲染输出 ──────────────────────────────────────────────────────────────

function renderFills(fills: any[]): string {
  if (fills.length === 0) return "";
  let out = `## ✅ 本次成交 (${fills.length})\n\n`;
  fills.forEach((f, i) => {
    const actionEmoji = f.result.portfolioAction === "add" ? "🟢" : "🔴";
    const sideLabel = f.order.side === "buy" ? "买入" : "卖出";
    const typeLabel =
      f.order.type === "limit"
        ? "限价单"
        : f.order.type === "stop_loss"
          ? "止损单"
          : "分批计划";
    out += `### ${actionEmoji} ${i + 1}. ${f.order.name} (${f.order.symbol})\n`;
    out += `- 方向: ${sideLabel} | 类型: ${typeLabel}\n`;
    out += `- 触发条件: ${f.triggerCondition}\n`;
    out += `- 成交: ${f.fillQuantity}股 @ ${fmtPrice(f.result.fillPrice)}\n`;
    out += `- 持仓更新: ${f.result.portfolioMessage}\n`;
    out += `- 交易记录: ${f.result.tradeRecorded ? "✅ 已记录" : "❌ 记录失败"}\n`;
    out += "\n";
  });
  return out;
}

function renderNotYets(notYets: any[]): string {
  if (notYets.length === 0) return "";
  let out = `## ⏳ 未触发 (${notYets.length})\n\n`;
  notYets.forEach((n) => {
    const sideLabel = n.order.side === "buy" ? "📉 买入" : "📈 卖出";
    const typeLabel =
      n.order.type === "limit"
        ? "限价"
        : n.order.type === "stop_loss"
          ? "止损"
          : "分批";
    out += `### ${sideLabel} ${typeLabel} ${n.order.name} (${n.order.symbol})\n`;
    out += `- 当前价: ${fmtPrice(n.currentPrice)} | 挂单价: ${fmtPrice(n.order.price)}\n`;
    out += `- 状态: ${n.reason}\n\n`;
  });
  return out;
}

function renderErrors(errors: any[]): string {
  if (errors.length === 0) return "";
  let out = `## ❌ 数据错误 (${errors.length})\n\n`;
  errors.forEach((e) => {
    out += `- ${e.order.name} (${e.order.symbol}): ${e.error}\n`;
  });
  out += "\n";
  return out;
}

// ─── Tool Definition ───────────────────────────────────────────────────────

export const checkPendingOrdersTool: ToolDefinition = {
  name: "check_pending_orders",
  label: "检查挂单",
  description:
    "检查所有挂单是否满足成交条件。读取 orders.json 中的 pending 挂单，" +
    "获取每只股票实时价格，自动检测触发条件（限价买入/卖出、止损单）。" +
    "触发后自动更新持仓（portfolio.json）和交易记录（trades.json）。" +
    "可指定 symbol 只检查某只股票的挂单，不传则检查全部。",
  parameters: Type.Object({
    symbol: Type.Optional(
      Type.String({
        description:
          "可选，只检查指定股票的挂单（如 '688981'）。不传则检查全部。",
      }),
    ),
    dry_run: Type.Optional(
      Type.Boolean({
        description:
          "试运行模式：只检查是否触发，不实际执行成交。默认 false。",
      }),
    ),
  }),
  execute: async (toolCallId: string, params: any) => {
    try {
      const symbol: string | undefined = params.symbol;
      const dryRun: boolean = params.dry_run ?? false;

      // 创建服务实例并注入依赖
      const orderService = new OrderService(PI_DIR);
      const portfolioService = new PortfolioService(PI_DIR);
      const tradeService = new TradeService(PI_DIR);

      orderService.setServices(portfolioService, tradeService);

      // 调用服务层方法
      const result = await orderService.checkAndFillOrders(symbol, dryRun);

      // 无挂单情况
      if (result.totalChecked === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: `📋 当前无${symbol ? ` ${symbol} 的` : ""}挂单${result.expiredCount > 0 ? `（已清理 ${result.expiredCount} 个过期挂单）` : ""}`,
            },
          ],
          details: {
            expiredOrders: result.expiredCount,
            checked: 0,
            fills: [],
            notYets: [],
            errors: [],
          },
        };
      }

      // ── 构建输出 ──
      const lines: string[] = [];

      lines.push(`📋 挂单检查报告 — ${chinaDate()}`);
      lines.push(`检查 ${result.totalChecked} 个挂单`);
      if (result.expiredCount > 0) lines.push(`已自动清理 ${result.expiredCount} 个过期挂单`);
      if (dryRun) lines.push("**【试运行模式】仅检查，未实际成交**");
      lines.push("\n");

      if (result.fills.length > 0) {
        lines.push(renderFills(result.fills));
      }

      if (result.notYets.length > 0) {
        lines.push(renderNotYets(result.notYets));
      }

      if (result.errors.length > 0) {
        lines.push(renderErrors(result.errors));
      }

      if (result.fills.length === 0 && result.notYets.length === 0 && result.errors.length === 0) {
        lines.push("所有挂单状态正常，无触发。");
      }

      // ── 总体建议 ──
      lines.push(`## 💡 总结\n`);
      lines.push(
        `✅ 成交: ${result.fills.length} · ⏳ 等待: ${result.notYets.length} · ❌ 错误: ${result.errors.length}${dryRun ? " · 🧪 试运行" : ""}`,
      );
      if (result.fills.length > 0) {
        lines.push(
          `\n挂单已成交${dryRun ? "（试运行，未实际执行）" : "，持仓和交易记录已自动更新"}。`,
        );
      }
      lines.push(`\n📂 orders.json 路径: ${orderService.piDirPath}/orders.json`);

      return {
        content: [{ type: "text" as const, text: lines.join("\n") }],
        details: {
          expiredOrders: result.expiredCount,
          checked: result.totalChecked,
          fills: result.fills.map((f) => ({
            symbol: f.order.symbol,
            name: f.order.name,
            side: f.order.side,
            fillPrice: f.result.fillPrice,
            fillQuantity: f.fillQuantity,
          })),
          notYets: result.notYets.map((n) => ({
            symbol: n.order.symbol,
            name: n.order.name,
            currentPrice: n.currentPrice,
            targetPrice: n.order.price,
          })),
          errors: result.errors.map((e) => ({
            symbol: e.order.symbol,
            error: e.error,
          })),
        },
      };
    } catch (e) {
      return {
        content: [
          {
            type: "text" as const,
            text: `❌ 检查挂单失败: ${e instanceof Error ? e.message : String(e)}`,
          },
        ],
        details: { error: String(e) },
      };
    }
  },
};
