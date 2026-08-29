import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { createRiskControllerTool } from './tools/RiskControllerTool';
import { createRiskMetricsTool } from './tools/RiskMetricsTool';
import { createBarraDecompositionTool } from './tools/BarraDecompositionTool';
import { createRegimePositionLimitTool } from './tools/RegimePositionLimitTool';

/**
 * Minimal OsMemoryStore replacement (inlined from deleted @pi-investment/os-memory)
 * Wraps AgentOSClient to provide createMemory/searchMemory API
 */
class OsMemoryStore {
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

  async search(params: { query: string; namespace?: string; top_k?: number }): Promise<{ memories: any[] }> {
    const kind = params.namespace === 'experience' ? 'experience' : undefined;
    const result = await this.searchMemory({ q: params.query, kind, limit: params.top_k ?? 20 });
    return { memories: result.items };
  }

  async write(params: { title: string; content: string; namespace?: string; tags?: string[] }): Promise<{ id: string }> {
    const namespace = params.namespace || 'default';
    const kind = namespace === 'experience' ? 'experience' : 'episode';
    return this.createMemory({ kind, scope: namespace, title: params.title, content: params.content, payload: { namespace, tags: params.tags || [] }, status: 'testing', confidence: 0.5, source: 'agent', provenance: { channel: 'dsh', session_kind: 'agent' } });
  }
}

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
  agentOS?: {
    baseURL?: string;
    agentId?: string;
  };
}

/**
 * Risk Management Plugin for Agent-DH
 *
 * Risk control, position sizing, portfolio risk assessment.
 */
export default class RiskPlugin extends Service {
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
    super(ctx, 'risk');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.aos = new AgentOSClient({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
      agentId: config.agentOS?.agentId || 'agent-dh'
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;
    const osMemory = new OsMemoryStore({ baseURL: 'http://localhost:8080', agentId: 'agent-dh' });

    // 风险控制
    ctx.tools.register(createRiskControllerTool(qv2));

    // 风险指标
    ctx.tools.register(createRiskMetricsTool(qv2));

    // Barra风险分解
    ctx.tools.register(createBarraDecompositionTool(qv2));

    // M4 仓位映射表（RFC 004，2026-08-21）
    ctx.tools.register(createRegimePositionLimitTool(qv2, osMemory));
  }
}

