/**
 * Watch Manage Tool - 实时盯盘规则管理
 *
 * 管理 quantsys-v2 WatchEngine 的盯盘规则：添加/查看/更新/删除监视规则，查询触发记录。
 * 触发后 v2 会通过 wake-channel 唤醒 Agent 决策。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

const ConditionSchema = Type.Object({
  type: Type.String({
    description: "条件类型: price_break(价格上下破) | pct_change(涨跌幅) | pnl_pct(盈亏%) | velocity(瞬时涨速) | volume_surge(量能异动)"
  }),
  params: Type.Record(Type.String(), Type.Any(), {
    description: "条件参数。price_break: {direction, price}; pct_change: {direction, pct}; pnl_pct: {direction, pct}; velocity: {pct, window_min}; volume_surge: {multiple}。direction: above|below；pct 为百分数(3.0=3%)"
  }),
  cooldown_sec: Type.Optional(Type.Number({ description: "触发冷却秒数，默认300" })),
});

function errorResult(error: string, text: string) {
  return {
    content: [{ type: "text" as const, text }],
    details: { success: false, error },
  };
}

export const watchManageTool: ToolDefinition = {
  name: "watch_manage",
  label: "盯盘管理",
  description:
    "实时盯盘规则管理：对股票设置盘中监视条件（价格上下破/涨跌幅/盈亏%/瞬时涨速/量能异动），" +
    "触发时后端会唤醒你决策。持仓股止损止盈、买入机会监控都应通过此工具注册规则。",
  parameters: Type.Object({
    action: Type.String({ description: "操作: add | list | update | remove | triggers" }),
    symbol: Type.Optional(Type.String({ description: "股票代码，如 600519.SH" })),
    rule_id: Type.Optional(Type.Number({ description: "规则ID（update/remove 必填）" })),
    conditions: Type.Optional(Type.Array(ConditionSchema, { description: "监视条件数组（add/update 用）" })),
    context: Type.Optional(Type.String({ description: "监视理由——触发时会原样回传给你作决策上下文，务必写清楚" })),
    cost_price: Type.Optional(Type.Number({ description: "成本价（pnl_pct 条件必填）" })),
    active_window: Type.Optional(Type.Array(Type.String(), {
      description: "盯盘时段，如 [\"09:30-10:30\",\"14:30-15:00\"]，默认全交易时段"
    })),
    expires_at: Type.Optional(Type.String({ description: "过期时间 ISO 格式，如 2026-07-25T15:00:00" })),
    enabled: Type.Optional(Type.Boolean({ description: "启用/停用（update 用；list 用作过滤）" })),
    limit: Type.Optional(Type.Number({ description: "triggers 返回条数，默认50" })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    const call = async (command: string, payload: Record<string, unknown>) => {
      const response = await runQuantV2(command, payload);
      return handleToolResponse({
        toolName: "watch_manage",
        data: response,
        formatter: (data) => (typeof data === "string" ? data : JSON.stringify(data, null, 2)),
        metadata: { params },
      });
    };

    try {
      switch (params.action) {
        case "add": {
          if (!params.symbol) return errorResult("MISSING_SYMBOL", "缺少必填参数: symbol");
          if (!params.conditions?.length) {
            return errorResult("MISSING_CONDITIONS", "add 需要非空 conditions 数组");
          }
          return call("watch.rules.create", {
            symbol: params.symbol,
            conditions: params.conditions,
            context: params.context,
            cost_price: params.cost_price,
            active_window: params.active_window,
            expires_at: params.expires_at,
          });
        }
        case "list":
          return call("watch.rules.list", {
            symbol: params.symbol,
            enabled: params.enabled,
          });
        case "update": {
          if (params.rule_id === undefined) return errorResult("MISSING_RULE_ID", "update 需要 rule_id");
          const { action, rule_id, ...fields } = params;
          return call("watch.rules.update", { id: rule_id, ...fields });
        }
        case "remove": {
          if (params.rule_id === undefined) return errorResult("MISSING_RULE_ID", "remove 需要 rule_id");
          return call("watch.rules.remove", { id: params.rule_id });
        }
        case "triggers":
          return call("watch.triggers.list", { symbol: params.symbol, limit: params.limit });
        default:
          return errorResult("UNKNOWN_ACTION", `未知 action: ${params.action}，支持: add | list | update | remove | triggers`);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text" as const, text: `盯盘规则操作失败: ${errorMsg}` }],
        details: { success: false, error: errorMsg, params },
      };
    }
  },
};
