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
  output: {
    schema: {
      type: 'object',
      properties: {
        channels: {
          type: 'array',
          description: '已配置渠道清单',
          items: {
            type: 'object',
            properties: {
              code: { type: 'string', description: '渠道代码' },
              name: { type: 'string', description: '渠道名称（可选）' },
              enabled: { type: 'boolean', description: '是否启用' },
              webhook: { type: 'string', description: 'webhook 地址（脱敏，可选）' },
            },
            additionalProperties: true,
          },
        },
        recent_logs: {
          type: 'array',
          description: '最近投递日志',
          items: {
            type: 'object',
            properties: {
              title: { type: 'string', description: '消息标题（可选）' },
              status: { type: 'string', description: '状态 pending/sent/failed（可选）' },
              channel: { type: 'string', description: '投递渠道（可选）' },
              created_at: { type: 'string', description: '创建时间（可选）' },
            },
            additionalProperties: true,
          },
        },
        status_summary: {
          type: 'object',
          description: '按状态统计的投递数量',
          additionalProperties: true,
        },
      },
      additionalProperties: true,
    },
    render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },
};
