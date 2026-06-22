/**
 * Trade Monitor Tool - 交易监控工具
 *
 * 职责：查询订单、成交、执行记录
 * 命令：orders, trades, executions, stats
 *
 * 从 quant_cli 拆分出来，专注于交易监控业务
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

const TRADE_COMMANDS: Record<string, CommandRule> = {
  "orders": {
    domain: "orders",
    action: "list",
    description: "查询所有订单列表。v2 端点。",
    params: {},
    example: {},
  },
  "trades": {
    domain: "trades",
    action: "list",
    description: "查询所有成交记录。v2 端点。",
    params: {},
    example: {},
  },
  "executions": {
    domain: "executions",
    action: "list",
    description: "查询信号执行记录列表。v2 端点。",
    params: {},
    example: {},
  },
  "stats": {
    domain: "executions",
    action: "stats",
    description: "查询执行统计：成功率、平均延迟等。v2 端点。",
    params: {},
    example: {},
  },
};

export const tradeMonitorTool: ToolDefinition = {
  name: "trade_monitor",
  label: "交易监控",
  description:
    "交易监控工具：查询订单、成交记录、信号执行、统计信息。" +
    "\n\n命令列表：" +
    "\n  • orders - 查询订单列表" +
    "\n  • trades - 查询成交记录" +
    "\n  • executions - 查询信号执行记录" +
    "\n  • stats - 查询执行统计（推荐）" +
    "\n\n使用场景：" +
    "\n  • 查看订单：trade_monitor({ command: 'orders' })" +
    "\n  • 查看成交：trade_monitor({ command: 'trades' })" +
    "\n  • 查看统计：trade_monitor({ command: 'stats' })",

  parameters: Type.Object({
    command: Type.String({
      description: "命令名称：orders, trades, executions, stats",
      enum: ["orders", "trades", "executions", "stats"]
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
        const rule = TRADE_COMMANDS[command];
        if (!rule) {
          throw new Error(
            `未知命令 "${command}"。可用命令: orders, trades, executions, stats`
          );
        }

        // 构造完整的命令名称
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
        toolName: "trade_monitor",
        errorSuggestion: "请检查命令名称是否正确。使用 'orders' 或 'trades' 命令查看交易记录。"
      }
    );
  },
};
