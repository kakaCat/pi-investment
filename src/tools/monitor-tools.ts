/**
 * Monitor Tools - 实时盯盘工具
 */
import type { ToolDefinition } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { FeishuService } from "../services/notification/feishu-service.js";

const feishuService = new FeishuService();

export const sendFeishuAlertTool: ToolDefinition = {
  name: "send_feishu_alert",
  label: "发送飞书通知",
  description: "发送交易信号到飞书通知用户",
  parameters: Type.Object({
    action: Type.Union([Type.Literal("buy"), Type.Literal("sell")]),
    symbol: Type.String(),
    name: Type.String(),
    price: Type.Number(),
    reason: Type.String({ description: "详细理由（技术面+基本面）" }),
    confidence: Type.Number({ minimum: 0, maximum: 1 }),
    position_pct: Type.Optional(Type.Number({ description: "建议仓位百分比" }))
  }),
  execute: async (_toolCallId, params: any) => {
    await feishuService.sendTradeAlert(params);
    return { content: [{ type: "text" as const, text: JSON.stringify({ success: true, message: "已发送飞书通知" }) }], details: undefined };
  }
};

export const scheduleNextCheckTool: ToolDefinition = {
  name: "schedule_next_check",
  label: "设置下次检查",
  description: "根据市场状态设置下次盯盘时间",
  parameters: Type.Object({
    minutes: Type.Number({ minimum: 1, maximum: 60, description: "多少分钟后检查" }),
    reason: Type.String({ description: "为什么选择这个时间间隔" })
  }),
  execute: async (_toolCallId, params: any) => {
    console.log(`[Monitor] 下次检查: ${params.minutes}分钟后 (${params.reason})`);
    return { content: [{ type: "text" as const, text: JSON.stringify({
      success: true,
      next_check_minutes: params.minutes,
      reason: params.reason
    }) }], details: undefined };
  }
};

export const monitorTools = [sendFeishuAlertTool, scheduleNextCheckTool];
