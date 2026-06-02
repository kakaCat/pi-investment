/**
 * Financial CLI Tool - 财务数据查询命令
 *
 * 从 quant-cli-tool 中拆分出的财务相关命令
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../quant/quant-v2-client.js";
import { wrapToolExecution, validateParams } from "../shared/error-handler.js";

type CommandRule = {
  domain: string;
  action: string;
  description: string;
  params: Record<string, any>;
  example: Record<string, unknown>;
};

const FINANCIAL_COMMANDS: Record<string, CommandRule> = {
  "financial.indicators": {
    domain: "financial",
    action: "indicators",
    description: "查询财务指标（ROE、净利润、营收、毛利率等）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      years: { type: "integer", min: 1, max: 10 }
    },
    example: { symbol: "600000", years: 5 },
  },
  "financial.valuation": {
    domain: "financial",
    action: "valuation",
    description: "估值指标（PE、PB、PS、PEG等）。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "600000" },
  },
  "financial.pe_percentile": {
    domain: "financial",
    action: "pe-percentile",
    description: "PE 历史分位数（判断估值高低）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      years: { type: "integer", min: 1, max: 10 }
    },
    example: { symbol: "600000", years: 5 },
  },
  "financial.income_statement": {
    domain: "financial",
    action: "income-statement",
    description: "利润表（营业收入、净利润、毛利率等）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      periods: { type: "integer", min: 1, max: 20 }
    },
    example: { symbol: "600000", periods: 8 },
  },
  "financial.cash_flow": {
    domain: "financial",
    action: "cash-flow",
    description: "现金流量表（经营/投资/筹资现金流）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      periods: { type: "integer", min: 1, max: 20 }
    },
    example: { symbol: "600000", periods: 8 },
  },
  "financial.hk_financials": {
    domain: "financial",
    action: "hk-financials",
    description: "港股财务数据（营收、净利润、ROE等）。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "00700" },
  },
  "financial.hk_analysis": {
    domain: "financial",
    action: "hk-analysis",
    description: "港股财务分析（增长率、盈利能力、偿债能力）。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "00700" },
  },
};

export const financialCliTool: ToolDefinition = {
  name: "financial_cli",
  label: "财务数据查询",
  description:
    "查询财务数据：财务指标、估值、PE分位数、利润表、现金流量表、港股财务。" +
    "适用场景：基本面分析、估值判断、财务健康度评估、A股/港股财务对比。",

  parameters: Type.Object({
    command: Type.Union(
      Object.keys(FINANCIAL_COMMANDS).map(cmd => Type.Literal(cmd)) as any,
      { description: "财务查询命令" }
    ),
    params: Type.Optional(
      Type.Record(Type.String(), Type.Any(), {
        description: "命令参数"
      })
    )
  }),

  execute: async (_toolCallId, input: any) => {
    return wrapToolExecution(
      async () => {
        const { command, params = {} } = input as { command: string; params?: Record<string, any> };
        const rule = FINANCIAL_COMMANDS[command];

        if (!rule) {
          throw new Error(`未知的财务命令: ${command}`);
        }

        // 验证必填参数
        const requiredFields: string[] = [];
        for (const [key, paramRule] of Object.entries(rule.params)) {
          if ((paramRule as any).required) {
            requiredFields.push(key);
          }
        }

        if (requiredFields.length > 0) {
          validateParams(params).required(requiredFields).validate();
        }

        // 调用 v2 API
        const response = await runQuantV2(command, params);

        return {
          content: [{
            type: "text" as const,
            text: typeof response === 'string'
              ? response
              : JSON.stringify(response, null, 2)
          }],
          details: response
        };
      },
      {
        toolName: "financial_cli",
        enablePerformanceMonitoring: true,
        errorSuggestion: "财务数据可能存在延迟，如果查询失败请稍后重试。"
      }
    );
  }
};
