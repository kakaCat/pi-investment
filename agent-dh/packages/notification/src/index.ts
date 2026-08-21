import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { AgentOSClient } from '@pi-investment/agent-os-client';

export interface Config {
  agentOS?: {
    baseURL?: string;
    agentId?: string;
  };
}

/**
 * Notification Plugin for Agent-DH
 *
 * Send notifications via Agent OS (Feishu, webhook, etc.)
 */
export default class NotificationPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
      agentId: z.string().default('agent-dh'),
    }).default({} as any),
  }).default({} as any)

  private aos: AgentOSClient;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'notification');
    this.aos = new AgentOSClient({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
      agentId: config.agentOS?.agentId || 'agent-dh',
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, aos } = this;

    // 飞书通知
    ctx.tools.register(defineTool({
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
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean', description: '是否发送成功' },
            message_id: { type: 'string', description: '消息ID' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        // 2026-08-21 渠道路由：显式 channel 优先，否则按 urgency 分流
        // （修复"永远落到第一个 enabled channel"导致的日报/告警混发）
        const urgency = args.urgency || 'normal';
        const channel = args.channel || (urgency === 'high' ? 'alerts' : 'reports');
        return aos.notification.send({
          title: args.title,
          content: args.content,
          urgency,
          channel,
        }) as any;
      },
    } as any));

    // 通用通知
    ctx.tools.register(defineTool({
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
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean', description: '是否发送成功' },
            channel: { type: 'string', description: '发送渠道' },
            message_id: { type: 'string', description: '消息ID' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return aos.notification.send({
          channel: args.channel,
          title: args.title,
          content: args.content,
          urgency: args.urgency || 'normal',
        }) as any;
      },
    } as any));

    // 通知渠道自检（2026-08-21）：渠道清单 + 投递状态可见性
    ctx.tools.register(defineTool({
      name: 'notification_channels',
      description: '查看通知渠道清单与投递状态：已配置的渠道（code/名称/启用/webhook 脱敏）、最近投递日志（状态 pending/sent/failed + 所属渠道）、状态统计。适用于：发重要通知前确认渠道配置、排查"消息没收到"（如日报未达时先看这里）、feishu_notify 选 channel 参数。',
      parameters: {
        log_limit: {
          type: 'number',
          description: '返回最近投递日志条数，默认 10',
          default: 10,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            channels: { type: 'array', items: { type: 'object', additionalProperties: true } },
            recent_logs: { type: 'array', items: { type: 'object', additionalProperties: true } },
            status_summary: { type: 'object', additionalProperties: true },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        const [channelsRes, logsRes] = await Promise.all([
          aos.notification.listChannels(),
          aos.notification.listLogs(args.log_limit ?? 10),
        ]);
        const channels = channelsRes.channels || [];
        const codeById = new Map(channels.map((c: any) => [c.id, c.code]));

        const maskHook = (hook?: string) =>
          hook ? hook.slice(0, 45) + '...' + hook.slice(-6) : null;

        const logs = (logsRes.logs || []).map((l: any) => ({
          title: l.title ?? null,
          status: l.status ?? null,
          channel: codeById.get(l.channel_id) ?? l.channel_id ?? null,
          created_at: l.created_at ?? null,
        }));

        const statusSummary: Record<string, number> = {};
        for (const l of logs) {
          const st = l.status ?? 'unknown';
          statusSummary[st] = (statusSummary[st] ?? 0) + 1;
        }

        return {
          channels: channels.map((c: any) => ({
            code: c.code,
            name: c.name ?? null,
            enabled: c.enabled !== false,
            webhook: maskHook(c.config?.webhook),
          })),
          recent_logs: logs,
          status_summary: statusSummary,
        } as any;
      },
    } as any));
  }
}
