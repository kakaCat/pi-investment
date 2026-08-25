/**
 * Agent OS 记忆库适配器（2026-08-25）
 *
 * 背景：quantsys-v2 记忆库写入已停用（ollama embedding 挂起致读写超时），
 * 用户决策统一使用 Agent OS 记忆（/api/v1/memory，postgres 持久）。
 *
 * 设计：签名与 QuantsysV2Client 的 createMemory/searchMemory 完全对齐，
 * 插件迁移 = 把 `new QuantsysV2Client(...)` 换成 `new OsMemoryStore(...)`。
 *
 * 字段映射（OS 搜索只命中 title+content，实测 2026-08-25）：
 *   kind: episode→data / experience→experience / rule→knowledge / namespace=decision→decision
 *   scope/payload/status/confidence/provenance → 全部嵌入 content JSON 文本
 *   （scope 嵌进 JSON 才能被 q 命中；deprecated/payload 过滤全部 client 侧）
 */
import { AgentOSClient } from '@pi-investment/agent-os-client';

export interface OsMemoryEntry {
  kind: string;
  scope: string;
  title: string;
  content: string;
  payload?: any;
  status?: string;
  confidence?: number;
  source?: string;
  provenance?: any;
}

export interface OsMemorySearchResult {
  items: any[];
  total: number;
}

const KIND_TO_CATEGORY: Record<string, string> = {
  episode: 'data',
  experience: 'experience',
  rule: 'knowledge',
  stock_note: 'knowledge',
  decision: 'decision',
};

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

  /**
   * 写入记忆（映射到 OS category/tags，业务字段嵌入 content JSON）
   * 返回 { id }（与 qv2.createMemory 返回形状对齐）
   */
  async createMemory(entry: OsMemoryEntry): Promise<{ id: string }> {
    const category = KIND_TO_CATEGORY[entry.kind] ?? 'data';

    // 业务元数据包（嵌入 content JSON 头部，保证 scope/kind 可被 q 文本命中）
    const envelope = {
      kind: entry.kind,
      scope: entry.scope,
      status: entry.status ?? 'testing',
      confidence: entry.confidence ?? 0.5,
      source: entry.source ?? 'agent',
      provenance: entry.provenance ?? null,
      payload: entry.payload ?? null,
      body: entry.content,
    };

    const res: any = await (this.client.memory as any).write({
      title: entry.title,
      content: JSON.stringify(envelope),
      category,
      tags: [entry.scope, `kind:${entry.kind}`, `agent:${this.agentId}`].filter(Boolean),
    });

    return { id: String(res?.id ?? res?.memory?.id ?? '') };
  }

  /**
   * 搜索记忆（q 命中 OS title+content；kind/scope/status 过滤 client 侧）
   * 返回的 items 保持 {id, title, content, payload, status, kind, scope, created_at} 形状，
   * content 为 envelope.body（原始正文），payload/status 从 envelope 反解。
   */
  async searchMemory(params: { q?: string; kind?: string; scope?: string; limit?: number }): Promise<OsMemorySearchResult> {
    const q = params.q ?? '';
    const limit = params.limit ?? 20;
    // OS q 匹配 title+content；scope 搜索词与 q 合并（scope 嵌在 envelope JSON 里可被命中）
    // 2026-08-25 实测修正：OS 文本搜索是多词 AND 匹配，把 scope 合并进 q 会导致
    // 联合查询零命中。改为 q 单独搜、scope 纯 client 侧过滤。
    const query = q;

    // 2026-08-25 实测：agent-os-client 的 memory.search 用 POST /api/v1/memory/search，
    // 但 OS 服务端只注册 GET（Methods("GET")）→ 404。绕过 client，直接 GET。
    const url = `${this.baseURL}/api/v1/memory/search?q=${encodeURIComponent(query || ' ')}&limit=${Math.min(limit * 3, 150)}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`OS memory search failed: HTTP ${resp.status}`);
    const res: any = await resp.json();
    const raw: any[] = res?.memories ?? res?.items ?? [];

    const items: any[] = [];
    for (const it of raw) {
      let env: any = null;
      try { env = typeof it.content === 'string' ? JSON.parse(it.content) : it.content; } catch { /* 非 envelope 记录跳过 */ }
      if (!env || typeof env !== 'object' || env.kind === undefined) continue;

      // client 侧过滤
      if (params.kind && env.kind !== params.kind) continue;
      if (params.scope && env.scope !== params.scope) continue;
      if (env.status === 'deprecated') continue;

      items.push({
        id: it.id,
        kind: env.kind,
        scope: env.scope,
        title: it.title,
        content: env.body ?? '',
        payload: env.payload,
        status: env.status,
        confidence: env.confidence,
        source: env.source,
        provenance: env.provenance,
        created_at: it.created_at,
      });
      if (items.length >= limit) break;
    }

    return { items, total: items.length };
  }
}
