/**
 * Factor Calculate Tool - L2 因子工厂层（v2 版本）
 *
 * 批量计算多个因子，支持技术指标和基本面因子
 *
 * 🆕 集成统一响应处理系统：大批量因子数据自动持久化
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { requireAshare } from "../shared/validators.js";
import { computeFactors } from "../../adapters/quant/quant-v2-client.js";
import { formatFactorResult } from "../../adapters/quant/formatters.js";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

interface FactorCalculateParams {
  symbol: string;
  factors?: string[];
}

export const factorCalculateTool: ToolDefinition = {
  name: "factor_calculate",
  label: "计算因子",
  description:
    "L2 因子工厂工具：批量计算多个因子。" +
    "支持技术因子（RSI, MACD, KDJ, 布林带等）和基本面因子（ROE, 毛利率, 净利率等）。" +
    "默认计算所有可用因子。" +
    "仅支持A股（6位数字代码）。" +
    "\n\n💾 大批量因子数据自动保存到本地文件。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）"
    }),
    factors: Type.Optional(
      Type.Array(
        Type.String(),
        {
          description: "要计算的因子列表（可选）。留空则计算所有因子"
        }
      )
    )
  }),

  execute: async (_toolCallId, params: FactorCalculateParams) => {
    const { symbol, factors } = params;

    // 验证A股代码
    const validationError = requireAshare(symbol);
    if (validationError) {
      return {
        content: [{
          type: "text" as const,
          text: validationError
        }],
        details: null
      };
    }

    try {
      // 调用 v2 API 计算因子
      const result = await computeFactors({
        symbols: [symbol],
        factors: factors || undefined
      });

      // 使用统一响应处理（自动决定格式化或持久化）
      return handleToolResponse({
        toolName: 'factor_calculate',
        data: result,
        formatter: formatFactorResult,
        metadata: {
          symbol,
          factor_count: factors?.length || 'all',
        },
        threshold: 40 * 1024, // 40KB，多因子计算可能较大
      });
    } catch (error) {
      return createErrorResponse(error);
    }
  }
};
