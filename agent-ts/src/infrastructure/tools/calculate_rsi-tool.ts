import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

export const calculate_rsiTool: ToolDefinition = {
  name: "calculate_rsi",
  label: "calculate_rsi",
  description: "计算RSI相对强弱指标",
  parameters: Type.Object({
    prices: Type.Array(Type.Number(), {
      minItems: 2,
      description: "按时间升序排列的收盘价数组",
    }),
    period: Type.Optional(
      Type.Integer({
        minimum: 1,
        default: 14,
        description: "RSI计算周期",
      }),
    ),
  }),
  execute: async (_toolCallId, params: any) => {
    const prices = params?.prices;
    const period = Number.isInteger(params?.period) ? params.period : 14;

    if (
      !Array.isArray(prices) ||
      !Number.isInteger(period) ||
      period <= 0 ||
      prices.length < period + 1 ||
      prices.some((price) => typeof price !== "number" || !Number.isFinite(price))
    ) {
      return {
        content: [
          {
            type: "text" as const,
            text: "参数无效：prices必须包含至少period + 1个有效价格，period必须为正整数",
          },
        ],
        details: {
          success: false,
          error: "Invalid parameters",
          period,
          pricesCount: Array.isArray(prices) ? prices.length : 0,
        },
      };
    }

    let gainSum = 0;
    let lossSum = 0;

    for (let i = 1; i <= period; i += 1) {
      const change = prices[i] - prices[i - 1];

      if (change > 0) {
        gainSum += change;
      } else {
        lossSum += Math.abs(change);
      }
    }

    let averageGain = gainSum / period;
    let averageLoss = lossSum / period;
    const series: Array<{ index: number; rsi: number }> = [];

    const calculateRsiValue = () => {
      if (averageLoss === 0) return 100;
      if (averageGain === 0) return 0;

      const relativeStrength = averageGain / averageLoss;
      return 100 - 100 / (1 + relativeStrength);
    };

    series.push({
      index: period,
      rsi: Number(calculateRsiValue().toFixed(4)),
    });

    for (let i = period + 1; i < prices.length; i += 1) {
      const change = prices[i] - prices[i - 1];
      const gain = change > 0 ? change : 0;
      const loss = change < 0 ? Math.abs(change) : 0;

      averageGain = (averageGain * (period - 1) + gain) / period;
      averageLoss = (averageLoss * (period - 1) + loss) / period;

      series.push({
        index: i,
        rsi: Number(calculateRsiValue().toFixed(4)),
      });
    }

    const rsi = series[series.length - 1].rsi;

    return {
      content: [{ type: "text" as const, text: `RSI(${period}) = ${rsi}` }],
      details: {
        success: true,
        rsi,
        period,
        pricesCount: prices.length,
        series,
      },
    };
  },
};