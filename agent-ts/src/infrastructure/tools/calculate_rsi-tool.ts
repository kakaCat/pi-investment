import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

type RsiPoint = {
  index: number;
  close: number;
  gain: number;
  loss: number;
  averageGain: number;
  averageLoss: number;
  rsi: number;
};

function round(value: number, digits = 4): number {
  return Number(value.toFixed(digits));
}

function calculateRsi(prices: number[], period: number): RsiPoint[] {
  const changes = prices.slice(1).map((price, index) => price - prices[index]);
  const gains = changes.map((change) => Math.max(change, 0));
  const losses = changes.map((change) => Math.max(-change, 0));

  let averageGain = gains.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
  let averageLoss = losses.slice(0, period).reduce((sum, value) => sum + value, 0) / period;

  const values: RsiPoint[] = [];

  for (let i = period; i < changes.length; i += 1) {
    averageGain = (averageGain * (period - 1) + gains[i]) / period;
    averageLoss = (averageLoss * (period - 1) + losses[i]) / period;

    const rsi = averageLoss === 0 ? 100 : 100 - 100 / (1 + averageGain / averageLoss);

    values.push({
      index: i + 1,
      close: prices[i + 1],
      gain: round(gains[i]),
      loss: round(losses[i]),
      averageGain: round(averageGain),
      averageLoss: round(averageLoss),
      rsi: round(rsi),
    });
  }

  return values;
}

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
        description: "RSI计算周期，默认14",
      }),
    ),
  }),
  execute: async (_toolCallId: string, params: any) => {
    const prices = Array.isArray(params?.prices) ? params.prices : undefined;
    const period = Number.isInteger(params?.period) ? params.period : 14;

    if (!prices || prices.some((price: any) => typeof price !== "number" || !Number.isFinite(price))) {
      return {
        content: [{ type: "text" as const, text: "参数无效：prices必须是有效数字数组" }],
        details: {
          success: false,
          error: "prices must be an array of finite numbers",
          received: params,
        },
      };
    }

    if (period < 1 || prices.length <= period + 1) {
      return {
        content: [{ type: "text" as const, text: "参数无效：价格数量必须大于RSI周期+1" }],
        details: {
          success: false,
          error: "prices length must be greater than period + 1",
          period,
          pricesLength: prices.length,
        },
      };
    }

    const values = calculateRsi(prices, period);
    const latestRsi = values.length > 0 ? values[values.length - 1].rsi : null;

    return {
      content: [
        {
          type: "text" as const,
          text: latestRsi === null ? "RSI计算完成，但没有生成有效结果" : `RSI(${period}) = ${latestRsi}`,
        },
      ],
      details: {
        success: true,
        period,
        latestRsi,
        values,
      },
    };
  },
};