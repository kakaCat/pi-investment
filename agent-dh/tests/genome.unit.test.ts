/**
 * genome 插件单元测试（RFC 007 欠账补齐，2026-08-25）
 * 覆盖：guard（宪法拒绝/花括号/大小/规则ID/乐观锁/文件锁/交易时段）
 *      versioning（版本推进/回滚/上一版本兜底/promote）
 *      store（版本号递增/规则增删对比/原子写）
 * 纯函数级测试，不依赖 cordis ctx（Service 构造由 plugin-schema 冒烟测试覆盖）。
 */
import { describe, expect, it, beforeAll, afterAll, vi } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
  GenomeLock,
  guardConstitution,
  validateBraces,
  validateSize,
  validateAndExtractRuleIds,
  extractRuleDefinitions,
  validateVersion,
  checkTradingHours,
} from '../packages/genome/src/guard';
import {
  incrementGenomeVersion,
  writeGenomeJson,
  readGenomeJson,
  writeSection,
  readSection,
  computeRuleIdChanges,
  trimHistory,
} from '../packages/genome/src/store';
import {
  advanceVersion,
  getPreviousSectionVersion,
  promoteCandidate,
} from '../packages/genome/src/versioning';

let stateDir: string;
beforeAll(() => { stateDir = mkdtempSync(join(tmpdir(), 'genome-unit-')); });
afterAll(() => rmSync(stateDir, { recursive: true, force: true }));

const baseGenome = () => ({
  genome_version: 'g1',
  updated_at: new Date().toISOString(),
  sections: {
    constitution: { class: 'constitution' as const, version: 1, order: 10, locked: true },
    principles: { class: 'evolvable' as const, version: 1, order: 20 },
    rules: { class: 'evolvable' as const, version: 2, order: 30 },
  },
  history: [],
});

describe('guard: 宪法与内容校验', () => {
  it('guardConstitution 拒绝 constitution 段', () => {
    expect(() => guardConstitution('constitution', baseGenome())).toThrow(/宪法层段/);
  });
  it('guardConstitution 放行 evolvable 段，未知段报 Section not found', () => {
    expect(() => guardConstitution('principles', baseGenome())).not.toThrow();
    expect(() => guardConstitution('nope', baseGenome())).toThrow(/Section not found/);
  });
  it('validateBraces 拒绝未注册变量，放行 genome_version', () => {
    expect(() => validateBraces('引用 {{unknown_var}} 的内容', 'rules')).toThrow(/未注册变量/);
    expect(() => validateBraces('引用 {{genome_version}} 的内容', 'rules')).not.toThrow();
    expect(() => validateBraces('无花括号内容', 'rules')).not.toThrow();
  });
  it('validateSize 超过 8000 字符拒绝', () => {
    expect(() => validateSize('x'.repeat(8001), 'rules')).toThrow(/超限/);
    expect(() => validateSize('x'.repeat(100), 'rules')).not.toThrow();
  });
  it('validateVersion 乐观锁：版本不符抛冲突', () => {
    expect(() => validateVersion(1, 2, 'rules')).toThrow(/版本冲突/);
    expect(() => validateVersion(2, 2, 'rules')).not.toThrow();
    expect(() => validateVersion(undefined, 2, 'rules')).not.toThrow();  // 不传不校验
  });
});

describe('guard: 规则 ID 定义行口径（正文引用不算定义）', () => {
  it('extractRuleDefinitions 只取标题行', () => {
    const content = '## R-001 买入前确认\n正文中提到 R-001 是引用。\n## R-002 卖出前确认\n### R-003 拆单';
    expect(extractRuleDefinitions(content).sort()).toEqual(['R-001', 'R-002', 'R-003']);
  });
  it('重复定义拦截，正文引用不误判', () => {
    expect(() => validateAndExtractRuleIds('## R-001 甲\n## R-001 乙', 'rules')).toThrow(/重复定义/);
    expect(() => validateAndExtractRuleIds('## R-001 甲\n正文参考 R-001 不犯规', 'rules')).not.toThrow();
  });
  it('非 rules 段直接放行', () => {
    expect(validateAndExtractRuleIds('## R-001 随便写', 'lessons').ids).toEqual([]);
  });
});

