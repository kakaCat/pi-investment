import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { createEvolutionRunTool } from './tools/EvolutionRunTool';
import { createEvolutionLeaderboardTool } from './tools/EvolutionLeaderboardTool';

export interface Config {
  agentOS?: {
    baseURL?: string;
    agentId?: string;
  };
}

/**
 * Evolution Plugin for Agent-DH
 *
 * Strategy evolution and self-improvement via Agent OS.
 */
export default class EvolutionPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
      agentId: z.string().default('agent-dh'),
    }).default({} as any),
  }).default({} as any);

  private aos: AgentOSClient;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'evolution');
    this.aos = new AgentOSClient({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
      agentId: config.agentOS?.agentId || 'agent-dh',
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, aos } = this;

    // 注册进化运行工具
    ctx.tools.register(createEvolutionRunTool(aos));

    // 注册进化排行榜工具
    ctx.tools.register(createEvolutionLeaderboardTool(aos));
  }
}
