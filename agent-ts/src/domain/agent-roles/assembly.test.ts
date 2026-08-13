import { describe, test, expect } from '@jest/globals';
import { allCustomTools } from '../../infrastructure/tools/index.js';
import {
  SHARED_BASE_TOOLS,
  FIN_TOOLS,
  EVOLUTION_TOOLS,
  MEMORY_TOOLS,
} from '../../infrastructure/tools/groups.js';
import { selectToolsForKind } from './assembly.js';
import { buildSystemPrompt } from '../../services/intelligence/system-prompt-builder.js';

const names = (tools: readonly { name: string }[]) => tools.map((t) => t.name);

describe('Agent Tool Assembly (selectToolsForKind)', () => {
  test('fin 等价性铁律：返回列表与 allCustomTools 逐元素一致（零过滤、零重排、同引用）', () => {
    const result = selectToolsForKind('fin', allCustomTools);

    expect(result).toHaveLength(allCustomTools.length);
    expect(names(result)).toEqual(names(allCustomTools));
    // 铁律更强：元素对象引用也完全一致（不是重新构造的等价对象）
    result.forEach((tool, i) => {
      expect(tool).toBe(allCustomTools[i]);
    });
  });

  test('fin 保留「归属别组」的工具（memory_write / evolution_run 等）', () => {
    const result = names(selectToolsForKind('fin', allCustomTools));
    expect(result).toContain('memory_write');
    expect(result).toContain('memory_search');
    expect(result).toContain('evolution_run');
    expect(result).toContain('claude_code');
  });

  test('memory 工具列表不含交易/池/组合写工具', () => {
    const result = names(selectToolsForKind('memory', allCustomTools));

    // 结构隔离：无任何 trade_* / pool_* / portfolio_* 写工具
    expect(result.filter((n) => n.startsWith('trade_'))).toEqual([]);
    expect(result.filter((n) => n.startsWith('pool_'))).toEqual([]);
    expect(result.filter((n) => n.startsWith('portfolio_'))).toEqual([]);

    // 但保留记忆工具与基础工具
    expect(result).toContain('memory_write');
    expect(result).toContain('memory_search');
    expect(result).toContain('plan_task');
    expect(result).toContain('task_create');
  });

  test('memory/evolution 不含进程控制工具 restart_agent；fin 保留（批次6实证：memory agent 曾自主调用 restart_agent）', () => {
    expect(names(selectToolsForKind('memory', allCustomTools))).not.toContain('restart_agent');
    expect(names(selectToolsForKind('evolution', allCustomTools))).not.toContain('restart_agent');
    expect(names(selectToolsForKind('fin', allCustomTools))).toContain('restart_agent');
  });

  test('memory = SHARED_BASE + MEMORY_TOOLS（精确集合相等）', () => {
    const expected = [...SHARED_BASE_TOOLS, ...MEMORY_TOOLS];
    const result = selectToolsForKind('memory', allCustomTools);
    expect(new Set(names(result))).toEqual(new Set(names(expected)));
  });

  test('evolution = SHARED_BASE + EVOLUTION_TOOLS（精确集合相等）', () => {
    const expected = [...SHARED_BASE_TOOLS, ...EVOLUTION_TOOLS];
    const result = selectToolsForKind('evolution', allCustomTools);
    expect(new Set(names(result))).toEqual(new Set(names(expected)));
    expect(names(result)).toContain('evolution_run');
    expect(names(result)).toContain('evolution_leaderboard');
    expect(names(result)).toContain('claude_code');
  });

  test('FIN_TOOLS 与 MEMORY_TOOLS / EVOLUTION_TOOLS 无交集（结构隔离基础）', () => {
    const finNames = new Set(names(FIN_TOOLS));
    expect(names(MEMORY_TOOLS).some((n) => finNames.has(n))).toBe(false);
    expect(names(EVOLUTION_TOOLS).some((n) => finNames.has(n))).toBe(false);
  });
});

describe('Prompt Variant (VARIANT_IDENTITY 注入点)', () => {
  const base = {
    bootstrap: {
      'IDENTITY.md': '测试身份',
      'SOUL.md': '测试人格',
    },
    date: '2026-08-13',
    cwd: '/tmp',
    model: 'deepseek-v4-flash',
    mode: 'full' as const,
  };

  test('变体隔离：evolution/memory 各带身份块；fin 不含任何变体块（铁律）', () => {
    const fin = buildSystemPrompt({ ...base, promptVariant: 'fin' });
    const evolution = buildSystemPrompt({ ...base, promptVariant: 'evolution' });
    const memory = buildSystemPrompt({ ...base, promptVariant: 'memory' });

    // A1-T1/A2-T1 已落地：memory/evolution 变体各携带身份块，fin 两者皆无（隔离语义锁定）
    expect(memory).toContain('Memory Agent');
    expect(evolution).toContain('Evolution Agent');
    expect(fin).not.toContain('Memory Agent');
    expect(fin).not.toContain('Evolution Agent');
    expect(memory).not.toEqual(fin);
    expect(evolution).not.toEqual(fin);
    expect(memory).not.toEqual(evolution);
    // 变体与 fin 的差异只允许来自 VARIANT_IDENTITY 追加块（首行前缀一致）
    expect(memory.startsWith(fin.split('\n')[0])).toBe(true);
    expect(evolution.startsWith(fin.split('\n')[0])).toBe(true);
  });

  test('缺省 promptVariant 等价于显式 fin', () => {
    const explicit = buildSystemPrompt({ ...base, promptVariant: 'fin' });
    const implicit = buildSystemPrompt({ ...base });
    expect(implicit).toEqual(explicit);
  });
});
