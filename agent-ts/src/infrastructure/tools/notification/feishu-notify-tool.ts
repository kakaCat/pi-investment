/**
 * 飞书通知工具
 * Agent 通过此工具推送飞书消息给用户
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
// @ts-ignore - Module stub needed
import { getFeishuService } from "../../../services/feishu-notification.service.ts/feishu-notification-service.js";

export const feishuNotifyTool: ToolDefinition = {
  name: "feishu_notify",
  label: "飞书通知",
  description: `发送飞书通知给用户。

支持的消息类型:
- text: 纯文本消息
- card: 富文本卡片（支持 Markdown）
- daily_report: 每日投资报告
- weekly_report: 每周投资报告
- alert: 告警通知（市场异动、持仓告警等）
- premarket_report: 盘前准备报告

使用场景:
1. 每日报告推送
2. 市场异动通知
3. 持仓止损/止盈提醒
4. 交易信号推送
5. 风险预警`,

  parameters: Type.Object({
    messageType: Type.Union([
      Type.Literal('text'),
      Type.Literal('card'),
      Type.Literal('daily_report'),
      Type.Literal('weekly_report'),
      Type.Literal('alert'),
      Type.Literal('premarket_report')
    ], { description: "消息类型" }),

    title: Type.Optional(Type.String({ description: "卡片标题（card/alert 类型需要）" })),

    content: Type.String({ description: "消息内容，支持 Markdown 格式" }),

    urgency: Type.Optional(Type.Union([
      Type.Literal('normal'),
      Type.Literal('high'),
      Type.Literal('critical')
    ], { description: "紧急程度：normal=普通, high=重要, critical=紧急", default: 'normal' })),

    data: Type.Optional(Type.Record(Type.String(), Type.Any(), {
      description: "额外数据，用于 daily_report/weekly_report 等特定类型"
    })),

    actionButtons: Type.Optional(Type.Array(Type.Object({
      label: Type.String({ description: "按钮文本" }),
      url: Type.Optional(Type.String({ description: "跳转链接" })),
      action: Type.Optional(Type.String({ description: "动作类型" }))
    }), { description: "操作按钮列表" })),

    mentionUser: Type.Optional(Type.Boolean({
      description: "是否 @ 用户",
      default: false
    })),

    silent: Type.Optional(Type.Boolean({
      description: "是否静默发送（不推送通知）",
      default: false
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const {
        messageType,
        title,
        content,
        urgency = 'normal',
        data,
        actionButtons,
        mentionUser = false,
        silent = false
      } = params;

      console.log(`[FeishuNotify] Sending ${messageType} message, urgency: ${urgency}`);

      const feishuService = getFeishuService();

      if (!feishuService) {
        console.warn('[FeishuNotify] Feishu service not available');
        return {
          content: [{ type: "text" as const, text: '飞书服务未配置' }],
          details: {
            success: false,
            message: '飞书服务未配置'
          }
        };
      }

      let result = false;

      switch (messageType) {
        case 'text':
          result = await feishuService.sendText(content, mentionUser);
          break;

        case 'card':
          if (!title) {
            throw new Error('Card message requires title');
          }
          result = await feishuService.sendCard({
            title,
            content,
            urgency,
            actions: actionButtons
          });
          break;

        case 'daily_report':
          if (!data) {
            throw new Error('Daily report requires data');
          }
          result = await feishuService.sendDailyReport(data);
          break;

        case 'weekly_report':
          if (!data) {
            throw new Error('Weekly report requires data');
          }
          result = await feishuService.sendWeeklyReport(data);
          break;

        case 'alert':
          if (!title) {
            throw new Error('Alert message requires title');
          }
          result = await feishuService.sendAlert({
            title,
            content,
            urgency,
            actions: actionButtons,
            mentionUser
          });
          break;

        case 'premarket_report':
          if (!data) {
            throw new Error('Premarket report requires data');
          }
          result = await feishuService.sendPremarketReport(data);
          break;

        default:
          throw new Error(`Unknown message type: ${messageType}`);
      }

      if (result) {
        console.log(`[FeishuNotify] Message sent successfully: ${messageType}`);
        const successMsg = '飞书通知已发送';
        return {
          content: [{ type: "text" as const, text: successMsg }],
          details: {
            success: true,
            message: successMsg,
            messageType,
            timestamp: new Date().toISOString()
          }
        };
      } else {
        console.warn(`[FeishuNotify] Failed to send message: ${messageType}`);
        const errorMsg = '飞书通知发送失败';
        return {
          content: [{ type: "text" as const, text: errorMsg }],
          details: {
            success: false,
            message: errorMsg
          }
        };
      }

    } catch (error) {
      console.error('[FeishuNotify] Error:', error);
      const errorMsg = '飞书通知发送失败';
      const errorDetail = error instanceof Error ? error.message : 'Unknown error';
      return {
        content: [{ type: "text" as const, text: `${errorMsg}: ${errorDetail}` }],
        details: {
          success: false,
          message: errorMsg,
          error: errorDetail
        }
      };
    }
  }
};
