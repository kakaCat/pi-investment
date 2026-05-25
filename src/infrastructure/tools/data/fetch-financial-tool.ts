/**
 * 财务数据获取工具 - L1 数据管道层
 *
 * 获取利润表、资产负债表、现金流量表
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { requireAshare } from "../shared/validators.js";
import { getFinancials } from "../../quant/quant-v2-client.js";
import { formatFinancialData } from "../../quant/formatters.js";

export const dataFetchFinancialTool: ToolDefinition = {
  name: "data_fetch_financial",
  label: "获取财务数据",
  description:
    "L1 数据管道工具：获取股票的财务数据（利润表、资产负债表、现金流量表）。" +
    "返回最近4个季度的财务报表数据，包括营收、净利润、资产负债率、现金流等关键指标。" +
    "仅支持A股（6位数字代码）。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）"
    }),
    reportType: Type.Optional(
      Type.Union([
        Type.Literal("income"),
        Type.Literal("balance"),
        Type.Literal("cashflow"),
        Type.Literal("all")
      ]),
      {
        description: "报表类型：income=利润表, balance=资产负债表, cashflow=现金流量表, all=全部（默认）"
      }
    )
  }),

  execute: async (_toolCallId, params: { symbol: string; reportType?: string }) => {
    const { symbol, reportType } = params;

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
      // Map "cashflow" to "cash_flow" for v2 API
      const mappedReportType = reportType === 'cashflow' ? 'cash_flow' : reportType;

      const data = await getFinancials(
        symbol,
        mappedReportType as 'income' | 'balance' | 'cash_flow' | 'all' | undefined
      );

      const formattedText = formatFinancialData(data);

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
          text: `财务数据获取失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
};
