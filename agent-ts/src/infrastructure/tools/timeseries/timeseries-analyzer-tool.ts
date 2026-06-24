/**
 * Timeseries Analyzer Tool - 时间序列分析工具
 *
 * 职责：时间序列预测和分析
 * 命令：arima, garch, kalman, decay
 *
 * 从 quant_cli 拆分出来，专注于时间序列分析业务
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

const TIMESERIES_COMMANDS: Record<string, CommandRule> = {
  "arima": {
    domain: "timeseries",
    action: "arima",
    description: "ARIMA 时间序列预测模型。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      periods: { type: "integer", min: 1 },
      p: { type: "integer" },
      d: { type: "integer" },
      q: { type: "integer" },
    },
    example: { symbol: "600000", periods: 5, p: 1, d: 1, q: 1 },
  },
  "garch": {
    domain: "timeseries",
    action: "garch",
    description: "GARCH 波动率预测模型。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      periods: { type: "integer", min: 1 },
      p: { type: "integer" },
      q: { type: "integer" },
    },
    example: { symbol: "600000", periods: 5, p: 1, q: 1 },
  },
  "kalman": {
    domain: "timeseries",
    action: "kalman",
    description: "卡尔曼滤波器进行状态估计和预测。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      observation_noise: { type: "number" },
      process_noise: { type: "number" },
    },
    example: { symbol: "600000", observation_noise: 0.1, process_noise: 0.01 },
  },
  "decay": {
    domain: "factor",
    action: "decay",
    description: "分析因子随时间的衰减特性。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      factor_name: { required: true, type: "string" },
      periods: { type: "integer", min: 1 },
    },
    example: { symbol: "600000", factor_name: "momentum", periods: 20 },
  },
};

export const timeseriesAnalyzerTool: ToolDefinition = {
  name: "timeseries_analyzer",
  label: "时间序列分析",
  description:
    "时间序列分析工具：ARIMA预测、GARCH波动率、卡尔曼滤波、因子衰减。" +
    "\n\n命令列表：" +
    "\n  • arima - ARIMA时间序列预测" +
    "\n  • garch - GARCH波动率预测" +
    "\n  • kalman - 卡尔曼滤波器" +
    "\n  • decay - 因子衰减分析" +
    "\n\n使用场景：" +
    "\n  • 价格预测：timeseries_analyzer({ command: 'arima', params: { symbol: '600519', periods: 5 } })" +
    "\n  • 波动率预测：timeseries_analyzer({ command: 'garch', params: { symbol: '600519', periods: 5 } })" +
    "\n  • 因子衰减：timeseries_analyzer({ command: 'decay', params: { symbol: '600519', factor_name: 'momentum' } })",

  parameters: Type.Object({
    command: Type.String({
      description: "命令名称：arima, garch, kalman, decay",
      enum: ["arima", "garch", "kalman", "decay"]
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
        const rule = TIMESERIES_COMMANDS[command];
        if (!rule) {
          throw new Error(
            `未知命令 "${command}"。可用命令: arima, garch, kalman, decay`
          );
        }

        // 验证必需参数
        for (const [key, paramRule] of Object.entries(rule.params)) {
          if (paramRule.required && !params[key]) {
            throw new Error(`参数 ${key} 是必需的`);
          }
        }

        // 构造完整的命令名称
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
        toolName: "timeseries_analyzer",
        errorSuggestion: "请检查股票代码和预测参数。ARIMA 和 GARCH 需要足够的历史数据。"
      }
    );
  },
};
