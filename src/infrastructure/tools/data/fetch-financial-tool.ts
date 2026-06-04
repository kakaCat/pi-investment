/**
 * 财务数据获取工具 - L1 数据管道层（增强版）
 *
 * 统一的财务数据查询工具，支持：
 * - 原始财务报表（利润表、资产负债表、现金流量表）
 * - 财务指标（ROE、净利润、营收增长率等）
 * - 估值指标（PE、PB、PS、PEG）
 * - PE 历史分位数
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { requireAshare } from "../shared/validators.js";
import { getFinancials, runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { formatFinancialData } from "../../adapters/quant/formatters.js";
import { handleToolResponse } from "../utils/index.js";

export const dataFetchFinancialTool: ToolDefinition = {
  name: "data_fetch_financial",
  label: "获取财务数据",
  description:
    "L1 数据管道工具：统一的财务数据查询入口。" +
    "支持获取：(1) 原始财务报表（利润表、资产负债表、现金流量表）" +
    "(2) 财务指标（ROE、净利润等）" +
    "(3) 估值指标（PE、PB等）" +
    "(4) PE历史分位数。" +
    "智能容错：某个数据源失败时不影响其他数据。" +
    "仅支持A股（6位数字代码）。" +
    "缓存控制：通过source参数控制缓存策略（auto=缓存优先，fresh=强制刷新，cache_only=仅缓存）。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）"
    }),
    dataType: Type.Optional(Type.Union([
      Type.Literal("statements"),
      Type.Literal("indicators"),
      Type.Literal("valuation"),
      Type.Literal("pe_percentile"),
      Type.Literal("all")
    ], {
      description: "数据类型：statements=财务报表, indicators=财务指标, valuation=估值指标, pe_percentile=PE分位数, all=全部数据。默认: statements"
    })),
    reportType: Type.Optional(Type.Union([
      Type.Literal("income"),
      Type.Literal("balance"),
      Type.Literal("cashflow"),
      Type.Literal("all")
    ], {
      description: "报表类型（仅dataType=statements时生效）：income=利润表, balance=资产负债表, cashflow=现金流量表, all=全部。默认: all"
    })),
    periods: Type.Optional(Type.Integer({
      description: "报表期数（默认4期）",
      minimum: 1,
      maximum: 20
    })),
    years: Type.Optional(Type.Integer({
      description: "PE分位数年限（默认3年）",
      minimum: 1,
      maximum: 10
    }),
    source: Type.Optional(Type.Union([
      Type.Literal("auto"),
      Type.Literal("fresh"),
      Type.Literal("cache_only")
    ], {
      description: "数据源策略：auto=缓存优先（默认），fresh=强制刷新，cache_only=仅缓存"
    }))
    source?: "auto" | "fresh" | "cache_only";
    }))
  }),

  execute: async (_toolCallId, params: {
    symbol: string;
    dataType?: string;
    reportType?: string;
    periods?: number;
    years?: number;
    source?: "auto" | "fresh" | "cache_only";
  }) => {
    const { symbol, dataType = 'statements', reportType = 'all', periods = 4, years = 3, source = 'auto' } = params;

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

    try {
      const results: string[] = [];
      let hasError = false;

      // 1. 财务报表数据
      if (dataType === 'statements' || dataType === 'all') {
        try {
          const mappedReportType = reportType === 'cashflow' ? 'cash_flow' : reportType;
          const data = await getFinancials(
            symbol,
            mappedReportType as 'income' | 'balance' | 'cash_flow' | 'all' | undefined,
            periods
            ,source
          );
          results.push(formatFinancialData(data));
        } catch (error) {
          hasError = true;
          results.push(`【财务报表】\n⚠️ 暂时不可用: ${error instanceof Error ? error.message : String(error)}`);
        }
      }

      // 2. 财务指标
      if (dataType === 'indicators' || dataType === 'all') {
        try {
          const response = await runQuantV2('financial.indicators', { symbol });
          if (typeof response === 'string') {
            results.push(`\n【财务指标】\n${response}`);
          } else if (response && typeof response === 'object') {
            results.push(`\n【财务指标】\n${JSON.stringify(response, null, 2)}`);
          }
        } catch (error) {
          hasError = true;
          results.push(`\n【财务指标】\n⚠️ 暂时不可用: ${error instanceof Error ? error.message : String(error)}\n💡 提示：可从上方财务报表数据中手动提取`);
        }
      }

      // 3. 估值指标
      if (dataType === 'valuation' || dataType === 'all') {
        try {
          const response = await runQuantV2('financial.valuation', { symbol });
          if (typeof response === 'string') {
            results.push(`\n【估值指标】\n${response}`);
          } else if (response && typeof response === 'object') {
            results.push(`\n【估值指标】\n${JSON.stringify(response, null, 2)}`);
          }
        } catch (error) {
          hasError = true;
          results.push(`\n【估值指标】\n⚠️ 暂时不可用: ${error instanceof Error ? error.message : String(error)}`);
        }
      }

      // 4. PE 分位数
      if (dataType === 'pe_percentile' || dataType === 'all') {
        try {
          const response = await runQuantV2('financial.pe_percentile', { symbol, years });
          if (typeof response === 'string') {
            results.push(`\n【PE 历史分位数】\n${response}`);
          } else if (response && typeof response === 'object') {
            const data = response as any;
            if (data.success && data.data) {
              const pe = data.data;
              results.push(
                `\n【PE 历史分位数】（${years}年数据）\n` +
                `  当前价格: ${pe.currentPrice} 元\n` +
                `  当前 PE: ${pe.currentPe}\n` +
                `  历史分位数: ${pe.percentile}%\n` +
                `  估值判断: ${pe.interpretation}\n` +
                `  ${years}年区间: ${pe.minPe} - ${pe.maxPe}\n` +
                `  平均 PE: ${pe.meanPe}\n` +
                `  中位数 PE: ${pe.medianPe}\n` +
                `  数据点数: ${pe.dataPoints}`
              );
            } else {
              results.push(`\n【PE 历史分位数】\n${JSON.stringify(response, null, 2)}`);
            }
          }
        } catch (error) {
          hasError = true;
          results.push(`\n【PE 历史分位数】\n⚠️ 暂时不可用: ${error instanceof Error ? error.message : String(error)}`);
        }
      }

      // 检查是否至少有一个数据源成功
      if (results.length === 0 || (hasError && results.every(r => r.includes('⚠️')))) {
        throw new Error('所有财务数据源均不可用，请稍后重试');
      }

      // 使用统一响应处理（大数据自动持久化）
      const combinedText = results.join('\n');
      return handleToolResponse({
        toolName: 'data_fetch_financial',
        data: { rawText: combinedText, symbol, dataType, hasPartialErrors: hasError },
        formatter: (data) => data.rawText,
        metadata: { symbol, dataType, reportType, periods, years },
        threshold: 30 * 1024, // 30KB
      });
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `财务数据获取失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
};
