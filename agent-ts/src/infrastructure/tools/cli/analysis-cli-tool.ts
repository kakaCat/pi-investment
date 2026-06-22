/**
 * Analysis CLI Tool - 分析相关命令
 *
 * 从 quant-cli-tool 中拆分出的分析相关命令
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

const ANALYSIS_COMMANDS: Record<string, CommandRule> = {
  "analysis.technical": {
    domain: "analysis",
    action: "technical",
    description: "技术分析（RSI、MACD、布林带、均线、KDJ）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      period: { type: "integer", min: 1 }
    },
    example: { symbol: "600000", period: 60 },
  },
  "analysis.price_action": {
    domain: "analysis",
    action: "price-action",
    description: "价格行为分析（支撑位、阻力位、趋势线）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      period: { type: "integer", min: 1 }
    },
    example: { symbol: "600000", period: 90 },
  },
  "analysis.candlestick": {
    domain: "analysis",
    action: "candlestick",
    description: "K线形态识别（锤子线、十字星、吞没形态等）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      period: { type: "integer", min: 1 }
    },
    example: { symbol: "600000", period: 30 },
  },
  "analysis.buy_range": {
    domain: "analysis",
    action: "buy-range",
    description: "计算买入区间（基于估值、技术面、资金面综合判断）。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "600000" },
  },
  "analysis.quality": {
    domain: "analysis",
    action: "quality",
    description: "公司质量评分（ROE、负债率、毛利率、净利率和趋势）。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "600000" },
  },
  "analysis.exit_plan": {
    domain: "analysis",
    action: "exit-plan",
    description: "生成退出计划（止盈、止损、分批卖出策略）。entry_price可选，不提供时使用当前价格。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      entry_price: { required: false, type: "number" },
      position_size: { type: "number" }
    },
    example: { symbol: "600000", entry_price: 10.5, position_size: 1000 },
  },
  "analysis.peers": {
    domain: "analysis",
    action: "peers",
    description: "同行对比（返回目标股关键指标和行业名称，用于后续对比）。",
    params: {
      symbol: { required: true, type: "string", symbol: true }
    },
    example: { symbol: "600000" },
  },
};

export const analysisCliTool: ToolDefinition = {
  name: "analysis_cli",
  label: "股票分析工具",
  description:
    "股票分析：技术分析、价格行为、K线形态、买入区间、公司质量、退出计划、同行对比。" +
    "适用场景：技术面分析、买卖点判断、风险控制、基本面质量评估。",

  parameters: Type.Object({
    command: Type.Union(
      Object.keys(ANALYSIS_COMMANDS).map(cmd => Type.Literal(cmd)) as any,
      { description: "分析命令" }
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
        const rule = ANALYSIS_COMMANDS[command];

        if (!rule) {
          throw new Error(`未知的分析命令: ${command}`);
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
          toolName: 'analysis_cli',
          data: response,
          formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
          metadata: { command, params },
          threshold: 20 * 1024, // 20KB
        });
      },
      {
        toolName: "analysis_cli",
        enablePerformanceMonitoring: true,
        errorSuggestion: "分析工具需要足够的历史数据，如果分析失败请检查股票代码和数据可用性。"
      }
    );
  }
};
