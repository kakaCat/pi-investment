/**
 * Watchlist CLI Tool - 自选股管理命令
 *
 * 从 quant-cli-tool 中拆分出的自选股相关命令
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

const WATCHLIST_COMMANDS: Record<string, CommandRule> = {
  "watchlist.list": {
    domain: "watchlist",
    action: "list",
    description: "获取自选股列表（可按分组筛选）。",
    params: {
      group_id: { type: "string" }
    },
    example: { group_id: "default" },
  },
  "watchlist.add": {
    domain: "watchlist",
    action: "add",
    description: "添加股票到自选股。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      group_id: { type: "string" },
      note: { type: "string" }
    },
    example: { symbol: "600000", group_id: "default", note: "关注银行股" },
  },
  "watchlist.remove": {
    domain: "watchlist",
    action: "remove",
    description: "从自选股移除股票。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      group_id: { type: "string" }
    },
    example: { symbol: "600000", group_id: "default" },
  },
  "watchlist.update": {
    domain: "watchlist",
    action: "update",
    description: "更新自选股备注/标签。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      group_id: { type: "string" },
      note: { type: "string" },
      tags: { type: "array" }
    },
    example: { symbol: "600000", note: "等待回调", tags: ["银行", "低估值"] },
  },
  "watchlist.groups": {
    domain: "watchlist",
    action: "groups",
    description: "获取自选股分组列表。",
    params: {},
    example: {},
  },
};

export const watchlistCliTool: ToolDefinition = {
  name: "watchlist_cli",
  label: "自选股管理",
  description:
    "自选股管理：列出、添加、移除、更新、分组管理。" +
    "适用场景：管理关注股票池、添加备注标签、按主题分组。",

  parameters: Type.Object({
    command: Type.Union(
      Object.keys(WATCHLIST_COMMANDS).map(cmd => Type.Literal(cmd)) as any,
      { description: "自选股命令" }
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
        const rule = WATCHLIST_COMMANDS[command];

        if (!rule) {
          throw new Error(`未知的自选股命令: ${command}`);
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
          toolName: 'watchlist_cli',
          data: response,
          formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
          metadata: { command, params },
          threshold: 15 * 1024, // 15KB
        });
      },
      {
        toolName: "watchlist_cli",
        enablePerformanceMonitoring: true,
        errorSuggestion: "自选股数据保存在本地数据库，如果操作失败请检查数据库连接。"
      }
    );
  }
};
