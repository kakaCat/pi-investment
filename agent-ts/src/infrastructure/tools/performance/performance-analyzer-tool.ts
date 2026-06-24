/**
 * Performance Analyzer Tool - 性能分析工具
 *
 * 职责：策略性能分析和对比
 * 命令：analyze, by_strategy, comparison
 *
 * 从 quant_cli 拆分出来，专注于性能分析业务
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { wrapToolExecution } from "../shared/error-handler.js";

type CommandRule = {
  domain: string;
  action: string;
  description: string;
  params: Record<string, any>;
  example: Record<string, unknown>;
};

const PERFORMANCE_COMMANDS: Record<string, CommandRule> = {
  "analyze": {
    domain: "performance",
    action: "analyze",
    description: "分析策略信号表现，返回胜率、平均收益、最大回撤和夏普比率。",
    params: {
      strategy_id: { type: "string" },
      days: { type: "integer", min: 1 },
      signals_dir: { type: "string" },
    },
    example: { strategy_id: "rsi-strategy", days: 90 },
  },
  "by_strategy": {
    domain: "performance",
    action: "by-strategy",
    description: "查询单个策略的性能详情：收益、回撤、夏普比率。v2 端点。",
    params: {
      strategy_id: { required: true, type: "string" },
    },
    example: { strategy_id: "rsi-strategy" },
  },
  "comparison": {
    domain: "performance",
    action: "comparison",
    description: "多策略性能对比。v2 端点。",
    params: {},
    example: {},
  },
};

export const performanceAnalyzerTool: ToolDefinition = {
  name: "performance_analyzer",
  label: "性能分析",
  description:
    "策略性能分析工具：信号分析、策略对比、收益统计。" +
    "\n\n命令列表：" +
    "\n  • analyze - 分析策略信号表现" +
    "\n  • by_strategy - 查询单策略性能（推荐）" +
    "\n  • comparison - 多策略性能对比" +
    "\n\n使用场景：" +
    "\n  • 查看策略表现：performance_analyzer({ command: 'by_strategy', params: { strategy_id: 'rsi-strategy' } })" +
    "\n  • 分析信号：performance_analyzer({ command: 'analyze', params: { strategy_id: 'rsi-strategy', days: 90 } })" +
    "\n  • 对比策略：performance_analyzer({ command: 'comparison' })",

  parameters: Type.Object({
    command: Type.String({
      description: "命令名称：analyze, by_strategy, comparison",
      enum: ["analyze", "by_strategy", "comparison"]
    }),
    params: Type.Optional(
      Type.Object({}, {
        additionalProperties: true,
        description: "命令参数（可选）"
      })
    )
  }),

  execute: async (_toolCallId: string, rawParams: any, _signal?: AbortSignal) => {
    return wrapToolExecution(
      async () => {
        const { command, params = {} } = rawParams;

        // 验证命令
        const rule = PERFORMANCE_COMMANDS[command];
        if (!rule) {
          throw new Error(
            `未知命令 "${command}"。可用命令: analyze, by_strategy, comparison`
          );
        }

        // 验证必需参数
        for (const [key, paramRule] of Object.entries(rule.params)) {
          if (paramRule.required && !params[key]) {
            throw new Error(`参数 ${key} 是必需的`);
          }
        }

        // 构造完整的命令名称（performance.xxx）
        const fullCommand = `${rule.domain}.${rule.action}`;

        // 调用 quantsys-v2 API
        const result = await runQuantV2(fullCommand, params);

        if (!result.ok) {
          const errorMsg = typeof (result as any).error === 'string'
            ? (result as any).error
            : (result as any).error?.message || `命令执行失败: ${fullCommand}`;
          throw new Error(errorMsg);
        }

        // 格式化输出
        let output = `✅ 命令执行成功: ${command}\n\n`;

        if ((result as any).data) {
          if (typeof (result as any).data === 'string') {
            output += (result as any).data;
          } else {
            output += JSON.stringify((result as any).data, null, 2);
          }
        }

        return output;
      },
      {
        toolName: "performance_analyzer",
        errorSuggestion: "请检查策略ID是否正确。使用 'by_strategy' 命令查看单个策略的性能指标。"
      }
    );
  },
};
