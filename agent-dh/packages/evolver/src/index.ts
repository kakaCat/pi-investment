/**
 * Evolver Plugin - Prompt Evolution Engine
 * P1-2: 接收 experience_distill 建议，生成段更新提案，调用 genome_update 应用
 * P2 (RFC 008): 验证门——提案应用为 candidate 观察版，观察期后裁决转正/回滚
 */
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import {
  createPromptEvolverTool,
  createValidationGateTool,
  createDailyDistillTool,
  createWeeklyReportTool,
} from './tools';

/**
 * Minimal OsMemoryStore replacement (inlined from deleted @pi-investment/os-memory)
 * Wraps AgentOSClient to provide createMemory/searchMemory API
 */
export class OsMemoryStore {
  private client: AgentOSClient;
  private agentId: string;
  private baseURL: string;

  constructor(opts: { baseURL?: string; agentId?: string } = {}) {
    this.baseURL = opts.baseURL || 'http://localhost:8080';
    this.client = new AgentOSClient({
      baseURL: this.baseURL,
      agentId: opts.agentId || 'agent-dh',
    });
    this.agentId = opts.agentId || 'agent-dh';
  }

  async createMemory(entry: { kind: string; scope: string; title: string; content: string; payload?: any; status?: string; confidence?: number; source?: string; provenance?: any }): Promise<{ id: string }> {
    const category = entry.kind === 'experience' ? 'experience' : entry.kind === 'rule' ? 'knowledge' : entry.kind === 'decision' ? 'decision' : 'data';
    const envelope = { kind: entry.kind, scope: entry.scope, status: entry.status ?? 'testing', confidence: entry.confidence ?? 0.5, source: entry.source ?? 'agent', provenance: entry.provenance ?? null, payload: entry.payload ?? null, body: entry.content };
    const res: any = await (this.client.memory as any).write({ title: entry.title, content: JSON.stringify(envelope), category, tags: [entry.scope, `kind:${entry.kind}`, `agent:${this.agentId}`].filter(Boolean) });
    return { id: String(res?.id ?? res?.memory?.id ?? '') };
  }

  async searchMemory(params: { q?: string; kind?: string; scope?: string; limit?: number }): Promise<{ items: any[]; total: number; degraded: boolean; strategy: string }> {
    const q = params.q ?? '';
    const limit = params.limit ?? 20;
    const url = `${this.baseURL}/api/v1/memory/search?q=${encodeURIComponent(q || ' ')}&limit=${Math.min(limit * 3, 150)}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`OS memory search failed: HTTP ${resp.status}`);
    const res: any = await resp.json();
    const raw: any[] = res?.memories ?? res?.items ?? [];
    const items: any[] = [];
    for (const it of raw) {
      let env: any = null;
      try { env = typeof it.content === 'string' ? JSON.parse(it.content) : it.content; } catch { continue; }
      if (!env || typeof env !== 'object' || env.kind === undefined) continue;
      if (params.kind && env.kind !== params.kind) continue;
      if (params.scope && env.scope !== params.scope) continue;
      if (env.status === 'deprecated') continue;
      items.push({ id: it.id, kind: env.kind, scope: env.scope, title: it.title, content: env.body ?? '', payload: env.payload, status: env.status, confidence: env.confidence, source: env.source, provenance: env.provenance, created_at: it.created_at });
      if (items.length >= limit) break;
    }
    return { items, total: items.length, degraded: false, strategy: 'os-text' };
  }
}

/** 观察期候选记录（RFC 008 §3.3）——共享实现见 ./candidates.ts（2026-09-03 抽取） */

export default class EvolverPlugin extends Service {
  static inject = ['tools', 'genome', 'llm'];  // 依赖 genome 插件 + LLM（段落改写）

  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
    }).default({} as any),
    observeDays: z.number().default(5),  // 模拟盘观察期（交易日）
    llmProvider: z.string().default('deepseek-official'),  // LLM 改写路由
    llmModel: z.string().default('deepseek-v4-flash'),
  }).default({} as any);

  private osMemory: OsMemoryStore;
  private observeDays: number;
  private llmProvider: string;
  private llmModel: string;
  private qv2BaseURL: string;

  constructor(ctx: Context, config: any) {
    super(ctx, 'evolver');
    this.qv2BaseURL = config?.quantsysV2?.baseURL || 'http://localhost:5001';
    this.osMemory = new OsMemoryStore({ baseURL: (config as any).agentOS?.baseURL || 'http://localhost:8080', agentId: (config as any).agentOS?.agentId || 'agent-dh' });
    this.observeDays = config?.observeDays || 5;
    this.llmProvider = config?.llmProvider || 'deepseek-official';
    this.llmModel = config?.llmModel || 'deepseek-v4-flash';
    this.registerTools();
  }

  private registerTools(): void {
    const { ctx, osMemory, llmProvider, llmModel, observeDays } = this;

    // 1. Prompt Evolver - 接收 experience_distill 建议，生成段更新提案，调用 genome_update 应用
    ctx.tools.register(createPromptEvolverTool(ctx, osMemory, llmProvider, llmModel, observeDays));

    // 2. Validation Gate - RFC 008: 验证门——提案应用为 candidate 观察版，观察期后裁决转正/回滚
    ctx.tools.register(createValidationGateTool(ctx, osMemory, observeDays));

    // 3. Daily Distill - 每日蒸馏编排：experience_distill → prompt_evolver
    ctx.tools.register(createDailyDistillTool(ctx, osMemory));

    // 4. Weekly Report - M6 学习飞轮周报：封装后端 /api/reports/weekly
    //    （2026-09-03 补：原 prompt 引用 weekly_report 但 agent 侧无此工具 → 业务空转）
    ctx.tools.register(createWeeklyReportTool(this.qv2BaseURL));
  }
}
