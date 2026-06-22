/**
 * Notification Tools - 通知工具集
 */
import type { ToolDefinition } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { NotificationService } from "../../../services/notification/notification-service.js";
import type { NotificationMessage } from "../../../services/notification/notification-channel.js";

let notificationService: NotificationService | null = null;

/**
 * 初始化通知服务
 */
export function initNotificationService(): NotificationService {
  if (!notificationService) {
    notificationService = new NotificationService();
  }
  return notificationService;
}

/**
 * 获取通知服务实例
 */
export function getNotificationService(): NotificationService {
  if (!notificationService) {
    throw new Error('NotificationService not initialized. Call initNotificationService() first.');
  }
  return notificationService;
}

/**
 * 通用通知工具
 */
export const sendNotificationTool: ToolDefinition = {
  name: "send_notification",
  label: "发送通知",
  description: "发送通用通知消息",
  parameters: Type.Object({
    message: Type.String({ description: "通知内容" }),
    title: Type.Optional(Type.String({ description: "通知标题" }))
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const service = getNotificationService();
      await service.send(params.message);

      return {
        content: [{
          type: 'text' as const,
          text: JSON.stringify({
            success: true,
            message: '通知已发送'
          })
        }],
        details: null
      };
    } catch (error) {
      return {
        content: [{
          type: 'text' as const,
          text: JSON.stringify({
            success: false,
            error: error instanceof Error ? error.message : String(error)
          })
        }],
        details: null
      };
    }
  }
};

/**
 * 交易信号工具
 */
export const sendTradeSignalTool: ToolDefinition = {
  name: "send_trade_signal",
  label: "发送交易信号",
  description: "发送买入/卖出交易信号通知",
  parameters: Type.Object({
    action: Type.Union([Type.Literal("buy"), Type.Literal("sell")], {
      description: "交易动作"
    }),
    symbol: Type.String({ description: "股票代码" }),
    name: Type.String({ description: "股票名称" }),
    price: Type.Number({ description: "当前价格" }),
    reason: Type.String({ description: "交易理由" }),
    confidence: Type.Number({
      minimum: 0,
      maximum: 1,
      description: "信号置信度 (0-1)"
    }),
    position_pct: Type.Optional(Type.Number({
      description: "建议仓位百分比"
    }))
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const service = getNotificationService();

      const actionText = params.action === 'buy' ? '买入' : '卖出';
      const confidencePct = (params.confidence * 100).toFixed(1);

      let content = `**股票**: ${params.symbol} ${params.name}\n`;
      content += `**价格**: ¥${params.price.toFixed(2)}\n`;
      content += `**置信度**: ${confidencePct}%\n`;

      if (params.position_pct !== undefined) {
        content += `**建议仓位**: ${params.position_pct}%\n`;
      }

      content += `\n**理由**: ${params.reason}`;

      const message: NotificationMessage = {
        title: `🔔 ${actionText}信号`,
        content,
        type: 'card',
        metadata: params
      };

      await service.sendCard(message);

      return {
        content: [{
          type: 'text' as const,
          text: JSON.stringify({
            success: true,
            message: `${actionText}信号已发送`
          })
        }],
        details: null
      };
    } catch (error) {
      return {
        content: [{
          type: 'text' as const,
          text: JSON.stringify({
            success: false,
            error: error instanceof Error ? error.message : String(error)
          })
        }],
        details: null
      };
    }
  }
};

/**
 * 市场简报工具
 */
export const sendMarketBriefTool: ToolDefinition = {
  name: "send_market_brief",
  label: "发送市场简报",
  description: "发送市场概况和指数摘要",
  parameters: Type.Object({
    summary: Type.String({ description: "市场概况总结" }),
    indices: Type.Record(
      Type.String(),
      Type.Object({
        value: Type.Number({ description: "指数点位" }),
        change: Type.Number({ description: "涨跌幅百分比" })
      }),
      { description: "指数数据，key为指数名称" }
    ),
    highlights: Type.Optional(Type.Array(Type.String(), {
      description: "市场亮点"
    }))
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const service = getNotificationService();

      let content = `${params.summary}\n\n`;

      // 添加指数信息
      content += '**主要指数**:\n';
      for (const [name, data] of Object.entries(params.indices as Record<string, any>)) {
        const changeSign = data.change >= 0 ? '+' : '';
        content += `- ${name}: ${data.value.toFixed(2)} (${changeSign}${data.change.toFixed(1)}%)\n`;
      }

      // 添加亮点
      if (params.highlights && params.highlights.length > 0) {
        content += '\n**市场亮点**:\n';
        for (const highlight of params.highlights) {
          content += `- ${highlight}\n`;
        }
      }

      const message: NotificationMessage = {
        title: '📊 市场简报',
        content,
        type: 'card',
        metadata: params
      };

      await service.sendCard(message);

      return {
        content: [{
          type: 'text' as const,
          text: JSON.stringify({
            success: true,
            message: '市场简报已发送'
          })
        }],
        details: null
      };
    } catch (error) {
      return {
        content: [{
          type: 'text' as const,
          text: JSON.stringify({
            success: false,
            error: error instanceof Error ? error.message : String(error)
          })
        }],
        details: null
      };
    }
  }
};

/**
 * 风险警告工具
 */
export const sendRiskWarningTool: ToolDefinition = {
  name: "send_risk_warning",
  label: "发送风险警告",
  description: "发送风险提示和警告信息",
  parameters: Type.Object({
    warning: Type.String({ description: "警告内容" }),
    severity: Type.Union([
      Type.Literal("low"),
      Type.Literal("medium"),
      Type.Literal("high")
    ], { description: "严重程度" }),
    details: Type.Optional(Type.String({ description: "详细说明" })),
    suggestion: Type.Optional(Type.String({ description: "应对建议" }))
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const service = getNotificationService();

      const severityMap = {
        low: '低',
        medium: '中',
        high: '高'
      };

      let content = `**警告**: ${params.warning}\n`;
      content += `**严重程度**: ${severityMap[params.severity as keyof typeof severityMap]}\n`;

      if (params.details) {
        content += `\n**详情**: ${params.details}\n`;
      }

      if (params.suggestion) {
        content += `\n**建议**: ${params.suggestion}\n`;
      }

      const message: NotificationMessage = {
        title: '⚠️ 风险警告',
        content,
        type: 'card',
        metadata: params
      };

      await service.sendCard(message);

      return {
        content: [{
          type: 'text' as const,
          text: JSON.stringify({
            success: true,
            message: '风险警告已发送'
          })
        }],
        details: null
      };
    } catch (error) {
      return {
        content: [{
          type: 'text' as const,
          text: JSON.stringify({
            success: false,
            error: error instanceof Error ? error.message : String(error)
          })
        }],
        details: null
      };
    }
  }
};

/**
 * 导出所有通知工具
 */
export const notificationTools: ToolDefinition[] = [
  sendNotificationTool,
  sendTradeSignalTool,
  sendMarketBriefTool,
  sendRiskWarningTool
];
