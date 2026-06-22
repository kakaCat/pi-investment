/**
 * Stock CLI Tool - 个股数据查询命令
 *
 * 从 quant-cli-tool 中拆分出的个股相关命令
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

const STOCK_COMMANDS: Record<string, CommandRule> = {
  "stock.batch_quotes": {
    domain: "stock",
    action: "batch-quotes",
    description: "批量查询股票实时报价（支持3只以上股票）。",
    params: {
      symbols: { required: true, type: "array" }
    },
    example: { symbols: ["600000", "000001", "600519"] },
  },
  "stock.list": {
    domain: "stock",
    action: "list",
    description: "获取股票列表（支持按市场、板块筛选）。",
    params: {
      market: { type: "string", enum: ["全部", "沪市", "深市", "创业板", "科创板"] },
      limit: { type: "integer", min: 1 }
    },
    example: { market: "科创板", limit: 50 },
  },
  "stock.score": {
    domain: "stock",
    action: "score",
    description: "综合评分（技术+基本面+动量+质量+估值）。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "600000" },
  },
  "stock.screen": {
    domain: "stock",
    action: "screen",
    description: "多条件选股（支持PE、ROE、市值等筛选）。",
    params: {
      min_roe: { type: "number" },
      max_pe: { type: "number" },
      min_market_cap: { type: "number" },
      max_market_cap: { type: "number" },
      limit: { type: "integer", min: 1 }
    },
    example: { min_roe: 10, max_pe: 30, limit: 20 },
  },
  "stock.technical": {
    domain: "stock",
    action: "technical",
    description: "技术指标计算（RSI、MACD、布林带等）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      period: { type: "integer", min: 1 }
    },
    example: { symbol: "600000", period: 60 },
  },
};

export const stockCliTool: ToolDefinition = {
  name: "stock_cli",
  label: "个股数据查询",
  description:
    "查询个股数据：批量报价、股票列表、综合评分、多条件选股、技术指标。" +
    "适用场景：快速查看多只股票行情、筛选符合条件的股票、分析个股技术面。",

  parameters: Type.Object({
    command: Type.Union(
      Object.keys(STOCK_COMMANDS).map(cmd => Type.Literal(cmd)) as any,
      { description: "个股查询命令" }
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
        const rule = STOCK_COMMANDS[command];

        if (!rule) {
          throw new Error(`未知的个股命令: ${command}`);
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
          toolName: 'stock_cli',
          data: response,
          formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
          metadata: { command, params },
          threshold: 15 * 1024, // 15KB
        });
      },
      {
        toolName: "stock_cli",
        enablePerformanceMonitoring: true,
        errorSuggestion: "请检查股票代码格式（6位数字）和参数是否正确。"
      }
    );
  }
};
