/**
 * Indicator List Tool — 列出可用指标
 *
 * 列出系统可用的所有技术指标（自定义 + 系统内置），
 * 支持按 type 过滤和分页。
 *
 * 从 quant_cli 的 indicators.list 提取为独立工具。
 *
 * 🆕 集成统一响应处理系统：大列表自动持久化
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

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
    "可选按 type='my'|'system' 过滤，支持分页。" +
    "\n\n💾 大列表（>20条）自动保存到本地文件。",

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
      const data = (result as any).data ?? result;

      // 使用统一响应处理（大列表持久化）
      return handleToolResponse({
        toolName: 'indicator_list',
        data,
        formatter: _formatIndicatorList,
        metadata: {
          type: rawParams.type || 'all',
          page: rawParams.page || 1,
          pageSize: rawParams.pageSize || 20,
        },
        threshold: 15 * 1024, // 15KB，约对应20-30个指标
      });
    } catch (error) {
      return createErrorResponse(error);
    }
  },
};

/**
 * 格式化指标列表
 */
function _formatIndicatorList(data: any): string {
  if (!data || !Array.isArray(data.indicators)) {
    return JSON.stringify(data, null, 2);
  }

  const lines: string[] = [];
  lines.push(`📋 指标列表 (共 ${data.total || data.indicators.length} 个)`);

  if ((data as any).page) {
    lines.push(`页码: ${data.page}/${data.totalPages || '?'}`);
  }

  lines.push('');

  data.indicators.forEach((indicator: any, index: number) => {
    lines.push(`${index + 1}. ${indicator.name || indicator.indicator_name || 'N/A'}`);
    lines.push(`   ID: ${indicator.id || indicator.indicator_id || 'N/A'}`);
    if (indicator.description) {
      lines.push(`   说明: ${indicator.description}`);
    }
    if (indicator.type) {
      lines.push(`   类型: ${indicator.type}`);
    }
    lines.push('');
  });

  return lines.join('\n');
}
