import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { PortfolioService } from "../../services/portfolio/portfolio-service.js";
import { PriceService } from "../../services/data/price-service.js";
import { StockDBService } from "../../services/data/stock-db-service.js";
import { join } from "path";
import { homedir } from "os";

const round = (value: number, digits = 2): number => {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
};

const toFiniteNumber = (value: unknown): number | undefined => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

export const check_stop_loss_triggerTool: ToolDefinition = {
  name: "check_stop_loss_trigger",
  label: "check_stop_loss_trigger",
  description: "检查持仓是否触发止损条件。可以检查单个持仓或批量检查所有持仓。",
  promptSnippet: '需要检查持仓是否触发止损时',
  promptGuidelines: [
    '每日盘后自动检查，无需手动调用',
    '触发止损时会发送警报通知',
    '返回触发止损的股票列表和原因'
  ],
  parameters: Type.Object({
    mode: Type.Optional(
      Type.Union([Type.Literal("single"), Type.Literal("batch")], {
        description: "检查模式：single=单个持仓，batch=批量检查所有持仓（默认single）",
      })
    ),
    symbol: Type.Optional(
      Type.String({
        description: "持仓标的代码或名称（mode=single时必填）",
      }),
    ),
    entryPrice: Type.Number({
      description: "建仓价格",
      exclusiveMinimum: 0,
    }),
    currentPrice: Type.Number({
      description: "当前价格",
      exclusiveMinimum: 0,
    }),
    stopLossPrice: Type.Optional(
      Type.Number({
        description: "固定止损价",
        exclusiveMinimum: 0,
      }),
    ),
    stopLossPercent: Type.Optional(
      Type.Number({
        description: "止损百分比，例如 8 表示亏损 8% 止损",
        exclusiveMinimum: 0,
        maximum: 100,
      }),
    ),
    highestPrice: Type.Optional(
      Type.Number({
        description: "持仓期间最高价，用于移动止损",
        exclusiveMinimum: 0,
      }),
    ),
    trailingStopPercent: Type.Optional(
      Type.Number({
        description: "移动止损百分比，例如 10 表示从最高价回撤 10% 止损",
        exclusiveMinimum: 0,
        maximum: 100,
      }),
    ),
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const mode = params?.mode === "batch" ? "batch" : "single";

      // 批量模式：检查所有持仓
      if (mode === "batch") {
        const base = join(homedir(), "Documents", "ai", "pi-investment");
        const piDir = join(base, ".pi-invest");
        const portfolioService = new PortfolioService(piDir);
        const stockDBService = new StockDBService(piDir);
        const priceService = new PriceService(stockDBService);

        const portfolio = portfolioService.load();
        const holdings = portfolio.holdings;

        if (holdings.length === 0) {
          return {
            content: [
              {
                type: "text" as const,
                text: "当前没有持仓",
              },
            ],
            details: {
              status: "no_holdings",
              holdingsCount: 0,
            },
          };
        }

        const results: any[] = [];
        let triggeredCount = 0;

        for (const holding of holdings) {
          const currentPrice = await priceService.getPrice(holding.symbol);
          if (!currentPrice) {
            results.push({
              symbol: holding.symbol,
              name: holding.name,
              status: "price_unavailable",
              triggered: false,
            });
            continue;
          }

          // 使用默认止损规则：8%固定止损
          const stopLossPercent = 8;
          const entryPrice = holding.avg_cost;
          const stopPrice = entryPrice * (1 - stopLossPercent / 100);
          const triggered = currentPrice <= stopPrice;

          if (triggered) {
            triggeredCount++;
          }

          const pnlAmount = round(currentPrice - entryPrice);
          const pnlPercent = round(((currentPrice - entryPrice) / entryPrice) * 100);
          const distanceToStop = round(currentPrice - stopPrice);
          const distanceToStopPercent = round(((currentPrice - stopPrice) / stopPrice) * 100);

          results.push({
            symbol: holding.symbol,
            name: holding.name,
            status: triggered ? "triggered" : "not_triggered",
            triggered,
            entryPrice: round(entryPrice),
            currentPrice: round(currentPrice),
            stopPrice: round(stopPrice),
            pnlAmount,
            pnlPercent,
            distanceToStop,
            distanceToStopPercent,
            quantity: holding.quantity,
            marketValue: round(currentPrice * holding.quantity),
          });
        }

        const lines: string[] = [];
        lines.push(`# 批量止损检查结果`);
        lines.push(`持仓数量: ${holdings.length}，触发止损: ${triggeredCount}`);
        lines.push("");

        if (triggeredCount > 0) {
          lines.push("⚠️ 已触发止损:");
          results
            .filter((r) => r.triggered)
            .forEach((r) => {
              lines.push(
                `- ${r.symbol} ${r.name}: 成本 ${r.entryPrice}，现价 ${r.currentPrice}，止损线 ${r.stopPrice}，亏损 ${r.pnlPercent}%`
              );
            });
          lines.push("");
        }

        lines.push("未触发止损:");
        results
          .filter((r) => !r.triggered && r.status !== "price_unavailable")
          .forEach((r) => {
            lines.push(
              `- ${r.symbol} ${r.name}: 成本 ${r.entryPrice}，现价 ${r.currentPrice}，距止损线 ${r.distanceToStopPercent}%`
            );
          });

        if (results.some((r) => r.status === "price_unavailable")) {
          lines.push("");
          lines.push("价格不可用:");
          results
            .filter((r) => r.status === "price_unavailable")
            .forEach((r) => {
              lines.push(`- ${r.symbol} ${r.name}`);
            });
        }

        return {
          content: [
            {
              type: "text" as const,
              text: lines.join("\n"),
            },
          ],
          details: {
            status: "batch_complete",
            mode: "batch",
            holdingsCount: holdings.length,
            triggeredCount,
            results,
          },
        };
      }

      // 单个模式：原有逻辑
      const symbol =
        typeof params?.symbol === "string" && params.symbol.trim() !== ""
          ? params.symbol.trim()
          : "当前持仓";

      const entryPrice = toFiniteNumber(params?.entryPrice);
      const currentPrice = toFiniteNumber(params?.currentPrice);
      const stopLossPrice = toFiniteNumber(params?.stopLossPrice);
      const stopLossPercent = toFiniteNumber(params?.stopLossPercent);
      const highestPrice = toFiniteNumber(params?.highestPrice);
      const trailingStopPercent = toFiniteNumber(params?.trailingStopPercent);

      const errors: string[] = [];

      if (entryPrice === undefined || entryPrice <= 0) {
        errors.push("entryPrice 必须是大于 0 的数字");
      }
      if (currentPrice === undefined || currentPrice <= 0) {
        errors.push("currentPrice 必须是大于 0 的数字");
      }
      if (
        stopLossPrice === undefined &&
        stopLossPercent === undefined &&
        trailingStopPercent === undefined
      ) {
        errors.push("至少提供一种止损条件：stopLossPrice、stopLossPercent 或 trailingStopPercent");
      }
      if (stopLossPercent !== undefined && (stopLossPercent <= 0 || stopLossPercent > 100)) {
        errors.push("stopLossPercent 必须在 0 到 100 之间");
      }
      if (
        trailingStopPercent !== undefined &&
        (trailingStopPercent <= 0 || trailingStopPercent > 100)
      ) {
        errors.push("trailingStopPercent 必须在 0 到 100 之间");
      }
      if (trailingStopPercent !== undefined) {
        if (highestPrice === undefined || highestPrice <= 0) {
          errors.push("使用移动止损时必须提供大于 0 的 highestPrice");
        }
      }
      if (
        entryPrice !== undefined &&
        highestPrice !== undefined &&
        highestPrice < entryPrice
      ) {
        errors.push("highestPrice 不能低于 entryPrice");
      }

      if (errors.length > 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: `止损检查失败: ${errors.join("；")}`,
            },
          ],
          details: {
            status: "invalid_params",
            triggered: false,
            symbol,
            errors,
          },
        };
      }

      const stopLevels: Array<{
        type: "fixed_price" | "percentage" | "trailing";
        label: string;
        stopPrice: number;
      }> = [];

      if (stopLossPrice !== undefined) {
        stopLevels.push({
          type: "fixed_price",
          label: "固定止损价",
          stopPrice: stopLossPrice,
        });
      }

      if (stopLossPercent !== undefined && entryPrice !== undefined) {
        stopLevels.push({
          type: "percentage",
          label: "百分比止损",
          stopPrice: entryPrice * (1 - stopLossPercent / 100),
        });
      }

      if (
        trailingStopPercent !== undefined &&
        highestPrice !== undefined
      ) {
        stopLevels.push({
          type: "trailing",
          label: "移动止损",
          stopPrice: highestPrice * (1 - trailingStopPercent / 100),
        });
      }

      const normalizedStopLevels = stopLevels.map((item) => ({
        ...item,
        stopPrice: round(item.stopPrice),
      }));

      const triggeredLevels = normalizedStopLevels.filter(
        (item) => currentPrice! <= item.stopPrice,
      );

      const effectiveStopPrice =
        normalizedStopLevels.length > 0
          ? Math.max(...normalizedStopLevels.map((item) => item.stopPrice))
          : undefined;

      const triggered = triggeredLevels.length > 0;
      const pnlAmount = round(currentPrice! - entryPrice!);
      const pnlPercent = round(((currentPrice! - entryPrice!) / entryPrice!) * 100);
      const distanceToStop =
        effectiveStopPrice !== undefined
          ? round(currentPrice! - effectiveStopPrice)
          : undefined;
      const distanceToStopPercent =
        effectiveStopPrice !== undefined
          ? round(((currentPrice! - effectiveStopPrice) / effectiveStopPrice) * 100)
          : undefined;

      const triggerReasons = triggeredLevels.map(
        (item) => `${item.label}已触发 (当前价 ${round(currentPrice!)} <= 止损价 ${item.stopPrice})`,
      );

      let text = `${symbol}止损检查结果: ${triggered ? "已触发止损" : "未触发止损"}\n`;
      text += `建仓价: ${round(entryPrice!)}，当前价: ${round(currentPrice!)}\n`;
      text += `盈亏: ${pnlAmount >= 0 ? "+" : ""}${pnlAmount} (${pnlPercent >= 0 ? "+" : ""}${pnlPercent}%)\n`;

      if (normalizedStopLevels.length > 0) {
        text += `止损条件:\n`;
        normalizedStopLevels.forEach((item, index) => {
          text += `${index + 1}. ${item.label}: ${item.stopPrice}\n`;
        });
      }

      if (effectiveStopPrice !== undefined) {
        text += `有效止损线: ${effectiveStopPrice}\n`;
      }

      if (triggered) {
        text += `触发原因: ${triggerReasons.join("；")}`;
      } else if (distanceToStop !== undefined && distanceToStopPercent !== undefined) {
        text += `距离止损线: ${distanceToStop >= 0 ? "+" : ""}${distanceToStop} (${distanceToStopPercent >= 0 ? "+" : ""}${distanceToStopPercent}%)`;
      }

      return {
        content: [
          {
            type: "text" as const,
            text,
          },
        ],
        details: {
          status: triggered ? "triggered" : "not_triggered",
          triggered,
          symbol,
          entryPrice: round(entryPrice!),
          currentPrice: round(currentPrice!),
          pnlAmount,
          pnlPercent,
          effectiveStopPrice,
          stopLevels: normalizedStopLevels,
          triggeredLevels,
          triggerReasons,
          distanceToStop,
          distanceToStopPercent,
        },
      };
    } catch (e) {
      return {
        content: [
          {
            type: "text" as const,
            text: `止损检查失败: ${e instanceof Error ? e.message : String(e)}`,
          },
        ],
        details: {
          status: "error",
          triggered: false,
          error: e instanceof Error ? e.message : String(e),
        },
      };
    }
  },
};