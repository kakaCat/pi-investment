import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { readFileSync } from 'node:fs';

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
    // 飞书 webhook 直配（渠道 code → webhook URL）。
    // 2026-08-21：Agent OS 进程会挂/通知路由只记录不投递，关键通知链路不能依赖它。
    feishuWebhooks: z.any().default({}),
  }).default({} as any)

  private aos: AgentOSClient;
  private aosBaseURL: string;
  private feishuWebhooks: Record<string, string>;
  private agentSign: string;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'notification');
    this.aosBaseURL = config.agentOS?.baseURL || 'http://localhost:8080';
    this.feishuWebhooks = (config as any).feishuWebhooks || {};
    this.agentSign = this.loadAgentSign((config as any).agentsFile);
    this.aos = new AgentOSClient({
      baseURL: this.aosBaseURL,
      agentId: config.agentOS?.agentId || 'agent-dh',
    });
    this.registerTools();
  }

  /**
   * 通知署名（2026-08-21 身份系统）：所有外发通知带上 agent 名字+ID，
   * 用户能一眼看出是哪个分身发的。读 agents.json 的 primary 身份。
   */
  private loadAgentSign(file?: string): string {
    const fallback = 'PI 投资顾问·投资脑 (investor)';
    try {
      const p = (file || '~/.dsh/profiles/investment/agents.json').replace(/^~/, process.env.HOME || '');
      const registry = JSON.parse(readFileSync(p, 'utf-8'));
      const primary = (registry.agents || []).find((a: any) => a.primary) || (registry.agents || [])[0];
      return primary ? `${primary.name} (${primary.id})` : fallback;
    } catch {
      return fallback;
    }
  }

  private sign(content: string): string {
    return `${content}\n\n—— ${this.agentSign}`;
  }

  /**
   * 直发飞书（降级兜底路径，方案 C）：主路径 Agent OS 失败/不可达时使用。
   * webhook 解析顺序：①插件配置 feishuWebhooks（无中间层依赖，Agent OS 全挂也能发）
   * ②Agent OS 渠道 API（配置单一事实源）。以飞书返回 code=0 为真实送达依据。
   */
  private async sendFeishuDirect(channelCode: string, title: string, content: string, urgency: string): Promise<any> {
    // 1. 解析 webhook：配置优先，Agent OS API 回退
    let webhook = this.feishuWebhooks[channelCode] || this.feishuWebhooks['*'];
    let webhookSource = webhook ? 'config' : '';
    if (!webhook) {
      try {
        const res = await fetch(`${this.aosBaseURL}/api/v1/notifications/channels`);
        if (res.ok) {
          const data: any = await res.json();
          const channel = (data?.channels || []).find((c: any) => c.code === channelCode && c.enabled);
          webhook = channel?.config?.webhook;
          webhookSource = webhook ? 'agent_os_api' : '';
        }
      } catch { /* Agent OS 不可达，落到错误处理 */ }
    }
    if (!webhook) {
      throw new Error(`渠道 ${channelCode} 无可用 webhook（配置与 Agent OS API 均无）。请在 cordis.patch.yml 的 notification.feishuWebhooks 配置`);
    }

    // 2. 直发飞书自定义机器人（interactive 卡片支持 markdown）
    const template = urgency === 'high' ? 'red' : urgency === 'low' ? 'grey' : 'blue';
    const resp = await fetch(webhook, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        msg_type: 'interactive',
        card: {
          header: { title: { tag: 'plain_text', content: title }, template },
          elements: [{ tag: 'div', text: { tag: 'lark_md', content } }],
        },
      }),
    });
    const result: any = await resp.json().catch(() => ({}));
    if (!resp.ok || (result.code !== undefined && result.code !== 0)) {
      throw new Error(`飞书投递失败：HTTP ${resp.status} ${JSON.stringify(result).slice(0, 200)}`);
    }
    return {
      success: true,
      channel: channelCode,
      delivery: 'feishu_direct',
      webhook_source: webhookSource,
      feishu_code: result.code ?? 0,
      message: '已直发飞书（code=0 确认送达）',
    };
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
        // 渠道路由：显式 channel 优先，否则按 urgency 分流
        const urgency = args.urgency || 'normal';
        const channel = args.channel || (urgency === 'high' ? 'alerts' : 'reports');
        const content = this.sign(args.content);  // 身份署名（哪个 agent 发的）
        // 2026-08-21 方案 C（用户裁决）：主路径走 Agent OS API（真实发送 + 系统记录/审计日志，
        // 路由 bug 已由 1d6cab3e 修复）；Agent OS 失败时降级为直发飞书 webhook 兜底，
        // 兜底结果标记 degraded=true（事后可审计"走了旁路"）。
        try {
          const result: any = await aos.notification.send({
            channel,
            title: args.title,
            content,
            urgency,
          });
          if (result?.success === false) {
            throw new Error(result?.error || 'Agent OS 返回 success=false');
          }
          return { ...result, channel, delivery: 'agent_os' } as any;
        } catch (e: any) {
          const fallback = await this.sendFeishuDirect(channel, args.title, content, urgency);
          return { ...fallback, degraded: true, fallback_reason: String(e?.message ?? e) } as any;
        }
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
        // feishu 渠道：同 feishu_notify 的方案 C（Agent OS 主路径 + 直发兜底）；
        // webhook/email 渠道仍走 Agent OS
        if (args.channel === 'feishu') {
          const urgency = args.urgency || 'normal';
          const channelCode = urgency === 'high' ? 'alerts' : 'reports';
          const content = this.sign(args.content);  // 身份署名
          try {
            const result: any = await aos.notification.send({
              channel: channelCode,
              title: args.title,
              content,
              urgency,
            });
            if (result?.success === false) throw new Error(result?.error || 'success=false');
            return { ...result, channel: channelCode, delivery: 'agent_os' } as any;
          } catch (e: any) {
            const fallback = await this.sendFeishuDirect(channelCode, args.title, content, urgency);
            return { ...fallback, degraded: true, fallback_reason: String(e?.message ?? e) } as any;
          }
        }
        const result: any = await aos.notification.send({
          channel: args.channel,
          title: args.title,
          content: this.sign(args.content),  // 身份署名
          urgency: args.urgency || 'normal',
        });
        return result as any;
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
