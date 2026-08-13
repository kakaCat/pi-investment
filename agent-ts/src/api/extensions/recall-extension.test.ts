import { describe, it, expect, jest } from '@jest/globals';
import {
  createRecallExtension,
  detectFlow,
  stripSkillPrefix,
  adaptSearchResults,
} from './recall-extension.js';
import type { RecallSearchPort, RecallAuditPort } from '../../services/recall/ports.js';
import type { RecallHit } from '../../domain/recall/types.js';
import type { MemorySearchResult } from '../../services/memory/port.js';

type SearchFn = RecallSearchPort['search'];
type AuditFn = RecallAuditPort['record'];

function hit(id: number, score = 0.6): RecallHit {
  return { id, score, source: 'both', content: `记忆内容${id}` };
}

/**
 * fake pi：注册 handler，emit 返回 handler 的（await 后）返回值，
 * 用于断言 before_agent_start 是否产出 message。
 */
function createMockPi() {
  const handlers = new Map<string, Array<(event: any) => any>>();
  const pi = {
    on(event: string, handler: (event: any) => any) {
      handlers.set(event, [...(handlers.get(event) ?? []), handler]);
    },
    async emit(event: string, payload: Record<string, unknown> = {}) {
      let result: any;
      for (const h of handlers.get(event) ?? []) {
        result = await h({ type: event, ...payload });
      }
      return result;
    },
  };
  return pi;
}

function install(search: ReturnType<typeof jest.fn<SearchFn>>, audit: ReturnType<typeof jest.fn<AuditFn>>) {
  const pi = createMockPi();
  createRecallExtension({ search }, { record: audit })(pi as any);
  return pi;
}

describe('recallExtension 接线', () => {
  it('① 普通对话 → before_agent_start 产出 recalled-memory message', async () => {
    const search = jest.fn<SearchFn>().mockResolvedValue([hit(1, 0.9)]);
    const audit = jest.fn<AuditFn>().mockResolvedValue(undefined);
    const pi = install(search, audit);

    pi.emit('input', { text: '中国铝业股息', source: 'interactive' });
    const result = await pi.emit('before_agent_start', { prompt: '中国铝业股息' });

    expect(result.message).toBeDefined();
    expect(result.message.customType).toBe('recalled-memory');
    expect(result.message.display).toBe(false);
    expect(result.message.content).toContain('<recalled_memory');
    expect(result.message.details.count).toBe(1);
  });

  it('② /skill:x 文本 → search query 不含 skill 前缀', async () => {
    const search = jest.fn<SearchFn>().mockResolvedValue([]);
    const audit = jest.fn<AuditFn>().mockResolvedValue(undefined);
    const pi = install(search, audit);

    pi.emit('input', { text: '/skill:portfolio-entry 分析茅台', source: 'interactive' });
    await pi.emit('before_agent_start', { prompt: '<skill expanded>' });

    expect(search).toHaveBeenCalledTimes(1);
    expect(search.mock.calls[0][0]).toBe('分析茅台');
    expect(search.mock.calls[0][0]).not.toContain('/skill');
  });

  it('③ 检索空 → before_agent_start 返回 void', async () => {
    const search = jest.fn<SearchFn>().mockResolvedValue([]);
    const audit = jest.fn<AuditFn>().mockResolvedValue(undefined);
    const pi = install(search, audit);

    pi.emit('input', { text: '无关查询', source: 'interactive' });
    const result = await pi.emit('before_agent_start', { prompt: '无关查询' });

    expect(result).toBeUndefined();
  });

  it('④ source=rpc → flow=scheduled-task 写入 message.details', async () => {
    const search = jest.fn<SearchFn>().mockResolvedValue([hit(1, 0.9)]);
    const audit = jest.fn<AuditFn>().mockResolvedValue(undefined);
    const pi = install(search, audit);

    pi.emit('input', { text: '📚 每日复盘', source: 'rpc' });
    const result = await pi.emit('before_agent_start', { prompt: '📚 每日复盘' });

    expect(result.message).toBeDefined();
    expect(result.message.details.flow).toBe('scheduled-task');
  });

  it('⑤ source=extension → flow=wake-event 写入 message.details', async () => {
    const search = jest.fn<SearchFn>().mockResolvedValue([hit(1, 0.9)]);
    const audit = jest.fn<AuditFn>().mockResolvedValue(undefined);
    const pi = install(search, audit);

    pi.emit('input', { text: '【盯盘触发】', source: 'extension' });
    const result = await pi.emit('before_agent_start', { prompt: '【盯盘触发】' });

    expect(result.message).toBeDefined();
    expect(result.message.details.flow).toBe('wake-event');
  });
});

describe('detectFlow', () => {
  it('/skill: 开头 → skill-invocation', () => {
    expect(detectFlow('/skill:foo bar')).toBe('skill-invocation');
  });

  it('普通文本 → interactive-chat', () => {
    expect(detectFlow('中国铝业股息')).toBe('interactive-chat');
  });

  it('source=rpc → scheduled-task（调度任务）', () => {
    expect(detectFlow('📚 每日复盘', 'rpc')).toBe('scheduled-task');
  });

  it('source=extension → wake-event（wake 通道）', () => {
    expect(detectFlow('【盯盘触发】', 'extension')).toBe('wake-event');
  });

  it('source=rpc 优先于 /skill: 前缀判定', () => {
    expect(detectFlow('/skill:foo bar', 'rpc')).toBe('scheduled-task');
  });
});

describe('stripSkillPrefix', () => {
  it('去掉 /skill:name 前缀，保留参数', () => {
    expect(stripSkillPrefix('/skill:portfolio-entry 分析茅台')).toBe('分析茅台');
  });
});

describe('adaptSearchResults', () => {
  it('MemorySearchResult → RecallHit 字段映射', () => {
    const results: MemorySearchResult[] = [
      { id: 1, title: 't1', content: 'c1', score: 0.8, source: 'both' },
      { id: 2, title: 't2', content: 'c2', score: 0.5, source: 'vector' },
    ];
    const hits = adaptSearchResults(results);

    expect(hits).toHaveLength(2);
    expect(hits[0]).toMatchObject({ id: 1, score: 0.8, source: 'both', title: 't1', content: 'c1' });
    expect(hits[1].source).toBe('vector');
  });

  it('过滤非数字 id + 未知 source 归一为 bm25', () => {
    const results: MemorySearchResult[] = [
      { title: 'no-id', content: 'c', score: 0.5, source: 'bm25' },
      { id: 5, title: 'ok', content: 'c5', score: 0.7, source: 'unknown' },
    ];
    const hits = adaptSearchResults(results);

    expect(hits).toHaveLength(1);
    expect(hits[0].id).toBe(5);
    expect(hits[0].source).toBe('bm25');
  });
});
