/**
 * Portfolio Optimizer Tool - 组合优化工具
 *
 * 职责：投资组合权重优化和相关性分析
 * 命令：optimize, correlation
 *
 * 从 quant_cli 拆分出来，专注于组合优化业务
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

const PORTFOLIO_COMMANDS: Record<string, CommandRule> = {
  "optimize": {
    domain: "portfolio",
    action: "optimize",
    description: "基于历史数据优化投资组合权重，支持均值方差、最小方差、风险平价、最大夏普等方法。",
    params: {
      symbols: { required: true, type: "array" },
      start_date: { type: "string" },
      end_date: { type: "string" },
      method: { type: "string", enum: ["mean_variance", "min_variance", "risk_parity", "max_sharpe", "equal_weight"] },
      risk_free_rate: { type: "number" },
      target_return: { type: "number" },
      constraints: { type: "object" },
    },
    example: { symbols: ["600000.SH", "000001.SZ", "600519.SH"], method: "max_sharpe", risk_free_rate: 0.03 },
  },
  "correlation": {
    domain: "portfolio",
    action: "correlation",
    description: "计算投资组合内股票的相关性矩阵，用于分散化分析。",
    params: {
      symbols: { required: true, type: "array" },
      start_date: { type: "string" },
      end_date: { type: "string" },
      method: { type: "string", enum: ["pearson", "spearman", "kendall"] },
    },
    example: { symbols: ["600000.SH", "000001.SZ", "600519.SH"], method: "pearson" },
  },
};

export const portfolioOptimizerTool: ToolDefinition = {
  name: "portfolio_optimizer",
  label: "组合优化",
  description:
    "投资组合优化工具：权重优化、相关性分析。" +
    "\n\n命令列表：" +
    "\n  • optimize - 组合权重优化（推荐）" +
    "\n  • correlation - 相关性矩阵分析" +
    "\n\n支持的优化方法：" +
    "\n  • mean_variance - 均值方差优化" +
    "\n  • min_variance - 最小方差" +
    "\n  • risk_parity - 风险平价" +
    "\n  • max_sharpe - 最大夏普比率（推荐）" +
    "\n  • equal_weight - 等权重" +
    "\n\n使用场景：" +
    "\n  • 优化组合：portfolio_optimizer({ command: 'optimize', params: { symbols: ['600000', '000001', '600519'], method: 'max_sharpe' } })" +
    "\n  • 分析相关性：portfolio_optimizer({ command: 'correlation', params: { symbols: ['600000', '000001'] } })",

  parameters: Type.Object({
    command: Type.String({
      description: "命令名称：optimize, correlation",
      enum: ["optimize", "correlation"]
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
        const rule = PORTFOLIO_COMMANDS[command];
        if (!rule) {
          throw new Error(
            `未知命令 "${command}"。可用命令: optimize, correlation`
          );
        }

        // 验证必需参数
        for (const [key, paramRule] of Object.entries(rule.params)) {
          if (paramRule.required && !params[key]) {
            throw new Error(`参数 ${key} 是必需的`);
          }
        }

        // 构造完整的命令名称（portfolio.xxx）
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
        toolName: "portfolio_optimizer",
        errorSuggestion: "请检查股票代码列表和优化方法。推荐使用 'max_sharpe' 方法进行组合优化。"
      }
    );
  },
};
