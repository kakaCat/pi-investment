import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

export const check_stop_loss_triggerTool: ToolDefinition = {
  name: "check_stop_loss_trigger",
  label: "check_stop_loss_trigger",
  description: "检查持仓是否触发止损条件",
  parameters: Type.Object({
    symbol: Type.Optional(
      Type.String({
        description: "股票代码或持仓标识",
      }),
    ),
    currentPrice: Type.Number({
      description: "当前价格",
      exclusiveMinimum: 0,
    }),
    costPrice: Type.Optional(
      Type.Number({
        description: "持仓成本价",
        exclusiveMinimum: 0,
      }),
    ),
    stopLossPrice: Type.Optional(
      Type.Number({
        description: "止损价，若未提供则基于成本价和止损比例计算",
        exclusiveMinimum: 0,
      }),
    ),
    stopLossPct: Type.Optional(
      Type.Number({
        description: "止损比例，百分比形式，默认 8",
        minimum: 0,
        maximum: 100,
      }),
    ),
    quantity: Type.Optional(
      Type.Number({
        description: "持仓数量",
        minimum: 0,
      }),
    ),
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const symbol = typeof params.symbol === "string" ? params.symbol : "未知持仓";
      const currentPrice = Number(params.currentPrice);
      const costPrice =
        params.costPrice === undefined ? undefined : Number(params.costPrice);
      const inputStopLossPrice =
        params.stopLossPrice === undefined
          ? undefined
          : Number(params.stopLossPrice);
      const stopLossPct =
        params.stopLossPct === undefined ? 8 : Number(params.stopLossPct);
      const quantity =
        params.quantity === undefined ? undefined : Number(params.quantity);

      if (!Number.isFinite(currentPrice) || currentPrice <= 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: "止损检查失败: currentPrice 必须为大于 0 的数字",
            },
          ],
          details: {
            triggered: false,
            error: "INVALID_CURRENT_PRICE",
          },
        };
      }

      if (
        inputStopLossPrice === undefined &&
        (costPrice === undefined || !Number.isFinite(costPrice) || costPrice <= 0)
      ) {
        return {
          content: [
            {
              type: "text" as const,
              text: "止损检查失败: 请提供有效的 stopLossPrice，或提供 costPrice 以便计算止损价",
            },
          ],
          details: {
            triggered: false,
            error: "MISSING_STOP_LOSS_REFERENCE",
          },
        };
      }

      if (
        inputStopLossPrice !== undefined &&
        (!Number.isFinite(inputStopLossPrice) || inputStopLossPrice <= 0)
      ) {
        return {
          content: [
            {
              type: "text" as const,
              text: "止损检查失败: stopLossPrice 必须为大于 0 的数字",
            },
          ],
          details: {
            triggered: false,
            error: "INVALID_STOP_LOSS_PRICE",
          },
        };
      }

      if (!Number.isFinite(stopLossPct) || stopLossPct < 0 || stopLossPct > 100) {
        return {
          content: [
            {
              type: "text" as const,
              text: "止损检查失败: stopLossPct 必须在 0 到 100 之间",
            },
          ],
          details: {
            triggered: false,
            error: "INVALID_STOP_LOSS_PCT",
          },
        };
      }

      const resolvedStopLossPrice =
        inputStopLossPrice ?? (costPrice as number) * (1 - stopLossPct / 100);
      const triggered = currentPrice <= resolvedStopLossPrice;
      const lossPct =
        costPrice !== undefined
          ? ((currentPrice - costPrice) / costPrice) * 100
          : undefined;
      const distanceToStopLossPct =
        ((currentPrice - resolvedStopLossPrice) / resolvedStopLossPrice) * 100;
      const unrealizedPnl =
        costPrice !== undefined && quantity !== undefined
          ? (currentPrice - costPrice) * quantity
          : undefined;

      const text = triggered
        ? `${symbol} 已触发止损条件。当前价 ${currentPrice.toFixed(2)}，止损价 ${resolvedStopLossPrice.toFixed(2)}。`
        : `${symbol} 未触发止损条件。当前价 ${currentPrice.toFixed(2)}，止损价 ${resolvedStopLossPrice.toFixed(2)}。`;

      return {
        content: [
          {
            type: "text" as const,
            text,
          },
        ],
        details: {
          symbol,
          triggered,
          currentPrice,
          costPrice,
          stopLossPrice: Number(resolvedStopLossPrice.toFixed(4)),
          stopLossPct,
          quantity,
          lossPct:
            lossPct === undefined ? undefined : Number(lossPct.toFixed(2)),
          distanceToStopLossPct: Number(distanceToStopLossPct.toFixed(2)),
          unrealizedPnl:
            unrealizedPnl === undefined
              ? undefined
              : Number(unrealizedPnl.toFixed(2)),
          suggestedAction: triggered ? "consider_sell" : "hold_and_monitor",
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
          triggered: false,
          error: "EXECUTION_FAILED",
        },
      };
    }
  },
};