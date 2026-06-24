/**
 * Training Reports Tool - 训练报告工具
 *
 * 从 quant_cli 拆分出来，专注于训练报告查询业务
 * 查询模型训练报告列表
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

export const trainingReportsTool: ToolDefinition = {
  name: "training_reports",
  label: "训练报告",
  description: "查询模型训练报告列表，包括训练时间、模型类型、性能指标等",
  parameters: Type.Object({
    model_type: Type.Optional(Type.String({
      description: "按模型类型筛选"
    })),
    limit: Type.Optional(Type.Integer({
      description: "返回结果数量限制",
      default: 20,
      minimum: 1
    }))
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const response = await runQuantV2("training", "reports", params);
      return handleToolResponse({
        toolName: 'training_reports',
        data: response,
        formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
        metadata: { params }
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `查询训练报告失败: ${errorMsg}`
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
