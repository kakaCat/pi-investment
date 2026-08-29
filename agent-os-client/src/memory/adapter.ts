/**
 * OsMemoryStore - Compatibility adapter for legacy code
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
 */

import { AgentOSClient } from '../client.js';

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
  degraded: boolean;
  strategy: string;
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

    const res: any = await this.client.memory.write({
      namespace: this.agentId,
      content: JSON.stringify(envelope),
      category,
      importance: entry.confidence ?? 0.5,
      metadata: {
        title: entry.title,
        kind: entry.kind,
        scope: entry.scope,
      },
    });

    return { id: res.id };
  }

  /**
   * 搜索记忆（过滤 deprecated + payload，结构对齐 qv2）
   * 返回 { memories: [...] }（与 qv2.searchMemory 返回形状对齐）
   */
  async searchMemory(params: {
    q: string;
    kind?: string;
    scope?: string;
    top_k?: number;
    status_in?: string[];
  }): Promise<{ memories: any[] }> {
    const category = params.kind ? KIND_TO_CATEGORY[params.kind] : undefined;

    const results = await this.client.memory.search({
      namespace: this.agentId,
      query: params.q,
      top_k: params.top_k ?? 20,
      category,
    });

    // 解包 envelope，恢复业务字段
    const memories = results
      .map((r: any) => {
        try {
          const envelope = JSON.parse(r.memory.content);
          const kind = envelope.kind || params.kind || 'episode';
          const scope = envelope.scope || '';
          const status = envelope.status || 'testing';
          const confidence = envelope.confidence ?? 0.5;

          // 过滤逻辑（与 os-memory 对齐）
          if (params.kind && kind !== params.kind) return null;
          if (params.scope && scope !== params.scope) return null;
          if (params.status_in && !params.status_in.includes(status)) return null;
          if (status === 'deprecated') return null;

          return {
            id: r.memory.id,
            kind,
            scope,
            title: r.memory.metadata?.title || '',
            content: envelope.body || envelope.content || '',
            payload: envelope.payload || null,
            status,
            confidence,
            source: envelope.source || 'unknown',
            provenance: envelope.provenance || null,
            created_at: r.memory.created_at,
            score: r.score,
          };
        } catch {
          return null;
        }
      })
      .filter(Boolean);

    return { memories };
  }

  /**
   * 兼容方法：write({title, content, namespace, tags}) → id
   * 为 trading 等插件历史调用提供向后兼容（2026-08-28 修复）
   */
  async write(params: { title: string; content: string; namespace?: string; tags?: string[] }): Promise<{ id: string }> {
    const namespace = params.namespace || 'default';
    const kind = namespace === 'experience' ? 'experience' : 'episode';
    return this.createMemory({
      kind,
      scope: namespace,
      title: params.title,
      content: params.content,
      payload: { namespace, tags: params.tags || [] },
      status: 'testing',
      confidence: 0.5,
      source: 'agent',
      provenance: { channel: 'dsh', session_kind: 'agent' },
    });
  }
}