describe('guard: 文件锁', () => {
  it('拿锁-释放-重拿', () => {
    const lock = new GenomeLock(stateDir);
    lock.acquire();
    expect(existsSync(join(stateDir, 'genome.lock'))).toBe(true);
    lock.release();
    expect(existsSync(join(stateDir, 'genome.lock'))).toBe(false);
    lock.acquire();
    lock.release();
  });
  it('锁占用时拒写，stale（>5min）可接管', () => {
    const lockPath = join(stateDir, 'genome.lock');
    writeFileSync(lockPath, '{}');
    const lock = new GenomeLock(stateDir);
    expect(() => lock.acquire()).toThrow(/写锁被占用/);
    // 手工改 mtime 为 10 分钟前 → stale 接管
    const old = new Date(Date.now() - 10 * 60 * 1000);
    const { utimesSync } = require('node:fs');
    utimesSync(lockPath, old, old);
    expect(() => lock.acquire()).not.toThrow();
    lock.release();
  });
});

describe('guard: 交易时段检查', () => {
  it('交易时段内 force=false 拒改，force=true 放行带警告', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-08-26T10:00:00+08:00'));  // 周三上午盘中
    expect(() => checkTradingHours(false)).toThrow(/交易时段/);
    const r = checkTradingHours(true);
    expect(r.warning).toContain('force=true');
    vi.useRealTimers();
  });
  it('非交易时段与周末放行', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-08-26T20:00:00+08:00'));  // 周三晚
    expect(checkTradingHours(false)).toEqual({});
    vi.setSystemTime(new Date('2026-08-23T10:00:00+08:00'));  // 周日盘中时刻
    expect(checkTradingHours(false)).toEqual({});
    vi.useRealTimers();
  });
});

describe('store: 版本号与规则增删', () => {
  it('incrementGenomeVersion g1→g2，非法格式抛错', () => {
    expect(incrementGenomeVersion('g1')).toBe('g2');
    expect(incrementGenomeVersion('g41')).toBe('g42');
    expect(() => incrementGenomeVersion('v2')).toThrow(/Invalid genome_version/);
  });
  it('computeRuleIdChanges 按定义行算增删', () => {
    const oldC = '## R-001 甲\n## R-002 乙';
    const newC = '## R-002 乙改\n## R-005 新规则（正文提到 R-001 是引用）';
    const diff = computeRuleIdChanges(oldC, newC);
    expect(diff.added).toEqual(['R-005']);
    expect(diff.removed).toEqual(['R-001']);
  });
  it('genome.json/段文件原子写读回一致', () => {
    const dir = join(stateDir, 'atomic');
    const data = baseGenome() as any;
    writeGenomeJson(dir, data);
    expect(readGenomeJson(dir).genome_version).toBe('g1');
    writeSection(dir, 'principles', '# 原则 v1');
    expect(readSection(dir, 'principles')).toBe('# 原则 v1');
  });
  it('trimHistory 截尾保留最近 N 条', () => {
    const h = Array.from({ length: 60 }, (_, i) => ({ n: i }) as any);
    const t = trimHistory(h, 50);
    expect(t.length).toBe(50);
    expect((t[0] as any).n).toBe(10);
  });
});

describe('versioning: 版本推进与回滚兜底', () => {
  it('advanceVersion 代数+1、段版本+1、history 追加', () => {
    const g = baseGenome();
    const entry: any = { version: '', section: 'rules', section_version: 3, parent: 'g1', reason: 'test', ts: '', author: 'agent', type: 'update' };
    const ng = advanceVersion(g, 'rules', entry);
    expect(ng.genome_version).toBe('g2');
    expect(ng.sections.rules.version).toBe(3);
    expect(ng.history!.length).toBe(1);
    expect(ng.history![0].version).toBe('g2');
  });
  it('getPreviousSectionVersion：history≥2 取次新，不足时兜底 current-1，v1 返回 null', () => {
    const g = baseGenome() as any;  // rules v2，无 history → 兜底 v2-1=1
    expect(getPreviousSectionVersion(g, 'rules')).toBe(1);
    g.sections.rules.version = 1;
    expect(getPreviousSectionVersion(g, 'rules')).toBeNull();
    g.sections.rules.version = 3;
    g.history = [
      { section: 'rules', section_version: 3 },
      { section: 'rules', section_version: 2 },
    ];
    expect(getPreviousSectionVersion(g, 'rules')).toBe(2);
  });
  it('promoteCandidate：最新 candidate 转 active + promote 谱系；无 candidate 抛错', () => {
    const g = baseGenome() as any;
    g.history = [
      { version: 'g2', section: 'rules', section_version: 2, parent: 'g1', reason: 'x', ts: '', author: 'agent', type: 'update', stage: 'candidate' },
    ];
    const ng = promoteCandidate(g, 'rules', '观察期达标');
    expect(ng.history![0].stage).toBe('active');
    expect(ng.history![1].type).toBe('promote');
    expect(() => promoteCandidate(g, 'principles', '没有候选')).toThrow(/没有观察中的 candidate/);
  });
});
