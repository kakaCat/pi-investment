/**
 * Strategy Status Tool — 查询策略运行状态
 *
 * 查询所有策略的运行状态，包括最近运行时间、信号数量等。
 *
 * 从 quant_cli 的 strategy.status 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

export const strategyStatusTool: ToolDefinition = {
  name: "strategy_status",
  label: "策略状态",
  description:
    "查询策略运行状态，返回各策略的最近运行时间、生成信号数量和运行状况。",

  parameters: Type.Object({}),

  execute: async (_toolCallId) => {
    try {
      const result = await runQuantV2("strategy.status", {});
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
          text: `查询策略状态失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
