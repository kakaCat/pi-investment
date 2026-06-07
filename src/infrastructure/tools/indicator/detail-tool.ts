/**
 * Indicator Detail Tool — 查看指标详情
 *
 * 获取单个指标的完整详情（代码、参数、描述等）。
 *
 * 从 quant_cli 的 indicators.detail 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface DetailParams {
  indicator_id: number;
}

export const indicatorDetailTool: ToolDefinition = {
  name: "indicator_detail",
  label: "指标详情",
  description:
    "获取单个指标的完整详情（代码、参数、描述等）。" +
    "需要提供 indicator_id（可通过 indicator_list 查询）。",

  parameters: Type.Object({
    indicator_id: Type.Integer({
      description: "指标ID（可通过 indicator_list 查询）",
      minimum: 1,
    }),
  }),

  execute: async (_toolCallId, rawParams: DetailParams) => {
    try {
      const result = await runQuantV2("indicators.detail", rawParams as unknown as Record<string, unknown>);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(result.data ?? result, null, 2),
        }],
        details: null,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `获取指标详情失败: ${errorMsg}`,
        }],
        details: null,
      };
    }
  },
};
