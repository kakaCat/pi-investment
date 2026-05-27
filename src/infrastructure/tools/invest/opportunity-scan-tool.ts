/**
 * V2 机会雷达工具
 *
 * 基于 quantsys-v2 的多维评分引擎，批量扫描股票池找出交易机会。
 * 覆盖技术面（RSI/MACD/布林带）+ 基本面（PE/ROE）+ 资金面三维评分。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { scanOpportunities } from "../../../infrastructure/quant/quant-v2-client.js";
import { formatOpportunities } from "../../../infrastructure/quant/formatters.js";

export const opportunityScanTool: ToolDefinition = {
  name: "opportunity_scan",
  label: "机会雷达",
  description:
    "机会雷达扫描：对指定股票池进行三维评分（技术面50% + 基本面30% + 资金面20%），\n" +
    "输出综合评分 + 风险等级（low/medium/high）+ 信号理由。\n" +
    "支持筛选条件：RSI超卖、MACD金叉、PE合理区间、ROE门槛等。\n" +
    "适用于：市场扫描找机会、多股对比选优、策略信号确认。",
  parameters: Type.Object({
    symbols: Type.Optional(Type.Array(Type.String(), {
      description: "要扫描的股票代码列表，如 ['600519', '000001']。留空=扫描全市场。",
    })),
    conditions: Type.Optional(Type.Array(Type.String(), {
      description: "筛选条件列表，如 ['rsi_oversold', 'macd_golden_cross', 'pe_lt_20', 'roe_gt_15']",
    })),
    limit: Type.Optional(Type.Number({ description: "返回前N个结果（默认20）" })),
  }),
  execute: async (_toolCallId: string, rawParams: any) => {
    try {
      const params: Record<string, unknown> = {};
      if (rawParams?.symbols && Array.isArray(rawParams.symbols)) {
        params.symbols = rawParams.symbols;
      }
      if (rawParams?.conditions && Array.isArray(rawParams.conditions)) {
        params.conditions = rawParams.conditions;
      }
      if (rawParams?.limit !== undefined) {
        params.limit = rawParams.limit;
      }

      const opportunities = await scanOpportunities(params);
      const formattedText = formatOpportunities(opportunities);

      return {
        content: [
          {
            type: "text" as const,
            text: formattedText,
          },
        ],
        details: undefined,
      };
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `机会雷达扫描失败: ${error instanceof Error ? error.message : String(error)}`,
          },
        ],
        details: undefined,
      };
    }
  },
};
