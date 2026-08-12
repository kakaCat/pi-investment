/**
 * V2MemoryProvider - 通过 quantsys-v2 的 /api/memory/* 接口实现 MemoryProvider
 *
 * 设计要点：
 * - 所有写入携带 provenance（session_kind/channel/session_id）
 * - 召回结果自动调用 validate 更新 last_recalled_at
 * - 防 recall 循环：syncTurn 时排除本轮被召回的内容
 */

import type {
  MemoryProvider,
  MemorySearchResult,
  MemorySearchResponse,
  MemoryWriteParams,
  ExperienceWriteParams,
} from './port.js';

export class V2MemoryProvider implements MemoryProvider {
  readonly name = 'v2-memory';

  private baseUrl: string;
  private sessionId: string = '';
  private sessionKind: string = 'user';
  private channel: string = 'terminal';
  private workspace: string = '';
  private initialized = false;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
  }

  isAvailable(): boolean {
    // 配置检查：有 baseUrl 即可用
    return !!this.baseUrl;
  }

  async initialize(
    sessionId: string,
    context: {
      sessionKind?: string;
      channel?: string;
      workspace?: string;
    }
  ): Promise<void> {
    this.sessionId = sessionId;
    this.sessionKind = context.sessionKind || 'user';
    this.channel = context.channel || 'terminal';
    this.workspace = context.workspace || '';
    this.initialized = true;
  }

  systemPromptBlock(): string {
    if (!this.initialized) return '';
    return `Memory provider: ${this.name} (v2 unified storage, hybrid search ready)`;
  }

  async prefetch(
    query: string,
    sessionId?: string,
    limit: number = 3,
    maxChars: number = 2000
  ): Promise<string> {
    if (!query || !query.trim()) return '';

    try {
      const response = await this._search(query, { limit });
      if (!response.items || response.items.length === 0) {
        return '';
      }

      // 格式化召回结果，控制字符预算
      const lines: string[] = [];
      let totalChars = 0;
      const recalledIds: number[] = [];

      for (const item of response.items) {
        const block = this._formatRecalledItem(item);
        if (totalChars + block.length > maxChars) break;

        lines.push(block);
        totalChars += block.length;
        if (item.id) recalledIds.push(item.id);
      }

      // 异步更新 last_recalled_at（不阻塞召回）
      if (recalledIds.length > 0) {
        this._batchUpdateRecallTimestamp(recalledIds).catch((err) => {
          console.warn(`[V2Memory] Failed to update recall timestamp: ${err}`);
        });
      }

      return lines.join('\n\n');
    } catch (error) {
      console.warn(`[V2Memory] Prefetch failed: ${error}`);
      return '';
    }
  }

  async query(
    query: string,
    options?: {
      scope?: string;
      kind?: string;
      status?: string;
      limit?: number;
    }
  ): Promise<MemorySearchResponse> {
    return this._search(query, options);
  }

  async search(query: string, topK: number = 5): Promise<MemorySearchResult[]> {
    const response = await this._search(query, { limit: topK });
    return response.items;
  }

  async syncTurn(
    userContent: string,
    assistantContent: string,
    sessionId?: string,
    metadata?: {
      sessionKind?: string;
      channel?: string;
      recalledIds?: number[];
    }
  ): Promise<void> {
    // W1.4 要求：防 recall 循环——排除本轮被召回注入的内容
    // 当前实现：简单过滤空内容，后续可根据 recalledIds 做更精细过滤
    if (!assistantContent || !assistantContent.trim()) return;

    // 提取可持久化的助手输出（排除工具调用日志等）
    const persistContent = this._extractPersistableContent(assistantContent);
    if (!persistContent) return;

    // 暂不实现自动写入（需要更精细的判断逻辑）
    // 实际写入由工具层（memory_write/experience_write）触发
  }

  async validate(entryId: number, success: boolean): Promise<void> {
    try {
      const url = `${this.baseUrl}/api/memory/${entryId}/validate`;
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ success }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`HTTP ${response.status}: ${text}`);
      }
    } catch (error) {
      console.warn(`[V2Memory] Validate failed for entry ${entryId}: ${error}`);
      throw error;
    }
  }

  async writeExperience(params: ExperienceWriteParams): Promise<{ success: boolean; id?: number; message: string }> {
    try {
      // 构建经验条目（映射到 MemoryEntry 格式）
      const payload: MemoryWriteParams = {
        kind: 'experience',
        scope: params.symbol ? `stock:${params.symbol}` : 'global',
        title: params.scenario.slice(0, 100),
        content: this._formatExperienceContent(params),
        payload: {
          pattern: {
            conditions: params.conditions,
            action: params.action,
          },
          outcomes: {
            total_cases: params.total_cases,
            win_rate: params.win_rate,
            avg_return: params.avg_return,
            max_gain: params.max_gain,
            max_loss: params.max_loss,
          },
          recommendation: params.recommendation,
          examples: params.examples || [],
        },
        evidence: this._buildExperienceEvidence(params),
        status: 'testing',
        confidence: params.confidence,
        provenance: {
          session_kind: this.sessionKind,
          channel: this.channel,
          session_id: this.sessionId,
        },
        source: 'agent',
      };

      const result = await this._write(payload);
      return {
        success: true,
        id: result.id,
        message: `Experience recorded: "${params.scenario.slice(0, 40)}..." (id: ${result.id})`,
      };
    } catch (error) {
      return {
        success: false,
        message: `Failed to write experience: ${error}`,
      };
    }
  }

  async queryExperience(params: {
    scenario?: string;
    symbol?: string;
    conditions?: string[];
    limit?: number;
    include_deprecated?: boolean;
  }): Promise<string> {
    try {
      // 构建查询
      const query = params.scenario || params.symbol || params.conditions?.join(' ') || '';
      const scope = params.symbol ? `stock:${params.symbol}` : undefined;
      const status = params.include_deprecated ? undefined : 'active,testing';

      const response = await this._search(query, {
        scope,
        kind: 'experience',
        status,
        limit: params.limit || 5,
      });

      if (!response.items || response.items.length === 0) {
        return '未找到相关历史经验。';
      }

      // 格式化输出
      const lines: string[] = [];
      lines.push(`找到 ${response.total} 条相关经验，展示前 ${response.items.length} 条:\n`);

      for (let i = 0; i < response.items.length; i++) {
        const item = response.items[i];
        lines.push(`\n━━━ 经验 ${i + 1} ━━━`);
        lines.push(this._formatExperienceItem(item));
      }

      return lines.join('\n');
    } catch (error) {
      return `查询经验库失败: ${error}`;
    }
  }

  async shutdown(): Promise<void> {
    // No persistent connections to close
  }

  // ========== Private Helpers ==========

  private async _search(
    query: string,
    options?: {
      scope?: string;
      kind?: string;
      status?: string;
      limit?: number;
    }
  ): Promise<MemorySearchResponse> {
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    if (options?.scope) params.set('scope', options.scope);
    if (options?.kind) params.set('kind', options.kind);
    if (options?.status) params.set('status', options.status);
    if (options?.limit) params.set('limit', String(options.limit));

    const url = `${this.baseUrl}/api/memory/search?${params.toString()}`;
    const response = await fetch(url);

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`HTTP ${response.status}: ${text}`);
    }

    return response.json();
  }

  private async _write(params: MemoryWriteParams): Promise<{ id: number }> {
    const url = `${this.baseUrl}/api/memory`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`HTTP ${response.status}: ${text}`);
    }

    return response.json();
  }

  private async _batchUpdateRecallTimestamp(ids: number[]): Promise<void> {
    // 当前逐个更新 last_recalled_at（未来可优化为批量接口）
    for (const id of ids) {
      try {
        const url = `${this.baseUrl}/api/memory/${id}/validate`;
        await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ success: true }),
        });
      } catch (err) {
        // 静默失败，不阻塞召回
        console.warn(`[V2Memory] Failed to update recall timestamp for ${id}: ${err}`);
      }
    }
  }

  private _formatRecalledItem(item: MemorySearchResult): string {
    const lines: string[] = [];
    if (item.title) lines.push(`**${item.title}**`);
    lines.push(item.content);
    if (item.score !== undefined) lines.push(`(relevance: ${item.score.toFixed(2)})`);
    return lines.join('\n');
  }

  private _formatExperienceContent(params: ExperienceWriteParams): string {
    const lines: string[] = [];
    lines.push(`场景: ${params.scenario}`);
    lines.push(`建议: ${params.recommendation}`);
    lines.push(`原因: ${params.reason}`);
    lines.push(`置信度: ${(params.confidence * 100).toFixed(0)}%`);
    lines.push(`历史数据:`);
    lines.push(`  - 总案例: ${params.total_cases} 次`);
    lines.push(`  - 胜率: ${params.win_rate.toFixed(1)}%`);
    lines.push(`  - 平均收益: ${params.avg_return.toFixed(2)}%`);
    if (params.max_gain) lines.push(`  - 最大盈利: ${params.max_gain.toFixed(2)}%`);
    if (params.max_loss) lines.push(`  - 最大亏损: ${params.max_loss.toFixed(2)}%`);
    return lines.join('\n');
  }

  private _formatExperienceItem(item: MemorySearchResult): string {
    // 从 content 或 payload 提取信息
    return item.content || item.title || '(无内容)';
  }

  private _buildExperienceEvidence(params: ExperienceWriteParams): Record<string, any> {
    // 证据链：examples 作为证据
    if (params.examples && params.examples.length > 0) {
      return {
        examples: params.examples,
        total_cases: params.total_cases,
      };
    }
    return {};
  }

  private _extractPersistableContent(assistantContent: string): string {
    // 简单过滤：排除纯工具调用日志
    const lines = assistantContent.split('\n').filter(line => {
      const trimmed = line.trim();
      return trimmed && !trimmed.startsWith('[Tool') && !trimmed.startsWith('执行工具');
    });
    return lines.join('\n').trim();
  }
}
