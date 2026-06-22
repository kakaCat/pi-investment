/**
 * Sector Analysis Tool - 行业分析工具
 *
 * 从 quant_cli 拆分出来，专注于行业分析业务
 * 按行业或板块聚合估值、质量、负债率和信号数量
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

export const sectorAnalysisTool: ToolDefinition = {
  name: "sector_analysis",
  label: "行业分析",
  description: "按行业或板块聚合估值、质量、负债率和信号数量，用于行业轮动和板块比较分析",
  parameters: Type.Object({
    sector_field: Type.Optional(Type.Union([
      Type.Literal("sector"),
      Type.Literal("industry")
    ], {
      description: "聚合维度：sector=一级行业，industry=二级行业",
      default: "sector"
    })),
    limit: Type.Optional(Type.Integer({
      description: "返回结果数量限制",
      default: 20,
      minimum: 1
    }))
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const response = await runQuantV2("sector", "aggregate", params);
      return handleToolResponse({
        toolName: 'sector_analysis',
        data: response,
        formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
        metadata: { params }
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `行业分析失败: ${errorMsg}`
        }],
        details: {
          success: false,
          error: errorMsg,
          params
        }
      };
    }
  }
};
