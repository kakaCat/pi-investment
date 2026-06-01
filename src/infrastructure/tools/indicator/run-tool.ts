/**
 * Indicator Run Tool — 运行指标
 *
 * 在指定股票上运行自定义指标，返回信号和指标值。
 *
 * 从 quant_cli 的 indicators.run 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

interface RunParams {
  indicator_id: number;
  symbol: string;
  limit?: number;
}

export const indicatorRunTool: ToolDefinition = {
  name: "indicator_run",
  label: "运行指标",
  description:
    "在指定股票上运行自定义指标，返回信号和指标值。" +
    "需要提供 indicator_id 和 symbol。",

  parameters: Type.Object({
    indicator_id: Type.Integer({
      description: "指标ID（可通过 indicator_list 查询）",
      minimum: 1,
    }),
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）或港股（如 9988）",
    }),
    limit: Type.Optional(
      Type.Integer({
        description: "返回数据条数限制",
        minimum: 1,
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: RunParams) => {
    try {
      const result = await runQuantV2("indicators.run", rawParams as unknown as Record<string, unknown>);
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
          text: `运行指标失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
