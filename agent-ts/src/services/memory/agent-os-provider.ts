/**
 * Agent OS Memory Provider
 *
 * 实现 MemoryProvider 接口，通过 Agent OS CLI 操作记忆系统
 */

import type {
  MemoryProvider,
  MemorySearchResult,
  MemorySearchResponse,
  MemoryWriteParams,
  ExperienceWriteParams,
} from './port.js';

import {
  agentOSMemoryWrite,
  agentOSMemorySearch,
  agentOSMemoryRecallAudit,
  type AgentOSMemoryWriteOptions,
  type AgentOSMemorySearchOptions,
} from '../../infrastructure/agent-os/cli.js';

export class AgentOSMemoryProvider implements MemoryProvider {
  readonly name = 'agent-os';

  private sessionId?: string;
  private sessionKind?: string;
  private channel?: string;
  private namespace: string = 'default';
  private recalledIdsThisTurn: Set<string> = new Set();

  isAvailable(): boolean {
    // 检查 Agent OS CLI 是否可用
    const cliPath = process.env.AGENT_OS_CLI_PATH;
    return !!cliPath || true; // 默认假设可用
  }

  async initialize(sessionId: string, context: {
    sessionKind?: string;
    channel?: string;
    workspace?: string;
  }): Promise<void> {
    this.sessionId = sessionId;
    this.sessionKind = context.sessionKind || 'user';
    this.channel = context.channel || 'terminal';

    // 根据 session kind 映射到实际存在的 namespace
    const namespaceMap: Record<string, string> = {
      'user': 'system',           // 用户会话使用 system namespace
      'cron': 'fin-agent',        // 定时任务使用 fin-agent
      'wake': 'fin-agent',        // 唤醒任务使用 fin-agent
      'distiller': 'memory-agent', // 蒸馏任务使用 memory-agent
    };

    this.namespace = namespaceMap[this.sessionKind] || 'system';

    console.log(`[AgentOS Memory] Initialized for session ${sessionId}, namespace: ${this.namespace}`);
  }

  systemPromptBlock(): string {
    return `## Memory System (Agent OS)
- Provider: Agent OS CLI
- Namespace: ${this.namespace}
- Session: ${this.sessionId || 'unknown'}
- Memory is persisted across sessions and automatically recalled based on context.`;
  }

