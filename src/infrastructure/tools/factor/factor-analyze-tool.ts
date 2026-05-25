/**
 * Factor Analyze Tool - L2 因子工厂层（v2 版本）
 *
 * 分析因子的 IC、覆盖率、稳定性、衰减曲线等指标
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { analyzeFactors } from "../../quant/quant-v2-client.js";
import { formatFactorAnalysis } from "../../quant/formatters.js";

interface FactorAnalyzeParams {
  factors: string[];
  start_date: string;
  end_date: string;
  universe?: string[];
}

export const factorAnalyzeTool: ToolDefinition = {
  name: "factor_analyze",
  label: "因子分析",
  description:
    "L2 因子工厂工具：分析因子的有效性和稳定性。" +
    "计算因子的 IC（信息系数）、覆盖率、稳定性、衰减曲线等指标。" +
    "支持日度、周度、月度 IC 分析。" +
    "可指定股票池范围进行分析。",

  parameters: Type.Object({
    factors: Type.Array(
      Type.String(),
      {
        description: "要分析的因子列表（如 ['rsi', 'macd', 'roe']）"
      }
    ),
    start_date: Type.String({
      description: "开始日期，格式 YYYY-MM-DD（如 2024-01-01）"
    }),
    end_date: Type.String({
      description: "结束日期，格式 YYYY-MM-DD（如 2024-12-31）"
    }),
    universe: Type.Optional(
      Type.Array(
        Type.String(),
        {
          description: "股票池范围（可选），A股6位代码列表（如 ['600519', '000858']）"
        }
      )
    )
  }),

  execute: async (_toolCallId, params: FactorAnalyzeParams) => {
    const { factors, start_date, end_date, universe } = params;

    try {
      // 调用 v2 API 分析因子
      const result = await analyzeFactors({
        factors,
        start_date,
        end_date,
        universe
      });

      if (!result.success) {
        return {
          content: [{
            type: "text" as const,
            text: `因子分析失败: ${result.error || "未知错误"}`
          }],
          details: undefined
        };
      }

      // 使用格式化工具将结果转换为可读文本
      const formattedText = formatFactorAnalysis(result);

      return {
        content: [{
          type: "text" as const,
          text: formattedText
        }],
        details: undefined
      };
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `因子分析失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
};
