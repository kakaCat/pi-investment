/**
 * Daily Report Tool - 日报管理工具
 *
 * 从 quant_cli 拆分出来，专注于日报管理业务
 * 生成或读取日度量化报告
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

export const dailyReportTool: ToolDefinition = {
  name: "daily_report",
  label: "日报管理",
  description: "生成或读取日度量化报告，包括持仓情况、收益分析、风险指标等",
  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("generate"),
      Type.Literal("read")
    ], {
      description: "操作类型：generate=生成日报，read=读取日报"
    }),
    date: Type.Optional(Type.String({
      description: "日期（格式：YYYY-MM-DD）。read 模式下默认为最新日期"
    })),
    output_dir: Type.Optional(Type.String({
      description: "输出目录（仅 generate 模式）"
    }))
  }),
  execute: async (_toolCallId: string, params: any) => {
    const { action, date, output_dir } = params;

    // 参数验证
    if (!action) {
      return {
        content: [{
          type: "text" as const,
          text: "缺少必填参数: action。请指定 'generate' 或 'read'"
        }],
        details: { success: false, error: "MISSING_ACTION" }
      };
    }

    try {
      let response;
      if (action === "generate") {
        response = await runQuantV2("report.daily", { output_dir });
      } else {
        response = await runQuantV2("report.read-daily", { date });
      }
      return handleToolResponse({
        toolName: 'daily_report',
        data: response,
        formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
        metadata: { action, date, output_dir }
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `日报${action === "generate" ? "生成" : "读取"}失败: ${errorMsg}`
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
