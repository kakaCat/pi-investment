/**
 * 飞书通知工具
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { getFeishuService } from "../../../services/feishu-notification.service.js";

export const feishuNotifyTool: ToolDefinition = {
  name: "feishu_notify",
  label: "飞书通知",
  description: `发送飞书通知给用户。支持文本、卡片、报告、告警等消息类型。`,

  parameters: Type.Object({
    messageType: Type.Union([
      Type.Literal('text'),
      Type.Literal('card'),
      Type.Literal('daily_report'),
      Type.Literal('weekly_report'),
      Type.Literal('alert'),
    ], { description: "消息类型" }),

    title: Type.Optional(Type.String({ description: "卡片标题" })),

    content: Type.String({ description: "消息内容，支持 Markdown 格式" }),

    urgency: Type.Optional(Type.Union([
      Type.Literal('normal'),
      Type.Literal('high'),
      Type.Literal('critical')
    ], { default: 'normal' })),

    data: Type.Optional(Type.Record(Type.String(), Type.Any())),

    actionButtons: Type.Optional(Type.Array(Type.Object({
      label: Type.String(),
      url: Type.Optional(Type.String()),
      action: Type.Optional(Type.String())
    }))),

    mentionUser: Type.Optional(Type.Boolean({ default: false })),
  }),

  execute: async (_toolCallId, params: any) => {
    const fs = await import('fs');
    fs.appendFileSync('/tmp/feishu_tool.log', `[${new Date().toISOString()}] 被调用: ${JSON.stringify(params).substring(0, 300)}\n`);
    try {
      const { messageType, title, content, urgency = 'normal', data, actionButtons, mentionUser } = params;

      const feishuService = getFeishuService();
      if (!feishuService?.isAvailable()) {
        return {
          content: [{ type: "text" as const, text: '飞书服务未配置' }],
          details: { success: false }
        };
      }

      let result = false;
      switch (messageType) {
        case 'text':
          result = await feishuService.sendText(content, mentionUser);
          break;
        case 'card':
          if (!title) throw new Error('Card message requires title');
          result = await feishuService.sendCard({ title, content, urgency, actions: actionButtons });
          break;
        case 'daily_report':
          if (!data) throw new Error('Daily report requires data');
          result = await feishuService.sendDailyReport(data);
          break;
        case 'weekly_report':
          if (!data) throw new Error('Weekly report requires data');
          result = await feishuService.sendWeeklyReport(data);
          break;
        case 'alert':
          if (!title) throw new Error('Alert requires title');
          result = await feishuService.sendAlert({ title, content, urgency, actions: actionButtons });
          break;
        default:
          throw new Error(`Unknown message type: ${messageType}`);
      }

      const msg = result ? '飞书通知已发送' : '飞书通知发送失败';
      fs.appendFileSync('/tmp/feishu_tool.log', `[${new Date().toISOString()}] 结果: ${msg}\n`);
      return {
        content: [{ type: "text" as const, text: msg }],
        details: { success: result }
      };
    } catch (error) {
      const err = error instanceof Error ? error.message : 'Unknown error';
      return {
        content: [{ type: "text" as const, text: `飞书通知发送失败: ${err}` }],
        details: { success: false, error: err }
      };
    }
  }
};
