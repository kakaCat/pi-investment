/**
 * Backtest CLI Tool - 回测相关命令
 *
 * 从 quant-cli-tool 中拆分出的回测命令
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

const BACKTEST_COMMANDS: Record<string, CommandRule> = {
  "backtest.run": {
    domain: "backtest",
    action: "run",
    description: "运行回测（指定策略、股票池、时间区间）。",
    params: {
      strategy_id: { required: true, type: "string" },
      symbols: { type: "array" },
      start_date: { required: true, type: "string" },
      end_date: { required: true, type: "string" },
      initial_capital: { type: "number", min: 0 }
    },
    example: {
      strategy_id: "53",
      symbols: ["600000", "000001"],
      start_date: "2025-01-01",
      end_date: "2025-12-31",
      initial_capital: 100000
    },
  },
  "backtest.results": {
    domain: "backtest",
    action: "results",
    description: "查询回测结果（收益率、夏普比率、最大回撤、交易记录）。",
    params: {
      backtest_id: { required: true, type: "string" }
    },
    example: { backtest_id: "bt_20260601_001" },
  },
  "backtest.strategy": {
    domain: "backtest",
    action: "strategy",
    description: "策略历史表现回测（自动选择股票池和时间区间）。",
    params: {
      strategy_id: { required: true, type: "string" },
      period: { type: "string", enum: ["1m", "3m", "6m", "1y", "3y"] }
    },
    example: { strategy_id: "53", period: "6m" },
  },
};

export const backtestCliTool: ToolDefinition = {
  name: "backtest_cli",
  label: "策略回测工具",
  description:
    "策略回测：运行回测、查询结果、策略历史表现。" +
    "适用场景：验证策略有效性、评估风险收益、对比不同策略。",

  parameters: Type.Object({
    command: Type.Union(
      Object.keys(BACKTEST_COMMANDS).map(cmd => Type.Literal(cmd)) as any,
      { description: "回测命令" }
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
        const rule = BACKTEST_COMMANDS[command];

        if (!rule) {
          throw new Error(`未知的回测命令: ${command}`);
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
        toolName: "backtest_cli",
        enablePerformanceMonitoring: true,
        slowToolThreshold: 10000, // 回测通常较慢，提高阈值
        errorSuggestion: "回测需要大量历史数据，如果失败请检查日期范围和数据完整性。"
      }
    );
  }
};
