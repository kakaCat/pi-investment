/**
 * Indicator Create Tool — 创建自定义指标
 *
 * 创建新的自定义指标，需要 name 和 code（Python 策略代码）。
 *
 * 从 quant_cli 的 indicators.create 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface CreateParams {
  name: string;
  code: string;
  params?: Record<string, unknown>;
  description?: string;
  category?: string;
  is_public?: boolean;
}

export const indicatorCreateTool: ToolDefinition = {
  name: "indicator_create",
  label: "创建指标",
  description:
    "创建新的自定义指标。需要 name 和 code（Python 策略代码）。" +
    "可选设置参数、描述、分类、是否公开。",

  parameters: Type.Object({
    name: Type.String({
      description: "指标名称",
    }),
    code: Type.String({
      description: "Python 策略代码（def run(df): ...）",
    }),
    params: Type.Optional(
      Type.Record(Type.String(), Type.Unknown(), {
        description: "指标参数（键值对）",
      })
    ),
    description: Type.Optional(
      Type.String({
        description: "指标描述",
      })
    ),
    category: Type.Optional(
      Type.String({
        description: "指标分类",
      })
    ),
    is_public: Type.Optional(
      Type.Boolean({
        description: "是否公开（默认 false）",
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: CreateParams) => {
    try {
      const result = await runQuantV2("indicators.create", rawParams as unknown as Record<string, unknown>);
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
          text: `创建指标失败: ${errorMsg}`,
        }],
        details: null,
      };
    }
  },
};
