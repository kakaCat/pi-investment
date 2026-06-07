/**
 * Market CLI Tool - 市场数据查询命令
 *
 * 从 quant-cli-tool 中拆分出的市场相关命令
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { wrapToolExecution } from "../shared/error-handler.js";
import { handleToolResponse } from "../utils/index.js";

type CommandRule = {
  domain: string;
  action: string;
  description: string;
  params: Record<string, any>;
  example: Record<string, unknown>;
  deprecated?: boolean;
  replacement?: string;
};

const MARKET_COMMANDS: Record<string, CommandRule> = {
  "market.overview": {
    domain: "market",
    action: "overview",
    description: "查询主要 A 股指数概览。",
    params: {},
    example: {},
  },
  "market.index_history": {
    domain: "market",
    action: "index-history",
    description: "查询指数历史数据（支持上证指数、深证成指、创业板指等）。",
    params: {
      index_code: { required: true, type: "string" },
      start_date: { type: "string" },
      end_date: { type: "string" },
    },
    example: { index_code: "000001", start_date: "2026-01-01" },
  },
  "market.sectors": {
    domain: "market",
    action: "sectors",
    description: "查询 A 股行业板块列表。",
    params: {},
    example: {},
  },
  "market.concept_stocks": {
    domain: "market",
    action: "concept-stocks",
    description: "查询概念/主题板块成分股。使用前请先调用 market.concepts 获取可用概念列表。",
    params: { concept: { required: true, type: "string" } },
    example: { concept: "人工智能" },
  },
  "market.concepts": {
    domain: "market",
    action: "concepts",
    description: "查询全部概念/主题板块列表。",
    params: {},
    example: {},
  },
  "market.sector_flow": {
    domain: "market",
    action: "sector-flow",
    description: "查询行业资金流向排行。",
    params: {},
    example: {},
  },
  "market.margin": {
    domain: "market",
    action: "margin",
    description: "查询全市场融资融券余额趋势。",
    params: {},
    example: {},
  },
  "market.news": {
    domain: "market",
    action: "news",
    description: "查询市场综合新闻。",
    params: { limit: { type: "integer", min: 1 } },
    example: { limit: 10 },
  },
  "market.hot_stocks": {
    domain: "market",
    action: "hot-stocks",
    description: "查询热搜股票排行。",
    params: {},
    example: {},
  },
};

export const marketCliTool: ToolDefinition = {
  name: "market_cli",
  label: "市场数据查询",
  description:
    "查询 A 股市场数据：指数概览/历史、行业板块、概念股、资金流向、融资融券、市场新闻、热搜股票。" +
    "适用场景：了解市场整体情况、行业轮动、资金流向、热点追踪。" +
    "注意：宏观数据、北向资金、市场情绪请使用 L1 专用工具（data_fetch_macro、data_fetch_north_flow、data_fetch_market_sentiment）。",

  parameters: Type.Object({
    command: Type.Union(
      Object.keys(MARKET_COMMANDS).map(cmd => Type.Literal(cmd)) as any,
      { description: "市场查询命令" }
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
        const rule = MARKET_COMMANDS[command];

        if (!rule) {
          throw new Error(`未知的市场命令: ${command}`);
        }

        // 验证必填参数
        for (const [key, paramRule] of Object.entries(rule.params)) {
          if ((paramRule as any).required && !params[key]) {
            let errorMsg = `缺少必填参数: ${key}。示例: ${JSON.stringify(rule.example)}`;

            // 特殊提示：concept_stocks 需要先查询可用概念
            if (command === 'market.concept_stocks' && key === 'concept') {
              errorMsg += '\n\n💡 提示：请先调用 market.concepts 获取所有可用的概念板块列表，然后从中选择一个概念名称。';
            }

            throw new Error(errorMsg);
          }
        }

        // 调用 v2 API
        const response = await runQuantV2(command, params);

        // 使用统一响应处理（大数据自动持久化）
        return handleToolResponse({
          toolName: 'market_cli',
          data: response,
          formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
          metadata: { command, params },
          threshold: 20 * 1024, // 20KB
        });
      },
      {
        toolName: "market_cli",
        enablePerformanceMonitoring: true,
        errorSuggestion: "请检查命令名称和参数格式是否正确。使用 market_cli({ command: 'market.overview' }) 查看示例。"
      }
    );
  }
};
