import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { readFileSync } from 'node:fs';
import { createFeishuNotifyTool } from './tools/FeishuNotifyTool';
import { createNotificationSendTool } from './tools/NotificationSendTool';
import { createNotificationChannelsTool } from './tools/NotificationChannelsTool';

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

  private registerTools() {
    const { ctx, aos, agentSign, feishuWebhooks, aosBaseURL } = this;

    // 注册飞书通知工具
    ctx.tools.register(createFeishuNotifyTool(aos, agentSign, feishuWebhooks, aosBaseURL));

    // 注册通用通知工具
    ctx.tools.register(createNotificationSendTool(aos, agentSign, feishuWebhooks, aosBaseURL));

    // 注册通知渠道查询工具
    ctx.tools.register(createNotificationChannelsTool(aos));
  }
}

// 导出工具类型
export { FeishuNotifyTool } from './tools/FeishuNotifyTool';
export { NotificationSendTool } from './tools/NotificationSendTool';
export { NotificationChannelsTool } from './tools/NotificationChannelsTool';
