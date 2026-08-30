/**
 * Scheduler Plugin - Task Scheduling
 * 任务调度管理：定时任务、周期任务
 */
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { SchedulerManageTool } from './tools/SchedulerManageTool';

export interface Config {
  agentOS?: {
    baseURL?: string;
    agentId?: string;
  };
}

/**
 * Scheduler Plugin for Agent-DH
 *
 * Task scheduling via Agent OS Scheduler API (/api/v1/scheduler),
 * through the shared AgentOSClient.scheduler (SchedulerClient).
 */
export default class SchedulerPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
      agentId: z.string().default('agent-dh'),
    }).default({} as any),
  }).default({} as any)

  private aos: AgentOSClient;
  private owner: string;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'scheduler');
    this.aos = new AgentOSClient({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
    });
    this.owner = config.agentOS?.agentId || 'agent-dh';
    this.registerTools();
  }

  private registerTools() {
    const { ctx, aos } = this;

    // 调度器管理（重构为 BaseTool，需要通过 defineTool 包装）
    const tool = new SchedulerManageTool(aos);
    ctx.tools.register(tool.toDSHToolDefinition());
  }
}
