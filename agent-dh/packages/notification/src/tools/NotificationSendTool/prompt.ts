/**
 * NotificationSendTool 参数类型
 */
export interface NotificationSendParams {
  channel: 'feishu' | 'webhook' | 'email';
  title: string;
  content: string;
  urgency?: 'low' | 'normal' | 'high';
}

/**
 * NotificationSendTool 返回结果类型
 */
export interface NotificationSendResult {
  success: boolean;
  channel: string;
  delivery: string;
  message_id?: string;
  degraded?: boolean;
  fallback_reason?: string;
  webhook_source?: string;
  feishu_code?: number;
  message?: string;
}

/**
 * NotificationSendTool 的提示词定义
 */
export const notificationSendPrompt = {
  name: 'notification_send',
  description: '发送通知到指定渠道（写操作，用户会真实收到消息）。适用于：需要飞书以外渠道（webhook/邮件）时；发飞书直接用 feishu_notify 更简洁。仅在有实际价值的信息时发送，避免频繁打扰。',
  parameters: {
    channel: {
      type: 'string',
      description: '通知渠道。feishu：飞书；webhook：自定义 Webhook；email：邮件',
      enum: ['feishu', 'webhook', 'email'],
      required: true,
    },
    title: {
      type: 'string',
      description: '消息标题，简明扼要',
      required: true,
    },
    content: {
      type: 'string',
      description: '消息正文',
      required: true,
    },
    urgency: {
      type: 'string',
      description: '紧急程度。low：普通备忘；normal（默认）：一般通知；high：紧急，触发强提醒，仅用于需要立即关注的事项',
      enum: ['low', 'normal', 'high'],
      default: 'normal',
    },
  },
  examples: [
    {
      title: '飞书渠道示例',
      params: {
        channel: 'feishu',
        title: '系统通知',
        content: '测试消息',
        urgency: 'normal',
      },
      expectedResult: '成功发送通知到飞书',
    },
    {
      title: 'Webhook 渠道示例',
      params: {
        channel: 'webhook',
        title: '数据同步完成',
        content: '已成功同步 1000 条数据',
        urgency: 'low',
      },
      expectedResult: '成功发送通知到 webhook',
    },
    {
      title: '邮件渠道示例',
      params: {
        channel: 'email',
        title: '每周报告',
        content: '本周收益率：+3.5%',
        urgency: 'low',
      },
      expectedResult: '成功发送邮件通知',
    },
  ],
};
