/**
 * Data Manager Tool - 数据管理工具
 *
 * 职责：管理量化数据的完整性和更新
 * 命令：status, full_status, update_klines, update
 *
 * 从 quant_cli 拆分出来，专注于数据管理业务
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

const DATA_COMMANDS: Record<string, CommandRule> = {
  "status": {
    domain: "data",
    action: "status",
    description: "查看本地量化数据库状态。",
    params: { db_path: { type: "string" } },
    example: {},
  },
  "full_status": {
    domain: "data",
    action: "full-status",
    description: "查看股票数据和因子覆盖完整性。",
    params: {},
    example: {},
  },
  "update_klines": {
    domain: "data",
    action: "update-klines",
    description: "更新日线 K 线数据。支持单个或多个股票（逗号分隔）。",
    params: {
      symbols: { type: "string" },
      days: { type: "integer", min: 1 },
    },
    example: { symbols: "600000,000001", days: 365 },
  },
  "update": {
    domain: "data",
    action: "update",
    description: "统一数据更新入口。source 必填：portfolio(持仓)、watchlist(自选)、hs300(沪深300)、all(全部)。可选 days(天数,默认730)、force(强制全量)、async(异步执行)。",
    params: {
      source: { required: true, type: "string" },
      days: { type: "integer", min: 1 },
      force: { type: "boolean" },
      async: { type: "boolean" },
    },
    example: { source: "all" },
  },
};

export const dataManagerTool: ToolDefinition = {
  name: "data_manager",
  label: "数据管理",
  description:
    "量化数据管理工具：查看数据状态、更新数据。" +
    "\n\n命令列表：" +
    "\n  • status - 查看数据库状态" +
    "\n  • full_status - 查看数据完整性" +
    "\n  • update_klines - 批量更新K线数据" +
    "\n  • update - 统一数据更新入口（推荐）" +
    "\n\n使用场景：" +
    "\n  • 每日数据更新：data_manager({ command: 'update', params: { source: 'all' } })" +
    "\n  • 检查数据状态：data_manager({ command: 'status' })" +
    "\n  • 更新指定股票：data_manager({ command: 'update_klines', params: { symbols: '600519', days: 365 } })",

  parameters: Type.Object({
    command: Type.String({
      description: "命令名称：status, full_status, update_klines, update",
      enum: ["status", "full_status", "update_klines", "update"]
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
        const rule = DATA_COMMANDS[command];
        if (!rule) {
          throw new Error(
            `未知命令 "${command}"。可用命令: status, full_status, update_klines, update`
          );
        }

        // 验证必需参数
        for (const [key, paramRule] of Object.entries(rule.params)) {
          if (paramRule.required && !params[key]) {
            throw new Error(`参数 ${key} 是必需的`);
          }
        }

        // 构造完整的命令名称（data.xxx）
        const fullCommand = `${rule.domain}.${rule.action}`;

        // 调用 quantsys-v2 API
        const result = await runQuantV2(fullCommand, params);

        if (!result.ok) {
          const errorMsg = typeof result.error === 'string'
            ? result.error
            : result.error?.message || `命令执行失败: ${fullCommand}`;
          throw new Error(errorMsg);
        }

        // 格式化输出
        let output = `✅ 命令执行成功: ${command}\n\n`;

        if (result.data) {
          if (typeof result.data === 'string') {
            output += result.data;
          } else {
            output += JSON.stringify(result.data, null, 2);
          }
        }

        return output;
      },
      {
        toolName: "data_manager",
        errorSuggestion: "请检查命令名称和参数是否正确。使用 'status' 命令查看数据库状态。"
      }
    );
  },
};
