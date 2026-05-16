import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

type StopLossStatus = "triggered" | "warning" | "safe" | "invalid";

function formatPrice(value: number): string {
  return `¥${value.toFixed(2)}`;
}

function formatPct(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export const check_stop_loss_triggerTool: ToolDefinition = {
  name: "check_stop_loss_trigger",
  label: "check_stop_loss_trigger",
  description: "检查持仓是否触发止损条件",
  parameters: Type.Object(
    {
      symbol: Type.Optional(
        Type.String({
          description: "持仓代码",
        }),
      ),
      name: Type.Optional(
        Type.String({
          description: "持仓名称",
        }),
      ),
      currentPrice: Type.Number({
        description: "当前价格",
        exclusiveMinimum: 0,
      }),
      costPrice: Type.Number({
        description: "持仓成本价",
        exclusiveMinimum: 0,
      }),
      quantity: Type.Optional(
        Type.Number({
          description: "持仓数量",
          minimum: 0,
        }),
      ),
      stopLossPrice: Type.Optional(
        Type.Number({
          description: "显式止损价",
          exclusiveMinimum: 0,
        }),
      ),
      stopLossPct: Type.Optional(
        Type.Number({
          description: "止损比例，支持 8 或 -8，表示相对成本价 8% 的止损幅度",
        }),
      ),
      warningBufferPct: Type.Optional(
        Type.Number({
          description: "接近止损提醒阈值百分比，默认 3",
          minimum: 0,
          maximum: 100,
        }),
      ),
    },
    {
      additionalProperties: false,
    },
  ),
  execute: async (_toolCallId, params: any) => {
    const symbol =
      typeof params?.symbol === "string" && params.symbol.trim().length > 0
        ? params.symbol.trim()
        : "UNKNOWN";
    const name =
      typeof params?.name === "string" && params.name.trim().length > 0
        ? params.name.trim()
        : "未命名持仓";

    const currentPrice = Number(params?.currentPrice);
    const costPrice = Number(params?.costPrice);
    const quantity =
      typeof params?.quantity === "number" && Number.isFinite(params.quantity)
        ? params.quantity
        : 0;
    const warningBufferPct =
      typeof params?.warningBufferPct === "number" &&
      Number.isFinite(params.warningBufferPct)
        ? params.warningBufferPct
        : 3;

    if (
      !Number.isFinite(currentPrice) ||
      currentPrice <= 0 ||
      !Number.isFinite(costPrice) ||
      costPrice <= 0
    ) {
      return {
        content: [
          {
            type: "text" as const,
            text: "参数无效：必须提供大于 0 的 currentPrice 和 costPrice。",
          },
        ],
        details: {
          status: "invalid" as StopLossStatus,
          symbol,
          name,
          reason: "missing_or_invalid_price",
        },
      };
    }

    let stopLossPrice: number | undefined;
    let stopLossSource: "explicit" | "percentage" | "none" = "none";

    if (
      typeof params?.stopLossPrice === "number" &&
      Number.isFinite(params.stopLossPrice) &&
      params.stopLossPrice > 0
    ) {
      stopLossPrice = params.stopLossPrice;
      stopLossSource = "explicit";
    } else if (
      typeof params?.stopLossPct === "number" &&
      Number.isFinite(params.stopLossPct) &&
      params.stopLossPct !== 0
    ) {
      const stopLossPct = Math.abs(params.stopLossPct);
      stopLossPrice = costPrice * (1 - stopLossPct / 100);
      stopLossSource = "percentage";
    }

    if (!Number.isFinite(stopLossPrice) || (stopLossPrice ?? 0) <= 0) {
      return {
        content: [
          {
            type: "text" as const,
            text: `持仓 ${symbol}（${name}）缺少有效止损参数，无法判断是否触发止损。`,
          },
        ],
        details: {
          status: "invalid" as StopLossStatus,
          symbol,
          name,
          currentPrice,
          costPrice,
          quantity,
          reason: "missing_stop_loss",
        },
      };
    }

    const pnlPct = ((currentPrice - costPrice) / costPrice) * 100;
    const pnlAmount = (currentPrice - costPrice) * quantity;
    const distanceToStopLossPct =
      ((currentPrice - stopLossPrice) / stopLossPrice) * 100;

    let status: StopLossStatus = "safe";
    let recommendation = "未触发止损，继续按计划跟踪持仓。";

    if (currentPrice <= stopLossPrice) {
      status = "triggered";
      recommendation = "已触发止损，建议尽快复核并执行交易纪律。";
    } else if (distanceToStopLossPct <= warningBufferPct) {
      status = "warning";
      recommendation = "价格已接近止损位，建议提高警惕并准备应对方案。";
    }

    const summaryLines = [
      `持仓 ${symbol}（${name}）止损检查结果: ${status}`,
      `当前价: ${formatPrice(currentPrice)}`,
      `成本价: ${formatPrice(costPrice)}`,
      `止损价: ${formatPrice(stopLossPrice)}`,
      `盈亏: ${formatPct(pnlPct)}${quantity > 0 ? `，约 ${formatPrice(pnlAmount)}` : ""}`,
      `距离止损: ${formatPct(distanceToStopLossPct)}`,
      `建议: ${recommendation}`,
    ];

    return {
      content: [
        {
          type: "text" as const,
          text: summaryLines.join("\n"),
        },
      ],
      details: {
        status,
        symbol,
        name,
        currentPrice,
        costPrice,
        quantity,
        stopLossPrice,
        stopLossSource,
        warningBufferPct,
        pnlPct,
        pnlAmount,
        distanceToStopLossPct,
        isTriggered: status === "triggered",
        isWarning: status === "warning",
        recommendation,
      },
    };
  },
};