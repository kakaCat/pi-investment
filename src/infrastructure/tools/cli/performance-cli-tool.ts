/**
 * Performance Analysis CLI Tool
 *
 * 绩效分析命令：策略表现分析、多策略对比
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../quant/quant-v2-client.js";
import { formatMaybeLargeToolOutput } from "../shared/large-tool-output.js";

const PERFORMANCE_COMMANDS = {
  "performance.analyze": {
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
  "performance.by_strategy": {
    domain: "performance",
    action: "by-strategy",
    description: "查询单个策略的性能详情：收益、回撤、夏普比率。",
    params: {
      strategy_id: { required: true, type: "string" },
    },
    example: { strategy_id: "rsi-strategy" },
  },
  "performance.comparison": {
    domain: "performance",
    action: "comparison",
    description: "多策略性能对比。",
    params: {},
    example: {},
  },
};

export const performanceCliTool: ToolDefinition = {
  name: "performance_cli",
  label: "绩效分析 CLI",
  description:
    "绩效分析命令行工具，支持 3 个命令：" +
    "performance.analyze（策略表现分析）、performance.by_strategy（单策略详情）、" +
    "performance.comparison（多策略对比）。" +
    "通过 command 参数指定命令，params 参数传递命令参数。",

  parameters: Type.Object({
    command: Type.String({
      description: `命令名称，可选值：${Object.keys(PERFORMANCE_COMMANDS).join(", ")}`,
    }),
    params: Type.Optional(
      Type.Record(Type.String(), Type.Unknown(), {
        description: "命令参数对象",
      })
    ),
  }),

  execute: async (_toolCallId, rawParams) => {
    const { command, params = {} } = rawParams;

    // 验证命令
    const rule = PERFORMANCE_COMMANDS[command as keyof typeof PERFORMANCE_COMMANDS];
    if (!rule) {
      return {
        content: [{
          type: "text" as const,
          text: `不支持的绩效命令: ${command}\n\n可用命令: ${Object.keys(PERFORMANCE_COMMANDS).join(", ")}`
        }],
        details: undefined
      };
    }

    try {
      // 调用后端 API
      const result = await runQuantV2(rule.domain, rule.action, params);

      // 格式化输出
      const output = formatMaybeLargeToolOutput(JSON.stringify(result, null, 2));

      return {
        content: [{ type: "text" as const, text: output }],
        details: result
      };
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `❌ 绩效命令执行失败\n\n命令: ${command}\n错误: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  },
};
