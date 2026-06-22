/**
 * Monitor Alert Tool (L6 监控运维层)
 *
 * 整合通知工具为单一 monitor_alert 工具
 * 支持通用消息、交易信号、市场简报和风险警告
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import {
  sendNotificationTool,
  sendTradeSignalTool,
  sendMarketBriefTool,
  sendRiskWarningTool
} from "../shared/notification-tools.js";
import { FeishuService } from "../../../services/notification/feishu-service.js";

const feishuService = new FeishuService();

export const monitorAlertTool: ToolDefinition = {
  name: "monitor_alert",
  label: "监控告警",
  description:
    "发送监控告警通知，支持多种类型：\n" +
    "- general: 通用消息通知\n" +
    "- trade_signal: 交易信号（买入/卖出）\n" +
    "- market_brief: 市场简报\n" +
    "- risk_warning: 风险警告\n" +
    "trade_signal 类型可通过 channel='feishu' 额外发送到飞书通知。\n" +
    "根据 type 参数自动路由到对应的通知渠道",
  parameters: Type.Object({
    type: Type.Union([
      Type.Literal("general"),
      Type.Literal("trade_signal"),
      Type.Literal("market_brief"),
      Type.Literal("risk_warning")
    ], { description: "通知类型" }),
    channel: Type.Optional(Type.Union([
      Type.Literal("default"),
      Type.Literal("feishu")
    ], { description: "通知渠道（可选，仅 trade_signal 生效）。default=默认通知服务, feishu=额外发送飞书通知" })),

    // general 参数
    message: Type.Optional(Type.String({ description: "通知内容（general类型必填）" })),
    title: Type.Optional(Type.String({ description: "通知标题（general类型可选）" })),

    // trade_signal 参数
    action: Type.Optional(Type.Union([Type.Literal("buy"), Type.Literal("sell")], {
      description: "交易动作（trade_signal类型必填）"
    })),
    symbol: Type.Optional(Type.String({ description: "股票代码（trade_signal类型必填）" })),
    name: Type.Optional(Type.String({ description: "股票名称（trade_signal类型必填）" })),
    price: Type.Optional(Type.Number({ description: "当前价格（trade_signal类型必填）" })),
    reason: Type.Optional(Type.String({ description: "交易理由（trade_signal类型必填）" })),
    confidence: Type.Optional(Type.Number({
      minimum: 0,
      maximum: 1,
      description: "信号置信度 0-1（trade_signal类型必填）"
    })),
    position_pct: Type.Optional(Type.Number({
      description: "建议仓位百分比（trade_signal类型可选）"
    })),

    // market_brief 参数
    summary: Type.Optional(Type.String({ description: "市场概况总结（market_brief类型必填）" })),
    indices: Type.Optional(Type.Record(
      Type.String(),
      Type.Object({
        value: Type.Number({ description: "指数点位" }),
        change: Type.Number({ description: "涨跌幅百分比" })
      }),
      { description: "指数数据（market_brief类型必填）" }
    )),
    highlights: Type.Optional(Type.Array(Type.String(), {
      description: "市场亮点（market_brief类型可选）"
    })),

    // risk_warning 参数
    warning: Type.Optional(Type.String({ description: "警告内容（risk_warning类型必填）" })),
    severity: Type.Optional(Type.Union([
      Type.Literal("low"),
      Type.Literal("medium"),
      Type.Literal("high")
    ], { description: "严重程度（risk_warning类型必填）" })),
    details: Type.Optional(Type.String({ description: "详细说明（risk_warning类型可选）" })),
    suggestion: Type.Optional(Type.String({ description: "应对建议（risk_warning类型可选）" }))
  }),
  execute: async (toolCallId: string, params: any, signal: AbortSignal | undefined, onUpdate: any, ctx: any) => {
    try {
      const { type } = params;

      switch (type) {
        case "general":
          if (!params.message) {
            return {
              content: [{ type: "text" as const, text: JSON.stringify({ error: "general 类型需要 message 参数" }) }],
              details: null
            };
          }
          return await sendNotificationTool.execute(toolCallId, {
            message: params.message,
            title: params.title
          }, signal, onUpdate, ctx);

        case "trade_signal":
          if (!params.action || !params.symbol || !params.name || params.price == null || !params.reason || params.confidence == null) {
            return {
              content: [{ type: "text" as const, text: JSON.stringify({
                error: "trade_signal 类型需要 action, symbol, name, price, reason, confidence 参数"
              }) }],
              details: null
            };
          }
          // 主通知渠道
          const result = await sendTradeSignalTool.execute(toolCallId, {
            action: params.action,
            symbol: params.symbol,
            name: params.name,
            price: params.price,
            reason: params.reason,
            confidence: params.confidence,
            position_pct: params.position_pct
          }, signal, onUpdate, ctx);
          // 可选：额外发送飞书通知
          if (params.channel === "feishu") {
            try {
              await feishuService.sendTradeAlert({
                action: params.action,
                symbol: params.symbol,
                name: params.name,
                price: params.price,
                reason: params.reason,
                confidence: params.confidence,
                position_pct: params.position_pct
              });
              console.log("[monitor_alert] 已额外发送飞书通知");
            } catch (feishuError) {
              console.error("[monitor_alert] 飞书通知发送失败:", feishuError);
            }
          }
          return result;

        case "market_brief":
          if (!params.summary || !params.indices) {
            return {
              content: [{ type: "text" as const, text: JSON.stringify({
                error: "market_brief 类型需要 summary, indices 参数"
              }) }],
              details: null
            };
          }
          return await sendMarketBriefTool.execute(toolCallId, {
            summary: params.summary,
            indices: params.indices,
            highlights: params.highlights
          }, signal, onUpdate, ctx);

        case "risk_warning":
          if (!params.warning || !params.severity) {
            return {
              content: [{ type: "text" as const, text: JSON.stringify({
                error: "risk_warning 类型需要 warning, severity 参数"
              }) }],
              details: null
            };
          }
          return await sendRiskWarningTool.execute(toolCallId, {
            warning: params.warning,
            severity: params.severity,
            details: params.details,
            suggestion: params.suggestion
          }, signal, onUpdate, ctx);

        default:
          return {
            content: [{ type: "text" as const, text: JSON.stringify({
              error: `未知通知类型: ${type}`,
              valid_types: ["general", "trade_signal", "market_brief", "risk_warning"]
            }) }],
            details: null
          };
      }
    } catch (e) {
      return {
        content: [{ type: "text" as const, text: JSON.stringify({
          error: e instanceof Error ? e.message : String(e)
        }) }],
        details: null
      };
    }
  }
};
