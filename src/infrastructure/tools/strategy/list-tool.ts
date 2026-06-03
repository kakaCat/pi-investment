/**
 * Strategy List Tool — 列出所有策略
 *
 * 列出系统所有已注册策略，返回策略ID、名称、状态等信息。
 *
 * 从 quant_cli 的 strategy.list 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

export const strategyListTool: ToolDefinition = {
  name: "strategy_list",
  label: "列出策略",
  description:
    "列出系统所有已注册策略。返回每个策略的 ID、名称、类型和状态。" +
    "可用于查找 strategy_id 供其他策略工具使用。",

  parameters: Type.Object({}),

  execute: async (_toolCallId) => {
    try {
      const result = await runQuantV2("strategy.list", {});
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
          text: `列出策略失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
