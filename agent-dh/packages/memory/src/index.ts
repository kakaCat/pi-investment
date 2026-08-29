import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { createMemorySearchTool } from './tools/MemorySearchTool';
import { createMemoryWriteTool } from './tools/MemoryWriteTool';
import { createExperienceWriteTool } from './tools/ExperienceWriteTool';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
  /** Agent OS 配置 */
  agentOS?: {
    baseURL?: string;
    agentId?: string;
  };
}

/**
 * Memory Plugin for Agent-DH
 *
 * Long-term memory storage and retrieval via Agent OS 记忆库
 * （2026-08-25 起：quantsys-v2 记忆库写入停用，统一迁移 Agent OS /api/v1/memory，
 *  postgres 持久；经 @pi-investment/agent-os-client，title+content 文本检索）。
 *
 * 2026-08-19: 从已废弃的 agent-os 客户端迁移到 quantsys-v2。
 * 2026-08-25: quantsys-v2 记忆库写入挂起（ollama embedding 超时），迁回 Agent OS。
 * 2026-08-28: 迁移到 agent-os-client（os-memory 已废弃）。
 */
export default class MemoryPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
      agentId: z.string().default('agent-dh'),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;
  private aos: AgentOSClient;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'memory');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    // 2026-08-25：quantsys-v2 记忆库写入停用，记忆读写迁 Agent OS
    // 2026-08-28：迁移到 agent-os-client
    this.aos = new AgentOSClient({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
      agentId: config.agentOS?.agentId || 'agent-dh'
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, aos } = this;

    // 注册记忆搜索工具
    ctx.tools.register(createMemorySearchTool(aos.memory));

    // 注册记忆写入工具
    ctx.tools.register(createMemoryWriteTool(aos.memory));

    // 注册经验写入工具
    ctx.tools.register(createExperienceWriteTool(aos.memory));
  }
}

// Re-export tools for testing
export { MemorySearchTool, createMemorySearchTool } from './tools/MemorySearchTool';
export { MemoryWriteTool, createMemoryWriteTool } from './tools/MemoryWriteTool';
export { ExperienceWriteTool, createExperienceWriteTool } from './tools/ExperienceWriteTool';
export type { MemorySearchParams, MemorySearchResult } from './tools/MemorySearchTool';
export type { MemoryWriteParams, MemoryWriteResult } from './tools/MemoryWriteTool';
export type { ExperienceWriteParams, ExperienceWriteResult } from './tools/ExperienceWriteTool';
