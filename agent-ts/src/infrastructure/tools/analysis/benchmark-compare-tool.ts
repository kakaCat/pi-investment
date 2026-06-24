/**
 * Benchmark Compare Tool - 基准比较工具
 *
 * 从 quant_cli 拆分出来，专注于基准比较业务
 * 比较策略收益与基准收益，计算 alpha 和相对表现
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

export const benchmarkCompareTool: ToolDefinition = {
  name: "benchmark_compare",
  label: "基准比较",
  description: "比较策略收益与基准收益（如沪深300、中证500），计算 alpha、beta 和相对表现",
  parameters: Type.Object({
    strategy_return: Type.Number({
      description: "策略收益率（小数形式，如 0.12 表示 12%）"
    }),
    benchmark_return: Type.Number({
      description: "基准收益率（小数形式，如 0.08 表示 8%）"
    }),
    strategy_name: Type.Optional(Type.String({
      description: "策略名称"
    })),
    benchmark_name: Type.Optional(Type.String({
      description: "基准名称（如：沪深300、中证500）"
    })),
    equity: Type.Optional(Type.String({
      description: "策略对应的股票代码"
    })),
    benchmark: Type.Optional(Type.String({
      description: "基准对应的指数代码"
    }))
  }),
  execute: async (_toolCallId: string, params: any) => {
    // 参数验证
    if (params.strategy_return === undefined) {
      return {
        content: [{
          type: "text" as const,
          text: "缺少必填参数: strategy_return"
        }],
        details: { success: false, error: "MISSING_STRATEGY_RETURN" }
      };
    }

    if (params.benchmark_return === undefined) {
      return {
        content: [{
          type: "text" as const,
          text: "缺少必填参数: benchmark_return"
        }],
        details: { success: false, error: "MISSING_BENCHMARK_RETURN" }
      };
    }

    try {
      const response = await runQuantV2("benchmark", "compare", params);
      return handleToolResponse({
        toolName: 'benchmark_compare',
        data: response,
        formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
        metadata: { params }
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `基准比较失败: ${errorMsg}`
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
