/**
 * FeishuNotifyTool 参数类型
 */
export interface FeishuNotifyParams {
  title: string;
  content: string;
  urgency?: 'low' | 'normal' | 'high';
  channel?: string;
}

/**
 * FeishuNotifyTool 返回结果类型
 */
export interface FeishuNotifyResult {
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
 * FeishuNotifyTool 的提示词定义
 */
export const feishuNotifyPrompt = {
  name: 'feishu_notify',
  description: '发送飞书通知（写操作，用户会真实收到消息）。适用于：交易信号、风险提示、每日报告等重要事项。渠道路由：默认按 urgency 自动分流（high→alerts 告警群，normal/low→reports 报告群），也可用 channel 参数显式指定。仅在有实际价值的信息时发送，避免频繁打扰；一般性记录写入 memory_write 即可。需要其他渠道（webhook/邮件）时用 notification_send。',
  parameters: {
    title: {
      type: 'string',
      description: '消息标题，简明扼要，如 【买入信号】贵州茅台',
      required: true,
    },
    content: {
      type: 'string',
      description: '消息正文，支持 Markdown 格式',
      required: true,
    },
    urgency: {
      type: 'string',
      description: '紧急程度。low：普通备忘；normal（默认）：一般通知；high：紧急，会触发强提醒，仅用于需要立即关注的事项',
      enum: ['low', 'normal', 'high'],
      default: 'normal',
    },
    channel: {
      type: 'string',
      description: '显式指定 Agent OS 渠道 code（如 alerts=告警群 / reports=报告群）。不传则按 urgency 自动分流：high→alerts，normal/low→reports',
    },
  },
  examples: [
    {
      title: '正常通知示例',
      params: {
        title: '【买入信号】贵州茅台',
        content: '信号时间：2024-01-15 14:30\n价格：1850.00\n理由：突破前期高点',
        urgency: 'normal',
      },
      expectedResult: '成功发送飞书通知到 reports 渠道',
    },
    {
      title: '紧急通知示例',
      params: {
        title: '【风险警告】触发止损',
        content: '持仓：贵州茅台\n当前价格：1750.00\n跌幅：-5.4%\n建议：立即止损',
        urgency: 'high',
      },
      expectedResult: '成功发送紧急通知到 alerts 渠道',
    },
    {
      title: '指定渠道示例',
      params: {
        title: '每日复盘报告',
        content: '今日盈亏：+1.2%\n胜率：65%',
        urgency: 'low',
        channel: 'reports',
      },
      expectedResult: '成功发送通知到指定的 reports 渠道',
    },
  ],
};
