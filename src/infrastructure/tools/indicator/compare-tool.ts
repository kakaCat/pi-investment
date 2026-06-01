/**
 * Indicator Compare Tool — 对比指标
 *
 * 对比两个指标的回测表现（收益率、信号差异、过滤交易等）。
 *
 * 从 quant_cli 的 indicators.compare 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

interface CompareParams {
  indicator_id_a: number;
  indicator_id_b: number;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_cash?: number;
}

export const indicatorCompareTool: ToolDefinition = {
  name: "indicator_compare",
  label: "对比指标",
  description:
    "对比两个指标的回测表现（收益率、信号差异、过滤交易等）。" +
    "需要提供两个 indicator_id、股票代码和时间范围。",

  parameters: Type.Object({
    indicator_id_a: Type.Integer({
      description: "指标A的ID",
      minimum: 1,
    }),
    indicator_id_b: Type.Integer({
      description: "指标B的ID",
      minimum: 1,
    }),
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）或港股（如 9988）",
    }),
    start_date: Type.String({
      description: "回测开始日期，格式 YYYY-MM-DD",
    }),
    end_date: Type.String({
      description: "回测结束日期，格式 YYYY-MM-DD",
    }),
    initial_cash: Type.Optional(
      Type.Number({
        description: "初始资金（默认 1000000）",
        minimum: 10000,
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: CompareParams) => {
    try {
      const result = await runQuantV2("indicators.compare", rawParams as unknown as Record<string, unknown>);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(result.data ?? result, null, 2),
        }],
        details: undefined,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `对比指标失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
