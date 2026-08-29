/**
 * NotificationChannelsTool 参数类型
 */
export interface NotificationChannelsParams {
  log_limit?: number;
}

/**
 * NotificationChannelsTool 返回结果类型
 */
export interface NotificationChannelsResult {
  channels: Array<{
    code: string;
    name: string | null;
    enabled: boolean;
    webhook: string | null;
  }>;
  recent_logs: Array<{
    title: string | null;
    status: string | null;
    channel: string | null;
    created_at: string | null;
  }>;
  status_summary: Record<string, number>;
}

/**
 * NotificationChannelsTool 的提示词定义
 */
export const notificationChannelsPrompt = {
  name: 'notification_channels',
  description: '查看通知渠道清单与投递状态：已配置的渠道（code/名称/启用/webhook 脱敏）、最近投递日志（状态 pending/sent/failed + 所属渠道）、状态统计。适用于：发重要通知前确认渠道配置、排查"消息没收到"（如日报未达时先看这里）、feishu_notify 选 channel 参数。',
  parameters: {
    log_limit: {
      type: 'number',
      description: '返回最近投递日志条数，默认 10',
      default: 10,
    },
  },
  examples: [
    {
      title: '查看默认数量的日志',
      params: {},
      expectedResult: '返回渠道清单和最近 10 条投递日志',
    },
    {
      title: '查看更多日志',
      params: {
        log_limit: 20,
      },
      expectedResult: '返回渠道清单和最近 20 条投递日志',
    },
  ],
};
