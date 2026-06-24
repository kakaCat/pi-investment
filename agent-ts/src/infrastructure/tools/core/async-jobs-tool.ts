/**
 * Async Jobs Tool - 异步任务管理工具
 *
 * 从 quant_cli 拆分出来，专注于异步任务管理业务
 * 查询异步任务列表和状态
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

export const asyncJobsTool: ToolDefinition = {
  name: "async_jobs",
  label: "异步任务管理",
  description: "查询异步任务列表和状态，用于监控长时间运行的回测、训练等任务",
  parameters: Type.Object({
    status: Type.Optional(Type.Union([
      Type.Literal("pending"),
      Type.Literal("running"),
      Type.Literal("completed"),
      Type.Literal("failed")
    ], {
      description: "按状态筛选任务"
    })),
    limit: Type.Optional(Type.Integer({
      description: "返回结果数量限制",
      default: 20,
      minimum: 1
    }))
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const response = await runQuantV2("jobs", "list", params);
      return handleToolResponse({
        toolName: 'async_jobs',
        data: response,
        formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
        metadata: { params }
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `查询异步任务失败: ${errorMsg}`
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
