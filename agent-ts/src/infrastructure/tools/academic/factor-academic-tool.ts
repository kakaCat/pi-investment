/**
 * Factor Academic Tool - 学术因子工具
 *
 * 职责：学术级多因子模型计算
 * 命令：list, fama_french_3, fama_french_5, barra, carhart
 *
 * 从 quant_cli 拆分出来，专注于学术因子业务
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

const FACTOR_COMMANDS: Record<string, CommandRule> = {
  "list": {
    domain: "factor",
    action: "list",
    description: "列出某只股票的所有可用因子。v2 端点。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
    },
    example: { symbol: "600000" },
  },
  "fama_french_3": {
    domain: "factor",
    action: "fama-french-3",
    description: "计算 Fama-French 三因子模型（市场、规模、价值）。",
    params: {
      symbols: { required: true, type: "array" },
      start_date: { type: "string" },
      end_date: { type: "string" },
    },
    example: { symbols: ["600000.SH", "000001.SZ"], start_date: "2023-01-01", end_date: "2023-12-31" },
  },
  "fama_french_5": {
    domain: "factor",
    action: "fama-french-5",
    description: "计算 Fama-French 五因子模型（市场、规模、价值、盈利、投资）。",
    params: {
      symbols: { required: true, type: "array" },
      start_date: { type: "string" },
      end_date: { type: "string" },
    },
    example: { symbols: ["600000.SH", "000001.SZ"], start_date: "2023-01-01", end_date: "2023-12-31" },
  },
  "barra": {
    domain: "factor",
    action: "barra",
    description: "计算 Barra 风格因子（规模、价值、成长、杠杆等）。",
    params: {
      symbols: { required: true, type: "array" },
      start_date: { type: "string" },
      end_date: { type: "string" },
    },
    example: { symbols: ["600000.SH", "000001.SZ"], start_date: "2023-01-01" },
  },
  "carhart": {
    domain: "factor",
    action: "carhart",
    description: "计算 Carhart 四因子模型（FF三因子 + 动量因子）。",
    params: {
      symbols: { required: true, type: "array" },
      start_date: { type: "string" },
      end_date: { type: "string" },
    },
    example: { symbols: ["600000.SH", "000001.SZ"], start_date: "2023-01-01" },
  },
};

export const factorAcademicTool: ToolDefinition = {
  name: "factor_academic",
  label: "学术因子",
  description:
    "学术级多因子模型工具：Fama-French、Barra、Carhart等。" +
    "\n\n命令列表：" +
    "\n  • list - 列出可用因子" +
    "\n  • fama_french_3 - FF三因子模型（市场、规模、价值）" +
    "\n  • fama_french_5 - FF五因子模型（推荐）" +
    "\n  • barra - Barra风格因子" +
    "\n  • carhart - Carhart四因子模型" +
    "\n\n使用场景：" +
    "\n  • 因子研究：factor_academic({ command: 'fama_french_5', params: { symbols: ['600000', '000001'], start_date: '2023-01-01' } })" +
    "\n  • 风格分析：factor_academic({ command: 'barra', params: { symbols: ['600000', '000001'] } })" +
    "\n  • 查看因子：factor_academic({ command: 'list', params: { symbol: '600000' } })",

  parameters: Type.Object({
    command: Type.String({
      description: "命令名称：list, fama_french_3, fama_french_5, barra, carhart",
      enum: ["list", "fama_french_3", "fama_french_5", "barra", "carhart"]
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
        const rule = FACTOR_COMMANDS[command];
        if (!rule) {
          throw new Error(
            `未知命令 "${command}"。可用命令: list, fama_french_3, fama_french_5, barra, carhart`
          );
        }

        // 验证必需参数
        for (const [key, paramRule] of Object.entries(rule.params)) {
          if (paramRule.required && !params[key]) {
            throw new Error(`参数 ${key} 是必需的`);
          }
        }

        // 构造完整的命令名称（factor.xxx）
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
        toolName: "factor_academic",
        errorSuggestion: "请检查股票代码和日期范围。推荐使用 'fama_french_5' 进行多因子分析。"
      }
    );
  },
};
