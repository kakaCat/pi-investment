import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

export const calculate_rsiTool: ToolDefinition = {
  name: "calculate_rsi",
  label: "calculate_rsi",
  description: "计算RSI相对强弱指标",
  parameters: Type.Object({
    prices: Type.Array(Type.Number(), {
      description: "按时间顺序排列的收盘价数组",
      minItems: 2,
    }),
    period: Type.Optional(
      Type.Number({
        description: "RSI计算周期，默认14",
        minimum: 1,
        default: 14,
      })
    ),
  }),
  execute: async (_toolCallId, params: any) => {
    const prices = Array.isArray(params?.prices) ? params.prices : [];
    const period = Number.isFinite(params?.period) ? Math.floor(params.period) : 14;

    if (
      period < 1 ||
      prices.length < period + 1 ||
      !prices.every((price: unknown) => Number.isFinite(price))
    ) {
      return {
        content: [
          {
            type: "text" as const,
            text: `参数无效：prices必须包含至少${period + 1}个有效数字，period必须大于0。`,
          },
        ],
        details: {
          success: false,
          error: "INVALID_PARAMS",
          period,
          priceCount: prices.length,
        },
      };
    }

    const deltas: number[] = [];
    for (let i = 1; i < prices.length; i += 1) {
      deltas.push(prices[i] - prices[i - 1]);
    }

    let averageGain = 0;
    let averageLoss = 0;

    for (let i = 0; i < period; i += 1) {
      const delta = deltas[i];
      if (delta > 0) {
        averageGain += delta;
      } else {
        averageLoss += Math.abs(delta);
      }
    }

    averageGain /= period;
    averageLoss /= period;

    for (let i = period; i < deltas.length; i += 1) {
      const delta = deltas[i];
      const gain = delta > 0 ? delta : 0;
      const loss = delta < 0 ? Math.abs(delta) : 0;

      averageGain = (averageGain * (period - 1) + gain) / period;
      averageLoss = (averageLoss * (period - 1) + loss) / period;
    }

    let rsi: number;
    if (averageGain === 0 && averageLoss === 0) {
      rsi = 50;
    } else if (averageLoss === 0) {
      rsi = 100;
    } else {
      const relativeStrength = averageGain / averageLoss;
      rsi = 100 - 100 / (1 + relativeStrength);
    }

    const roundedRsi = Number(rsi.toFixed(2));

    return {
      content: [
        {
          type: "text" as const,
          text: `RSI(${period}) = ${roundedRsi}`,
        },
      ],
      details: {
        success: true,
        rsi: roundedRsi,
        period,
        priceCount: prices.length,
        averageGain: Number(averageGain.toFixed(6)),
        averageLoss: Number(averageLoss.toFixed(6)),
      },
    };
  },
};