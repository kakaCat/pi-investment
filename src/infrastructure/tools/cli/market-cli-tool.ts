/**
 * Market CLI Tool - 市场数据查询命令
 *
 * 从 quant-cli-tool 中拆分出的市场相关命令
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { wrapToolExecution } from "../shared/error-handler.js";
import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";
import { paths } from "../../../config/config.js";

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
    description: "查询概念/主题板块成分股。",
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
  "market.macro": {
    domain: "market",
    action: "macro",
    description: "查询 PMI、CPI、GDP 等宏观指标。",
    params: { indicators: { type: "array" } },
    example: { indicators: ["pmi", "cpi"] },
  },
  "market.north_flow": {
    domain: "market",
    action: "north-flow",
    description: "查询北向资金流向。",
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
  "market.sentiment": {
    domain: "market",
    action: "sentiment",
    description: "查询市场情绪指标（涨跌家数、涨停跌停等）。",
    params: {},
    example: {},
  },
};

export const marketCliTool: ToolDefinition = {
  name: "market_cli",
  label: "市场数据查询",
  description:
    "查询 A 股市场数据：指数概览/历史、行业板块、概念股、宏观指标、资金流向、融资融券、市场新闻、热搜股票、市场情绪。" +
    "适用场景：了解市场整体情况、行业轮动、资金流向、热点追踪。",

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
            throw new Error(
              `缺少必填参数: ${key}。` +
              `示例: ${JSON.stringify(rule.example)}`
            );
          }
        }

        // 调用 v2 API
        const response = await runQuantV2(command, params);

        // 确保输出目录存在
        mkdirSync(paths.toolOutputsDir, { recursive: true });

        // 生成文件名：命令名-时间戳.json
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const fileName = `${command.replace(/\./g, '-')}-${timestamp}.json`;
        const filePath = join(paths.toolOutputsDir, fileName);

        // 写入文件
        const outputData = {
          command,
          params,
          timestamp: new Date().toISOString(),
          data: response
        };
        writeFileSync(filePath, JSON.stringify(outputData, null, 2), 'utf-8');

        // 返回文件路径信息
        const resultText = `数据已保存到文件: ${filePath}\n\n` +
          `文件包含以下内容：\n` +
          `- 命令: ${command}\n` +
          `- 参数: ${JSON.stringify(params)}\n` +
          `- 时间戳: ${outputData.timestamp}\n` +
          `- 数据: 请使用 Read 工具读取完整数据\n\n` +
          `相对路径: .pi-invest/tool-outputs/${fileName}`;

        return {
          content: [{
            type: "text" as const,
            text: resultText
          }],
          details: {
            filePath,
            fileName,
            command,
            params,
            timestamp: outputData.timestamp
          }
        };
      },
      {
        toolName: "market_cli",
        enablePerformanceMonitoring: true,
        errorSuggestion: "请检查命令名称和参数格式是否正确。使用 market_cli({ command: 'market.overview' }) 查看示例。"
      }
    );
  }
};
