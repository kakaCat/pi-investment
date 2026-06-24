/**
 * Indicator Update Tool — 更新指标
 *
 * 更新已有指标（代码、参数、名称、描述等）。
 *
 * 从 quant_cli 的 indicators.update 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface UpdateParams {
  indicator_id: number;
  code?: string;
  params?: Record<string, unknown>;
  name?: string;
  description?: string;
  is_public?: boolean;
  category?: string;
  is_active?: boolean;
  notebook?: Record<string, unknown>;
  strategy_profile?: Record<string, unknown>;
}

export const indicatorUpdateTool: ToolDefinition = {
  name: "indicator_update",
  label: "更新指标",
  description:
    "更新已有指标（代码、参数、名称、描述等）。" +
    "需要提供 indicator_id，其余字段可选更新。",

  parameters: Type.Object({
    indicator_id: Type.Integer({
      description: "指标ID",
      minimum: 1,
    }),
    code: Type.Optional(
      Type.String({
        description: "Python 策略代码",
      })
    ),
    params: Type.Optional(
      Type.Record(Type.String(), Type.Unknown(), {
        description: "指标参数（键值对）",
      })
    ),
    name: Type.Optional(
      Type.String({
        description: "指标名称",
      })
    ),
    description: Type.Optional(
      Type.String({
        description: "指标描述",
      })
    ),
    is_public: Type.Optional(
      Type.Boolean({
        description: "是否公开",
      })
    ),
    category: Type.Optional(
      Type.String({
        description: "指标分类",
      })
    ),
    is_active: Type.Optional(
      Type.Boolean({
        description: "是否启用",
      })
    ),
    notebook: Type.Optional(
      Type.Record(Type.String(), Type.Unknown(), {
        description: "Notebook 内容",
      })
    ),
    strategy_profile: Type.Optional(
      Type.Record(Type.String(), Type.Unknown(), {
        description: "策略画像 — 结构化元数据，记录策略的市场环境、风险特征、适用场景等。支持部分更新(merge)。\n" +
          "推荐字段：strategy_type(mean_reversion|trend_following|breakout|momentum|hybrid), " +
          "description(简述), timeframe(daily|weekly), market_condition([bull|bear|range]), " +
          "risk_level(low|medium|high), max_holding_days, stop_loss_pct, take_profit_pct, " +
          "indicators_used, tags, created_for",
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: UpdateParams) => {
    try {
      const result = await runQuantV2("indicators.update", rawParams as unknown as Record<string, unknown>);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify((result as any).data ?? result, null, 2),
        }],
        details: null,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `更新指标失败: ${errorMsg}`,
        }],
        details: null,
      };
    }
  },
};
