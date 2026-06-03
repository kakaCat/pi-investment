import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

type RsiPoint = {
  index: number;
  price: number;
  rsi: number;
};

const round = (value: number, precision = 2): number => {
  const factor = 10 ** precision;
  return Math.round(value * factor) / factor;
};

const calculateRsiValue = (averageGain: number, averageLoss: number): number => {
  if (averageGain === 0 && averageLoss === 0) {
    return 50;
  }

  if (averageLoss === 0) {
    return 100;
  }

  const relativeStrength = averageGain / averageLoss;
  return 100 - 100 / (1 + relativeStrength);
};

export const calculate_rsiTool: ToolDefinition = {
  name: "calculate_rsi",
  label: "calculate_rsi",
  description: "计算RSI相对强弱指标",
  parameters: Type.Object({
    prices: Type.Array(Type.Number(), {
      description: "按时间升序排列的价格序列",
      minItems: 2,
    }),
    period: Type.Optional(
      Type.Integer({
        description: "RSI计算周期",
        minimum: 1,
        default: 14,
      }),
    ),
  }),
  execute: async (_toolCallId, params: any) => {
    const prices = Array.isArray(params?.prices) ? params.prices : [];
    const period = Number.isInteger(params?.period) ? params.period : 14;

    if (period < 1) {
      return {
        content: [{ type: "text" as const, text: "RSI计算失败：period必须大于等于1。" }],
        details: {
          success: false,
          error: "INVALID_PERIOD",
          period,
        },
      };
    }

    if (prices.length < period + 1) {
      return {
        content: [
          {
            type: "text" as const,
            text: `RSI计算失败：价格数量至少需要${period + 1}个。`,
          },
        ],
        details: {
          success: false,
          error: "INSUFFICIENT_PRICES",
          period,
          priceCount: prices.length,
        },
      };
    }

    if (!prices.every((price) => typeof price === "number" && Number.isFinite(price))) {
      return {
        content: [{ type: "text" as const, text: "RSI计算失败：prices必须全部为有效数字。" }],
        details: {
          success: false,
          error: "INVALID_PRICES",
          period,
          priceCount: prices.length,
        },
      };
    }

    let gainSum = 0;
    let lossSum = 0;

    for (let index = 1; index <= period; index += 1) {
      const change = prices[index] - prices[index - 1];

      if (change >= 0) {
        gainSum += change;
      } else {
        lossSum += Math.abs(change);
      }
    }

    let averageGain = gainSum / period;
    let averageLoss = lossSum / period;
    const values: RsiPoint[] = [
      {
        index: period,
        price: prices[period],
        rsi: round(calculateRsiValue(averageGain, averageLoss)),
      },
    ];

    for (let index = period + 1; index < prices.length; index += 1) {
      const change = prices[index] - prices[index - 1];
      const gain = change > 0 ? change : 0;
      const loss = change < 0 ? Math.abs(change) : 0;

      averageGain = (averageGain * (period - 1) + gain) / period;
      averageLoss = (averageLoss * (period - 1) + loss) / period;

      values.push({
        index,
        price: prices[index],
        rsi: round(calculateRsiValue(averageGain, averageLoss)),
      });
    }

    const latest = values[values.length - 1];

    return {
      content: [
        {
          type: "text" as const,
          text: `RSI(${period}) = ${latest.rsi}`,
        },
      ],
      details: {
        success: true,
        period,
        latestRsi: latest.rsi,
        latestIndex: latest.index,
        latestPrice: latest.price,
        values,
      },
    };
  },
};