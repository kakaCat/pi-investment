/**
 * Indicator List Tool — 列出可用指标
 *
 * 列出系统可用的所有技术指标（自定义 + 系统内置），
 * 支持按 type 过滤和分页。
 *
 * 从 quant_cli 的 indicators.list 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

interface ListParams {
  type?: "my" | "system";
  page?: number;
  pageSize?: number;
}

export const indicatorListTool: ToolDefinition = {
  name: "indicator_list",
  label: "列出指标",
  description:
    "列出系统可用的所有技术指标（自定义 + 系统内置）。" +
    "可选按 type='my'|'system' 过滤，支持分页。",

  parameters: Type.Object({
    type: Type.Optional(
      Type.Union([Type.Literal("my"), Type.Literal("system")], {
        description: "过滤指标类型：'my'=自定义, 'system'=系统内置",
      })
    ),
    page: Type.Optional(
      Type.Integer({
        description: "页码（从 1 开始）",
        minimum: 1,
      })
    ),
    pageSize: Type.Optional(
      Type.Integer({
        description: "每页数量（默认 20，最大 100）",
        minimum: 1,
        maximum: 100,
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: ListParams) => {
    try {
      const result = await runQuantV2("indicators.list", rawParams as Record<string, unknown>);
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
          text: `列出指标失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
