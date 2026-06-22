/**
 * Screening Tool - 股票筛选工具
 *
 * 从 quant_cli 拆分出来，专注于股票筛选业务
 * 支持按行业筛选和质量评分筛选
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

export const screeningTool: ToolDefinition = {
  name: "screening",
  label: "股票筛选",
  description: "按行业板块或质量评分筛选股票。支持 ROE、PE 和返回数量过滤",
  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("sector"),
      Type.Literal("quality")
    ], {
      description: "筛选类型：sector=按行业筛选，quality=按质量评分筛选"
    }),
    sector: Type.String({
      description: "行业板块名称，例如：白酒、医药、新能源等"
    }),
    min_roe: Type.Optional(Type.Number({
      description: "最小 ROE（净资产收益率），单位：%"
    })),
    max_pe: Type.Optional(Type.Number({
      description: "最大 PE（市盈率）",
      minimum: 0
    })),
    min_score: Type.Optional(Type.Integer({
      description: "最小质量评分（仅 quality 模式），范围 0-100",
      minimum: 0,
      maximum: 100
    })),
    limit: Type.Optional(Type.Integer({
      description: "返回结果数量限制",
      default: 20,
      minimum: 1
    }))
  }),
  execute: async (_toolCallId, params: any) => {
    const { action, ...restParams } = params;

    // 参数验证
    if (!action) {
      return {
        content: [{
          type: "text" as const,
          text: "缺少必填参数: action。请指定 'sector' 或 'quality'"
        }],
        details: { success: false, error: "MISSING_ACTION" }
      };
    }

    if (!restParams.sector) {
      return {
        content: [{
          type: "text" as const,
          text: "缺少必填参数: sector。请指定行业板块名称"
        }],
        details: { success: false, error: "MISSING_SECTOR" }
      };
    }

    // quality 模式需要 min_score 参数
    if (action === "quality" && restParams.min_score === undefined) {
      restParams.min_score = 65; // 默认最小评分
    }

    try {
      const response = await runQuantV2("screening", action, restParams);
      return handleToolResponse({
        toolName: 'screening',
        data: response,
        formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
        metadata: { action, ...restParams }
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `股票筛选失败: ${errorMsg}`
        }],
        details: {
          success: false,
          error: errorMsg,
          params: { action, ...restParams }
        }
      };
    }
  }
};
