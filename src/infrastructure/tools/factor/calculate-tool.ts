/**
 * Factor Calculate Tool - L2 因子工厂层
 *
 * 批量计算多个因子，支持技术指标、估值、质量评分、PE分位数、走势分析
 * 整合自 analyze_technical, get_valuation, get_quality_score, get_pe_percentile, analyze_price_action
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { requireAshare } from "../shared/validators.js";
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

// Constants
const DEFAULT_FACTORS = ["technical", "valuation", "quality"] as const;
const VALID_FACTORS = ["technical", "valuation", "quality", "pe_percentile", "price_action"] as const;

type FactorType = typeof VALID_FACTORS[number];

interface FactorCalculateParams {
  symbol: string;
  factors?: FactorType[];
}

interface ErrorResponse {
  success: false;
  error: string;
  invalid_format?: boolean;
  unsupported_for_hk?: boolean;
}

interface FactorResult {
  [key: string]: any;
}

/**
 * 因子计算路由映射
 */
const FACTOR_ROUTES: Record<FactorType, { method: string; params: (symbol: string) => Record<string, any> }> = {
  technical: {
    method: "calculate_technical_indicators",
    params: (symbol) => ({ symbol })
  },
  valuation: {
    method: "get_stock_valuation",
    params: (symbol) => ({ symbol })
  },
  quality: {
    method: "get_quality_score",
    params: (symbol) => ({ symbol, framework: "auto" })
  },
  pe_percentile: {
    method: "get_pe_percentile",
    params: (symbol) => ({ symbol, years: 3 })
  },
  price_action: {
    method: "analyze_price_action",
    params: (symbol) => ({ symbol, period: 60 })
  }
};

export const factorCalculateTool: ToolDefinition = {
  name: "factor_calculate",
  label: "计算因子",
  description:
    "L2 因子工厂工具：批量计算多个因子。" +
    "支持的因子类型：" +
    "1. 'technical' - 技术指标（MA, MACD, RSI, Bollinger）" +
    "2. 'valuation' - 估值分析（PE, PB, Graham fair value）" +
    "3. 'quality' - 基本面质量评分（0-100分）" +
    "4. 'pe_percentile' - PE历史分位数（近3年）" +
    "5. 'price_action' - 走势深度分析（近60日）" +
    `默认计算: ${DEFAULT_FACTORS.join(", ")}。` +
    "仅支持A股（6位数字代码）。" +
    "并行获取多个因子，部分失败时其他因子仍返回。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）"
    }),
    factors: Type.Optional(
      Type.Array(
        Type.Union([
          Type.Literal("technical"),
          Type.Literal("valuation"),
          Type.Literal("quality"),
          Type.Literal("pe_percentile"),
          Type.Literal("price_action")
        ]),
        {
          description: `要计算的因子列表。默认: ${JSON.stringify(DEFAULT_FACTORS)}`
        }
      )
    )
  }),

  execute: async (_toolCallId, params: FactorCalculateParams) => {
    const { symbol, factors = [...DEFAULT_FACTORS] } = params;

    // 验证A股代码
    const validationError = requireAshare(symbol);
    if (validationError) {
      return {
        content: [{
          type: "text" as const,
          text: validationError
        }],
        details: undefined
      };
    }

    // 并行获取所有因子
    const factorPromises = factors.map(async (factor) => {
      try {
        const route = FACTOR_ROUTES[factor];
        const result = await callQuantSysDaemon(route.method, route.params(symbol));
        return { factor, data: JSON.parse(result), error: null };
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return { factor, data: null, error: errorMsg };
      }
    });

    const results = await Promise.all(factorPromises);

    // 构建响应
    const response: FactorResult = {
      success: true,
      symbol,
      factors: {}
    };

    let hasAnySuccess = false;
    for (const result of results) {
      if (result.error) {
        response.factors[result.factor] = null;
        response.factors[`${result.factor}_error`] = result.error;
      } else {
        response.factors[result.factor] = result.data;
        hasAnySuccess = true;
      }
    }

    // 如果所有因子都失败，标记为失败
    if (!hasAnySuccess) {
      const errorResponse: ErrorResponse = {
        success: false,
        error: "所有因子计算失败"
      };

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(errorResponse)
        }],
        details: undefined
      };
    }

    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify(response, null, 2)
      }],
      details: undefined
    };
  }
};
