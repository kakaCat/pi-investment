/**
 * Sentiment CLI Tool - 市场情绪相关命令
 *
 * 从 quant-cli-tool 中拆分出的市场情绪命令
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { wrapToolExecution, validateParams } from "../shared/error-handler.js";
import { handleToolResponse } from "../utils/index.js";

type CommandRule = {
  domain: string;
  action: string;
  description: string;
  params: Record<string, any>;
  example: Record<string, unknown>;
};

const SENTIMENT_COMMANDS: Record<string, CommandRule> = {
  "sentiment.stock_fund_flow": {
    domain: "sentiment",
    action: "stock-fund-flow",
    description: "查询个股资金流向（主力、大单、中单、小单净流入）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      days: { type: "integer", min: 1 }
    },
    example: { symbol: "600000", days: 5 },
  },
  "sentiment.lhb": {
    domain: "sentiment",
    action: "lhb",
    description: "查询龙虎榜全榜或个股近期龙虎榜记录。",
    params: {
      symbol: { type: "string", symbol: true },
      date: { type: "string" }
    },
    example: { date: "20260601" },
  },
  "sentiment.insider_trades": {
    domain: "sentiment",
    action: "insider-trades",
    description: "高管增减持查询。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "600000" },
  },
  "sentiment.fund_holdings": {
    domain: "sentiment",
    action: "fund-holdings",
    description: "查询基金持仓（哪些基金持有该股票）。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "600000" },
  },
  "sentiment.top_fund_stocks": {
    domain: "sentiment",
    action: "top-fund-stocks",
    description: "基金重仓股排行（按持仓市值/占比）。",
    params: {
      limit: { type: "integer", min: 1 }
    },
    example: { limit: 50 },
  },
  "sentiment.top_holders": {
    domain: "sentiment",
    action: "top-holders",
    description: "十大股东/十大流通股东。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "600000" },
  },
  "sentiment.holder_changes": {
    domain: "sentiment",
    action: "holder-changes",
    description: "股东变化趋势（增持/减持分析）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      periods: { type: "integer", min: 1 }
    },
    example: { symbol: "600000", periods: 4 },
  },
  "sentiment.margin_data": {
    domain: "sentiment",
    action: "margin-data",
    description: "个股融资融券数据（融资买入额、融券卖出量）。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "600000" },
  },
};

export const sentimentCliTool: ToolDefinition = {
  name: "sentiment_cli",
  label: "市场情绪分析",
  description:
    "市场情绪分析：资金流向、龙虎榜、高管增减持、基金持仓、重仓股、股东变化、融资融券。" +
    "适用场景：追踪主力资金、发现机构动向、判断市场热度、分析股东结构。",

  parameters: Type.Object({
    command: Type.Union(
      Object.keys(SENTIMENT_COMMANDS).map(cmd => Type.Literal(cmd)) as any,
      { description: "情绪分析命令" }
    ),
    params: Type.Optional(
      Type.Record(Type.String(), Type.Any(), {
        description: "命令参数"
      })
    )
  }),

  execute: async (_toolCallId: string, input: any, _signal?: AbortSignal) => {
    return wrapToolExecution(
      async () => {
        const { command, params = {} } = input as { command: string; params?: Record<string, any> };
        const rule = SENTIMENT_COMMANDS[command];

        if (!rule) {
          throw new Error(`未知的情绪分析命令: ${command}`);
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

        // 使用统一响应处理（大数据自动持久化）
        return handleToolResponse({
          toolName: 'sentiment_cli',
          data: response,
          formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
          metadata: { command, params },
          threshold: 20 * 1024, // 20KB
        });
      },
      {
        toolName: "sentiment_cli",
        enablePerformanceMonitoring: true,
        errorSuggestion: "情绪数据可能有延迟，部分数据仅在交易时间更新。"
      }
    );
  }
};