  async prefetch(
    query: string,
    sessionId?: string,
    limit: number = 3,
    maxChars: number = 2000
  ): Promise<string> {
    try {
      const searchOptions: AgentOSMemorySearchOptions = {
        namespace: this.namespace,
        query,
        limit,
        minScore: 0.6, // 最低相关度阈值
      };

      const result = await agentOSMemorySearch(searchOptions);

      if (!result.success || !result.data || result.data.length === 0) {
        return ''; // 无相关记忆
      }

      // 记录本轮召回的 ID（防 recall 循环）
      this.recalledIdsThisTurn.clear();
      result.data.forEach(item => this.recalledIdsThisTurn.add(item.id));

      // 格式化为文本块（控制在 maxChars 内）
      let accumulated = '';
      const items: string[] = [];

      for (const mem of result.data) {
        const formatted = `[${mem.id}] ${mem.content}`;
        if (accumulated.length + formatted.length > maxChars) {
          break;
        }
        items.push(formatted);
        accumulated += formatted + '\n';
      }

      if (items.length === 0) {
        return '';
      }

      return `### Recalled Memories (${items.length})\n${items.join('\n')}`;
    } catch (error) {
      console.error('[AgentOS Memory] Prefetch error:', error);
      return ''; // 降级：无记忆
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
    try {
      const searchOptions: AgentOSMemorySearchOptions = {
        namespace: this.namespace, // 使用当前 namespace，不使用 options?.scope
        query,
        limit: options?.limit || 10,
        minScore: 0.5,
      };

      const result = await agentOSMemorySearch(searchOptions);

      if (!result.success) {
        throw new Error(result.error || 'Search failed');
      }

      const items: MemorySearchResult[] = (result.data || []).map(item => ({
        id: parseInt(item.id, 10),
        title: item.metadata?.title || item.content.slice(0, 50),
        content: item.content,
        score: item.score,
        kind: item.metadata?.kind,
        scope: item.metadata?.scope,
        source: 'both', // Agent OS 使用混合检索
      }));

      return {
        items,
        total: items.length,
        strategy: 'hybrid',
        degraded: false,
      };
    } catch (error) {
      console.error('[AgentOS Memory] Query error:', error);
      return {
        items: [],
        total: 0,
        degraded: true,
      };
    }
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
    // Agent OS 不需要轮次级记录（无自动抽取）
    // 仅记录召回 ID（防重复写入）
    if (metadata?.recalledIds) {
      this.recalledIdsThisTurn = new Set(metadata.recalledIds.map(id => id.toString()));
    }
  }

  async write(params: MemoryWriteParams): Promise<{ id?: number; path?: string }> {
    try {
      // 防 recall 循环：拒绝来自 recall 的写入
      if (params.source === 'recall') {
        console.warn('[AgentOS Memory] Rejected write from recall source');
        return { path: 'rejected:recall-loop' };
      }

      const writeOptions: AgentOSMemoryWriteOptions = {
        namespace: this.namespace, // 使用当前 namespace，不使用 params.scope
        content: params.content,
        metadata: {
          kind: params.kind || 'episode',
          title: params.title || params.content.slice(0, 50),
          status: params.status || 'active',
          confidence: params.confidence,
          provenance: params.provenance || {
            session_kind: this.sessionKind,
            channel: this.channel,
            session_id: this.sessionId,
          },
          payload: params.payload,
          evidence: params.evidence,
        },
        tags: params.kind ? [params.kind] : undefined,
      };

      const result = await agentOSMemoryWrite(writeOptions);

      if (!result.success) {
        throw new Error(result.error || 'Write failed');
      }

      return {
        id: result.data?.id ? parseInt(result.data.id, 10) : undefined,
      };
    } catch (error) {
      console.error('[AgentOS Memory] Write error:', error);
      throw error;
    }
  }

  async validate(entryId: number, success: boolean): Promise<void> {
    // Agent OS 暂不支持 validate 操作
    // 未来可通过 CLI 扩展实现
    console.log(`[AgentOS Memory] Validate called for entry ${entryId}: ${success ? 'success' : 'failure'}`);
  }

  async search(query: string, topK: number = 5): Promise<MemorySearchResult[]> {
    const response = await this.query(query, { limit: topK });
    return response.items;
  }

  async writeExperience(params: ExperienceWriteParams): Promise<{ success: boolean; id?: number; message: string }> {
    try {
      // Experience 作为特殊类型的 memory 写入
      const content = `
场景: ${params.scenario}
条件: ${params.conditions.join(', ')}
操作: ${params.action}
胜率: ${(params.win_rate * 100).toFixed(1)}%
平均收益: ${(params.avg_return * 100).toFixed(2)}%
样本数: ${params.total_cases}
建议: ${params.recommendation}
原因: ${params.reason}
置信度: ${(params.confidence * 100).toFixed(0)}%
`.trim();

      const writeResult = await this.write({
        kind: 'experience',
        scope: params.symbol ? `stock:${params.symbol}` : 'global',
        title: `经验: ${params.scenario}`,
        content,
        payload: {
          scenario: params.scenario,
          conditions: params.conditions,
          action: params.action,
          total_cases: params.total_cases,
          win_rate: params.win_rate,
          avg_return: params.avg_return,
          max_gain: params.max_gain,
          max_loss: params.max_loss,
          recommendation: params.recommendation,
          examples: params.examples,
        },
        confidence: params.confidence,
        source: 'agent',
      });

      return {
        success: true,
        id: writeResult.id,
        message: `Experience recorded: ${params.scenario}`,
      };
    } catch (error: any) {
      return {
        success: false,
        message: `Failed to write experience: ${error.message}`,
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
      const scope = params.symbol ? `stock:${params.symbol}` : undefined;
      const query = params.scenario || params.conditions?.join(' ') || 'experience';

      const response = await this.query(query, {
        scope,
        kind: 'experience',
        status: params.include_deprecated ? undefined : 'active',
        limit: params.limit || 5,
      });

      if (response.items.length === 0) {
        return '无相关经验';
      }

      return response.items
        .map((item, idx) => `${idx + 1}. [${item.title}] (相关度: ${(item.score * 100).toFixed(0)}%)\n${item.content}`)
        .join('\n\n');
    } catch (error: any) {
      return `查询经验失败: ${error.message}`;
    }
  }

  async shutdown(): Promise<void> {
    this.recalledIdsThisTurn.clear();
    console.log('[AgentOS Memory] Shutdown complete');
  }
}
