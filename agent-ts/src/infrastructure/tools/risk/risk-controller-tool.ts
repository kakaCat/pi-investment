/**
 * Risk Controller Tool - 风险控制工具
 *
 * 职责：交易前风控检查、仓位管理、止损规则管理
 * 命令：check, trade_check, position_size, stop_loss, rules_list, rules_create, rules_update, rules_delete
 *
 * 从 quant_cli 拆分出来，专注于风险控制业务
 * 2026-06-04 新增：止损规则管理命令
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

const RISK_COMMANDS: Record<string, CommandRule> = {
  "check": {
    domain: "risk",
    action: "check",
    description: "综合风控检查：持仓集中度、止损线、总风险敞口。",
    params: {
      symbol: { type: "string", symbol: true }
    },
    example: { symbol: "600519" },
  },
  "trade_check": {
    domain: "risk",
    action: "trade-check",
    description: "对单笔 A 股买卖订单执行交易前风控检查。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      action: { required: true, type: "string", enum: ["buy", "sell"] },
      price: { required: true, type: "number", min: 0 },
      shares: { required: true, type: "integer", min: 1 },
    },
    example: { symbol: "600000", action: "buy", price: 100, shares: 300 },
  },
  "position_size": {
    domain: "risk",
    action: "position-size",
    description: "按 Kelly 公式和组合风控参数计算建议仓位。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      price: { required: true, type: "number", min: 0 },
      signal_strength: { type: "number", min: 0 },
    },
    example: { symbol: "600000", price: 100, signal_strength: 0.8 },
  },
  "stop_loss": {
    domain: "risk",
    action: "stop-loss",
    description: "计算止损价格：支持固定百分比、ATR 倍数、支撑位等方法。",
    params: {
      symbol: { type: "string", symbol: true },
      entry_price: { type: "number", min: 0 },
      method: { type: "string", enum: ["percent", "atr", "support"] },
      atr: { type: "number" },
      percent: { type: "number" },
      support_level: { type: "number" },
    },
    example: { entry_price: 100, method: "atr", atr: 2.5 },
  },
  "rules_list": {
    domain: "risk",
    action: "stop-loss-rules-list",
    description: "查询止损规则列表（可按symbol过滤）。",
    params: {
      symbol: { type: "string", symbol: true },
    },
    example: { symbol: "600519" },
  },
  "rules_create": {
    domain: "risk",
    action: "stop-loss-rules-create",
    description: "创建止损规则（支持固定百分比、ATR倍数、时间止损等）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      rule_type: { required: true, type: "string", enum: ["fixed_percent", "atr_multiple", "trailing", "time_based"] },
      stop_loss_percent: { type: "number", min: 0, max: 1 },
      atr_multiple: { type: "number", min: 0 },
      trailing: { type: "boolean" },
      max_hold_days: { type: "integer", min: 1 },
      enabled: { type: "boolean" },
    },
    example: { symbol: "600519", rule_type: "atr_multiple", atr_multiple: 2.0, trailing: true },
  },
  "rules_update": {
    domain: "risk",
    action: "stop-loss-rules-update",
    description: "更新已有止损规则。",
    params: {
      rule_id: { required: true, type: "string" },
      stop_loss_percent: { type: "number", min: 0, max: 1 },
      atr_multiple: { type: "number", min: 0 },
      trailing: { type: "boolean" },
      enabled: { type: "boolean" },
    },
    example: { rule_id: "rule_123", atr_multiple: 2.5, enabled: true },
  },
  "rules_delete": {
    domain: "risk",
    action: "stop-loss-rules-delete",
    description: "删除止损规则。",
    params: {
      rule_id: { required: true, type: "string" },
    },
    example: { rule_id: "rule_123" },
  },
};

export const riskControllerTool: ToolDefinition = {
  name: "risk_controller",
  label: "风险控制",
  description:
    "风险控制工具：交易前风控检查、仓位计算、止损设置、止损规则管理。" +
    "\n\n命令列表：" +
    "\n  • check - 综合风控检查" +
    "\n  • trade_check - 交易前检查（推荐）" +
    "\n  • position_size - Kelly 仓位计算" +
    "\n  • stop_loss - 止损价格计算" +
    "\n  • rules_list - 查询止损规则列表（新增）" +
    "\n  • rules_create - 创建止损规则（新增）" +
    "\n  • rules_update - 更新止损规则（新增）" +
    "\n  • rules_delete - 删除止损规则（新增）" +
    "\n\n使用场景：" +
    "\n  • 交易前检查：risk_controller({ command: 'trade_check', params: { symbol: '600519', action: 'buy', price: 1800, shares: 100 } })" +
    "\n  • 创建止损规则：risk_controller({ command: 'rules_create', params: { symbol: '600519', rule_type: 'atr_multiple', atr_multiple: 2.0 } })" +
    "\n  • 计算仓位：risk_controller({ command: 'position_size', params: { symbol: '600519', price: 1800 } })" +
    "\n  • 设置止损：risk_controller({ command: 'stop_loss', params: { entry_price: 1800, method: 'atr', atr: 50 } })",

  parameters: Type.Object({
    command: Type.String({
      description: "命令名称：check, trade_check, position_size, stop_loss",
      enum: ["check", "trade_check", "position_size", "stop_loss"]
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
        const rule = RISK_COMMANDS[command];
        if (!rule) {
          throw new Error(
            `未知命令 "${command}"。可用命令: check, trade_check, position_size, stop_loss`
          );
        }

        // 验证必需参数
        for (const [key, paramRule] of Object.entries(rule.params)) {
          if (paramRule.required && !params[key]) {
            throw new Error(`参数 ${key} 是必需的`);
          }
        }

        // 构造完整的命令名称（risk.xxx）
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
        toolName: "risk_controller",
        errorSuggestion: "请检查命令名称和参数是否正确。使用 'trade_check' 命令进行交易前风控检查。"
      }
    );
  },
};
