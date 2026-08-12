/**
 * FileFallbackProvider - 包装现有 memory-store.ts 作为降级实现
 *
 * 设计要点：
 * - 保留现有文件存储逻辑（MEMORY.md + daily/*.jsonl）
 * - 实现 MemoryProvider 接口以兼容新架构
 * - 作为 v2-client 不可用时的降级方案
 */

import type {
  MemoryProvider,
  MemorySearchResult,
  MemorySearchResponse,
  MemoryWriteParams,
  ExperienceWriteParams,
} from './port.js';
import { MemoryStore } from '../intelligence/memory-store.js';
import {
  queryExperience as legacyQueryExperience,
  queryAndFormatExperience as legacyFormatExperience,
} from '../intelligence/experience-query.js';
import { addExperience } from '../intelligence/experience-manager.js';
import type { Experience } from '../../types/evolution.js';

export class FileFallbackProvider implements MemoryProvider {
  readonly name = 'file-fallback';

  private store: MemoryStore;
  private sessionId: string = '';
  private sessionKind: string = 'user';
  private channel: string = 'terminal';
  private initialized = false;

  constructor(piDir: string) {
    this.store = new MemoryStore(piDir);
  }

  isAvailable(): boolean {
    // 文件存储始终可用
    return true;
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
    this.initialized = true;
  }

  systemPromptBlock(): string {
    if (!this.initialized) return '';
    const stats = this.store.getStats();
    return `Memory provider: ${this.name} (file-based, ${stats.dailyEntries} entries, ${stats.dailyFiles} files)`;
  }

  async prefetch(
    query: string,
    sessionId?: string,
    limit: number = 3,
    maxChars: number = 2000
  ): Promise<string> {
    if (!query || !query.trim()) return '';

    try {
      // 使用 hybridSearch 召回
      const results = this.store.hybridSearch(query, limit);
      if (!results || results.length === 0) {
        return '';
      }

      // 格式化召回结果，控制字符预算
      const lines: string[] = [];
      let totalChars = 0;

      for (const item of results) {
        const block = `**${item.path}**\n${item.snippet}\n(score: ${item.score})`;
        if (totalChars + block.length > maxChars) break;

        lines.push(block);
        totalChars += block.length;
      }

      return lines.join('\n\n');
    } catch (error) {
      console.warn(`[FileFallback] Prefetch failed: ${error}`);
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
    const results = this.store.hybridSearch(query, options?.limit || 20);
    return {
      items: results.map(r => ({
        title: r.path,
        content: r.snippet,
        score: r.score,
      })),
      total: results.length,
      degraded: false,
      strategy: 'hybrid',
    };
  }

  async search(query: string, topK: number = 5): Promise<MemorySearchResult[]> {
    const results = this.store.hybridSearch(query, topK);
    return results.map(r => ({
      title: r.path,
      content: r.snippet,
      score: r.score,
    }));
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
    // 防 recall 循环：排除本轮被召回的内容
    // 文件存储模式下，简单过滤空内容
    if (!assistantContent || !assistantContent.trim()) return;

    // 暂不实现自动写入（需要更精细的判断逻辑）
  }

  async validate(entryId: number, success: boolean): Promise<void> {
    // 文件存储模式下，validate 操作无意义（无 ID 索引）
    // 静默成功
  }

  async writeExperience(params: ExperienceWriteParams): Promise<{ success: boolean; id?: number; message: string }> {
    try {
      // 构建经验条目（复用现有 Experience 类型）
      const scenarioSlug = params.scenario
        .replace(/[^a-zA-Z0-9一-鿿]/g, '_')
        .slice(0, 40);
      const id = `exp_${params.action}_${scenarioSlug}_${Date.now().toString(36)}`;

      const examples = params.examples || [];
      if (params.symbol && examples.length === 0) {
        examples.push({
          date: new Date().toISOString().split('T')[0],
          symbol: params.symbol,
          session_id: 'manual',
          result: params.avg_return,
        });
      }

      const experience: Experience = {
        id,
        scenario: params.scenario,
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
        reason: params.reason,
        examples,
        confidence: params.confidence,
        last_updated: new Date().toISOString().split('T')[0],
        weight: 1.0,
        last_verified_at: null,
        consecutive_failures: 0,
        half_life_days: 30,
        deprecated: false,
      };

      addExperience(experience);

      return {
        success: true,
        message: `Experience recorded: "${params.scenario.slice(0, 40)}..." (id: ${id})`,
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
      return legacyFormatExperience({
        scenario: params.scenario || '',
        symbol: params.symbol,
        conditions: params.conditions,
        limit: params.limit,
        include_deprecated: params.include_deprecated,
      });
    } catch (error) {
      return `查询经验库失败: ${error}`;
    }
  }

  async shutdown(): Promise<void> {
    // No cleanup needed for file storage
  }
}
