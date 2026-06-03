/**
 * Indicator Delete Tool — 删除指标
 *
 * 软删除指定指标。
 *
 * 从 quant_cli 的 indicators.delete 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface DeleteParams {
  indicator_id: number;
}

export const indicatorDeleteTool: ToolDefinition = {
  name: "indicator_delete",
  label: "删除指标",
  description:
    "软删除指定指标。删除后可恢复。" +
    "需要提供 indicator_id。",

  parameters: Type.Object({
    indicator_id: Type.Integer({
      description: "指标ID",
      minimum: 1,
    }),
  }),

  execute: async (_toolCallId, rawParams: DeleteParams) => {
    try {
      const result = await runQuantV2("indicators.delete", rawParams as unknown as Record<string, unknown>);
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
          text: `删除指标失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
