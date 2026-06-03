/**
 * Strategy Write Tool — 策略编写
 *
 * 创建或更新交易策略代码（indicator 类型），是"写→测→迭代"工作流的第一步。
 * - 不提供 indicator_id → 创建新策略，返回 strategy_id
 * - 提供 indicator_id → 更新已有策略代码
 *
 * 创建后可用 indicator_backtest 立即回测验证。
 *
 * 从 quant_cli 的 indicators.create / indicators.update 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { createIndicator, updateIndicator } from "../../adapters/quant/quant-v2-client.js";

// ── 参数类型 ─

interface StrategyWriteParams {
  name?: string;
  code: string;
  indicator_id?: number;
  description?: string;
  category?: string;
}

// ── 工具定义 ─

export const strategyWriteTool: ToolDefinition = {
  name: "strategy_write",
  label: "写策略",
  description:
    "创建或更新交易策略（indicator 类型）。" +
    "不提供 indicator_id = 创建新策略（需 name + code）；" +
    "提供 indicator_id = 更新已有策略代码。" +
    "\n\n策略代码格式：Python 函数式指标，需定义 my_indicator_name、calc_indicator(ctx) 函数，" +
    "并在返回的 DataFrame 中设置 df['buy'] 和 df['sell'] 列。" +
    "\n\n典型工作流：strategy_write → indicator_backtest → 调整参数 → strategy_write → indicator_backtest → ...",

  parameters: Type.Object({
    name: Type.Optional(
      Type.String({
        description: "策略名称（新建时必填，更新时可选）",
      })
    ),
    code: Type.String({
      description:
        "策略代码（Python）。需包含 calc_indicator(ctx) 函数，" +
        "通过 ctx.kline_df 获取K线，返回包含 'buy'/'sell' 列的 DataFrame。",
    }),
    indicator_id: Type.Optional(
      Type.Integer({
        description: "要更新的策略ID。不提供则创建新策略。",
        minimum: 1,
      })
    ),
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

  execute: async (_toolCallId, rawParams: StrategyWriteParams) => {
    const { name, code, indicator_id, description, category } = rawParams;

    try {
      if (indicator_id !== undefined) {
        // ── 更新已有策略 ──
        const result = await updateIndicator(indicator_id, {
          code,
          name,
          description,
          category,
        });

        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(
                {
                  action: "update",
                  indicator_id,
                  ...result,
                  hint: "已更新。用 indicator_backtest 验证新代码。",
                },
                null,
                2
              ),
            },
          ],
          details: undefined,
        };
      } else {
        // ── 创建新策略 ──
        if (!name) {
          return {
            content: [
              {
                type: "text" as const,
                text: "创建策略需要 name 参数。如需更新已有策略，请提供 indicator_id。",
              },
            ],
            details: undefined,
          };
        }

        const result = await createIndicator({
          name,
          code,
          description,
          category,
        });

        const strategyId = result.data?.strategy_id;
        const valid = result.data?.validation?.valid;
        const hasBuy = result.data?.validation?.has_buy_signal;
        const hasSell = result.data?.validation?.has_sell_signal;
        const validationError = result.data?.validation?.error;

        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(
                {
                  action: "create",
                  strategy_id: strategyId,
                  name,
                  valid,
                  has_buy_signal: hasBuy,
                  has_sell_signal: hasSell,
                  validation_error: validationError || null,
                  ...result,
                  hint: valid
                    ? "创建成功。用 indicator_backtest({ indicator_id: " +
                      strategyId +
                      ", ... }) 验证。"
                    : "代码验证失败，策略已保存但标记为无效。请修正后更新。",
                },
                null,
                2
              ),
            },
          ],
          details: undefined,
        };
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [
          {
            type: "text" as const,
            text: `策略写入失败: ${errorMsg}`,
          },
        ],
        details: undefined,
      };
    }
  },
};
