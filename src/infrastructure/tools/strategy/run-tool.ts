/**
 * Strategy Run Tool — 实时运行策略
 *
 * 实时运行策略生成信号，支持指定股票列表。
 *
 * 从 quant_cli 的 strategy.run 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

interface RunParams {
  strategy_id: string;
  symbols?: string[];
}

export const strategyRunTool: ToolDefinition = {
  name: "strategy_run",
  label: "运行策略",
  description:
    "实时运行策略生成信号。指定 strategy_id（可通过 strategy_list 查询），" +
    "可选指定股票列表。返回策略执行结果和生成的信号。",

  parameters: Type.Object({
    strategy_id: Type.String({
      description: "策略ID（可通过 strategy_list 查询）",
    }),
    symbols: Type.Optional(
      Type.Array(Type.String(), {
        description: "股票代码列表（如 [\"600000\", \"000001\"]），不传则使用策略默认股票池",
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: RunParams) => {
    try {
      const result = await runQuantV2("strategy.run", rawParams as unknown as Record<string, unknown>);
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
          text: `运行策略失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
