import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';
import { createMemorySearchTool } from './tools/MemorySearchTool';
import { createMemoryWriteTool } from './tools/MemoryWriteTool';
import { createExperienceWriteTool } from './tools/ExperienceWriteTool';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
  /** 已废弃：历史 agent-os 配置，仅为兼容旧配置文件保留，不再使用 */
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
 *  postgres 持久；经 @pi-investment/os-memory 适配器，title+content 文本检索）。
 *
 * 2026-08-19: 从已废弃的 agent-os 客户端迁移到 quantsys-v2。
 * 2026-08-25: quantsys-v2 记忆库写入挂起（ollama embedding 超时），迁回 Agent OS。
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
  private osMemory: OsMemoryStore;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'memory');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    // 2026-08-25：quantsys-v2 记忆库写入停用，记忆读写迁 Agent OS
    this.osMemory = new OsMemoryStore({
      baseURL: (config as any).agentOS?.baseURL || 'http://localhost:8080',
      agentId: (config as any).agentOS?.agentId || 'agent-dh'
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, osMemory } = this;

    // 注册记忆搜索工具
    ctx.tools.register(createMemorySearchTool(osMemory));

    // 注册记忆写入工具
    ctx.tools.register(createMemoryWriteTool(osMemory));

    // 注册经验写入工具
    ctx.tools.register(createExperienceWriteTool(osMemory));
  }
}

// Re-export tools for testing
export { MemorySearchTool, createMemorySearchTool } from './tools/MemorySearchTool';
export { MemoryWriteTool, createMemoryWriteTool } from './tools/MemoryWriteTool';
export { ExperienceWriteTool, createExperienceWriteTool } from './tools/ExperienceWriteTool';
export type { MemorySearchParams, MemorySearchResult } from './tools/MemorySearchTool';
export type { MemoryWriteParams, MemoryWriteResult } from './tools/MemoryWriteTool';
export type { ExperienceWriteParams, ExperienceWriteResult } from './tools/ExperienceWriteTool';
