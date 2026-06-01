/**
 * Strategy Detail Tool — 查询策略详情
 *
 * 查询单个策略的详细信息，包括参数、代码、回测结果等。
 *
 * 从 quant_cli 的 strategy.get 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

interface DetailParams {
  strategy_id: string;
}

export const strategyDetailTool: ToolDefinition = {
  name: "strategy_detail",
  label: "策略详情",
  description:
    "查询单个策略的详细信息，包括策略参数、代码和配置。" +
    "需提供 strategy_id（可通过 strategy_list 查询）。",

  parameters: Type.Object({
    strategy_id: Type.String({
      description: "策略ID（可通过 strategy_list 查询）",
    }),
  }),

  execute: async (_toolCallId, rawParams: DetailParams) => {
    try {
      const result = await runQuantV2("strategy.get", rawParams as unknown as Record<string, unknown>);
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
          text: `查询策略详情失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
