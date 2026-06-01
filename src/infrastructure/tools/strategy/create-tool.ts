/**
 * Strategy Create Tool — 创建新策略
 *
 * 创建新的交易策略，提供策略名称和代码。
 * 创建后可用 strategy_execute 或 indicator_backtest 验证。
 *
 * 从 quant_cli 的 strategy.create 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

interface CreateParams {
  name: string;
  code: string;
  description?: string;
  category?: string;
}

export const strategyCreateTool: ToolDefinition = {
  name: "strategy_create",
  label: "创建策略",
  description:
    "创建新的交易策略。需要提供策略名称和 Python 策略代码。" +
    "代码需包含 calc_indicator(ctx) 函数，返回包含 'buy'/'sell' 列的 DataFrame。" +
    "\n\n创建后可用 strategy_execute 或 indicator_backtest 验证效果。" +
    "\n\n如果只需要编写 indicator 类型策略代码，也可使用 strategy_write 工具。",

  parameters: Type.Object({
    name: Type.String({
      description: "策略名称",
    }),
    code: Type.String({
      description:
        "策略代码（Python）。需包含 calc_indicator(ctx) 函数，" +
        "通过 ctx.kline_df 获取K线，返回包含 'buy'/'sell' 列的 DataFrame。",
    }),
    description: Type.Optional(
      Type.String({
        description: "策略描述（可选）",
      })
    ),
    category: Type.Optional(
      Type.String({
        description: "分类标签（可选，默认 'custom'）",
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: CreateParams) => {
    try {
      const result = await runQuantV2("strategy.create", rawParams as unknown as Record<string, unknown>);
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
          text: `创建策略失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
