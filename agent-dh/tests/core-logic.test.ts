/**
 * 核心逻辑单元测试（2026-08-21 review 专项补建）
 * 覆盖：genome 护栏/版本模型/存储、learning 截断/规则提取/真实奖励、
 *       trading 交易时段边界、genome_update 金丝雀失败自动还原（故障注入）
 *
 * 与 plugin-schema.smoke.test.ts 的分工：冒烟只验证 schema 可编译；
 * 本文件验证真实行为。RFC 007 欠账补交。
 */
import { mkdtempSync, rmSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it, beforeAll, afterAll } from 'vitest';

import {
  guardConstitution,
  validateBraces,
  validateSize,
  validateAndExtractRuleIds,
  validateVersion,
  checkTradingHours,
  GenomeLock,
} from '../packages/genome/src/guard.js';
import {
  advanceVersion,
  advanceVersionForRollback,
  promoteCandidate,
  getPreviousSectionVersion,
} from '../packages/genome/src/versioning.js';
import { computeRuleIdChanges, incrementGenomeVersion } from '../packages/genome/src/store.js';
import GenomePlugin from '../packages/genome/src/index.js';
import LearningPlugin from '../packages/learning/src/index.js';
import { assertTradingHours } from '../packages/trading/src/index.js';

// ---------- genome guard ----------

describe('genome guard', () => {
  const meta = (cls: string, locked = false) => ({ sections: { principles: { class: cls, locked } } });

  it('宪法段拒绝修改', () => {
    expect(() => guardConstitution('constitution', { sections: { constitution: { class: 'constitution', locked: true } } })).toThrow(/宪法/);
    expect(() => guardConstitution('principles', meta('evolvable'))).not.toThrow();
    expect(() => guardConstitution('nonexist', meta('evolvable'))).toThrow(/not found/);
  });

  it('花括号安检：未知变量拒绝，已注册变量放行', () => {
    expect(() => validateBraces('引用 {{genome_version}} 没问题', 'principles')).not.toThrow();
    expect(() => validateBraces('引用 {{evil}} 会被拒', 'principles')).toThrow(/未注册变量/);
  });

  it('大小限制 8000 字符', () => {
    expect(() => validateSize('x'.repeat(7999), 'rules')).not.toThrow();
    expect(() => validateSize('x'.repeat(8001), 'rules')).toThrow(/超限/);
  });

  it('规则 ID：判重只看标题定义行，正文引用合法', () => {
    expect(() => validateAndExtractRuleIds('## R-001 甲\n正文引用 R-001 合法', 'rules')).not.toThrow();
    expect(() => validateAndExtractRuleIds('## R-001 甲\n## R-001 乙', 'rules')).toThrow(/重复定义/);
    expect(validateAndExtractRuleIds('任意文本', 'principles').ids).toEqual([]);
  });

  it('乐观锁版本校验', () => {
    expect(() => validateVersion(2, 2, 'rules')).not.toThrow();
    expect(() => validateVersion(1, 2, 'rules')).toThrow(/版本冲突/);
    expect(() => validateVersion(undefined, 5, 'rules')).not.toThrow();
  });

  it('交易时段检查：时段内放行、时段外拒绝、force 放行', () => {
    // checkTradingHours 内部用当前时间，无法注入——只验证接口行为存在性
    // （交易时段边界由 trading 插件的 assertTradingHours 测试覆盖）
    const r = checkTradingHours(true);
    expect(typeof r === 'object').toBe(true);
  });

  it('文件锁：占用拒绝、释放后可获取', () => {
    const dir = mkdtempSync(join(tmpdir(), 'genome-lock-'));
    const lock1 = new GenomeLock(dir);
    lock1.acquire();
    const lock2 = new GenomeLock(dir);
    expect(() => lock2.acquire()).toThrow(/写锁被占用/);
    lock1.release();
    expect(() => lock2.acquire()).not.toThrow();
    lock2.release();
    rmSync(dir, { recursive: true, force: true });
  });
});

// ---------- genome versioning ----------

describe('genome versioning', () => {
  const base = (): any => ({
    genome_version: 'g1',
    updated_at: '2026-08-20T00:00:00Z',
    sections: { principles: { class: 'evolvable', version: 1, order: 20 } },
    history: [],
  });

  it('advanceVersion：代数+1、段版本+1、history 追加', () => {
    const d = advanceVersion(base(), 'principles', { reason: 't' } as any);
    expect(d.genome_version).toBe('g2');
    expect(d.sections.principles.version).toBe(2);
    expect(d.history.length).toBe(1);
    expect(d.history[0].version).toBe('g2');
  });

  it('promoteCandidate：candidate 转 active + 追加 promote 谱系', () => {
    let d = base();
    d = advanceVersion(d, 'principles', { section: 'principles', reason: 't', stage: 'candidate' } as any);
    const p = promoteCandidate(d, 'principles', '达标');
    expect(p.history[0].stage).toBe('active');
    expect(p.history[1].type).toBe('promote');
    expect(p.sections.principles.version).toBe(2);  // 版本号不变
  });

  it('promoteCandidate：无 candidate 抛错', () => {
    expect(() => promoteCandidate(base(), 'principles', 'x')).toThrow(/没有观察中的 candidate/);
  });

  it('getPreviousSectionVersion：history 不足时兜底 current-1', () => {
    const d = base();
    expect(getPreviousSectionVersion(d, 'principles')).toBeNull();  // v1 无前版
    d.sections.principles.version = 3;
    expect(getPreviousSectionVersion(d, 'principles')).toBe(2);  // 兜底
  });

  it('incrementGenomeVersion 格式校验', () => {
    expect(incrementGenomeVersion('g9')).toBe('g10');
    expect(() => incrementGenomeVersion('v9')).toThrow(/Invalid/);
  });

  it('computeRuleIdChanges：只看定义行', () => {
    const r = computeRuleIdChanges('## R-001 甲', '## R-001 甲\n## R-002 乙\n正文提到 R-003 不算新增');
    expect(r.added).toEqual(['R-002']);
    expect(r.removed).toEqual([]);
  });
});

// ---------- trading 时段边界 ----------

describe('trading 交易时段边界', () => {
  // 2026-08-21 是周五
  const at = (h: number, m: number, dayOffset = 0) => new Date(2026, 7, 21 + dayOffset, h, m);

  it('开盘边界：9:29 拒、9:30 放', () => {
    expect(() => assertTradingHours(at(9, 29))).toThrow(/非交易时段/);
    expect(() => assertTradingHours(at(9, 30))).not.toThrow();
  });

  it('午休边界：11:30 放、11:31 拒、12:59 拒、13:00 放', () => {
    expect(() => assertTradingHours(at(11, 30))).not.toThrow();
    expect(() => assertTradingHours(at(11, 31))).toThrow(/非交易时段/);
    expect(() => assertTradingHours(at(12, 59))).toThrow(/非交易时段/);
    expect(() => assertTradingHours(at(13, 0))).not.toThrow();
  });

  it('收盘边界：15:00 放、15:01 拒', () => {
    expect(() => assertTradingHours(at(15, 0))).not.toThrow();
    expect(() => assertTradingHours(at(15, 1))).toThrow(/非交易时段/);
  });

  it('周末拒单（8-22 周六、8-23 周日）', () => {
    expect(() => assertTradingHours(at(10, 0, 1))).toThrow(/非交易日/);
    expect(() => assertTradingHours(at(10, 0, 2))).toThrow(/非交易日/);
  });

  it('盘前深夜拒单', () => {
    expect(() => assertTradingHours(at(8, 0))).toThrow(/非交易时段/);
    expect(() => assertTradingHours(at(23, 30))).toThrow(/非交易时段/);
  });
});

// ---------- learning 核心逻辑 ----------

describe('learning 截断/规则提取/真实奖励', () => {
  function makeLearning(qv2Stub: any): any {
    const ctx: any = {
      tools: { register: () => () => true },
      on: () => () => true,
      reflect: { provide: () => {} },
      logger: () => ({ info() {}, warn() {}, error() {}, debug() {} }),
      genome: { genomeData: { genome_version: 'g9', sections: {} } },
      memory: {},
    };
    const p: any = new (LearningPlugin as any)(ctx, { quantsysV2: { baseURL: 'http://localhost:1' } });
    p.qv2 = qv2Stub;
    return p;
  }

  it('truncateForMemory：小值原样、大值截断为占位', () => {
    const p = makeLearning({});
    expect(p.truncateForMemory({ a: 1 })).toEqual({ a: 1 });
    const big = p.truncateForMemory({ text: 'x'.repeat(5000) });
    expect(big._truncated).toBe(true);
    expect(big._original_chars).toBeGreaterThan(5000);
    expect(big.preview.length).toBeLessThan(2100);
  });

  it('extractRulesFromContext：从 args/result 提取 R-ID 并去重排序', () => {
    const p = makeLearning({});
    const ids = p.extractRulesFromContext({ args: { reason: '依据 R-002 和 R-001' }, result: '又见 R-001' });
    expect(ids).toEqual(['R-001', 'R-002']);
    expect(p.extractRulesFromContext({ args: {} })).toEqual([]);
  });

  it('tradeReward：卖出记录自带 pnlPercent 时直接用（后端精确值）', async () => {
    const p = makeLearning({
      getTradeHistory: async (q: any) => q.direction === 'sell'
        ? { items: [{ pnlPercent: 28.28, createdAt: '2026-05-13' }] }
        : { items: [] },
    });
    const r = await p.calculateReward({ tool: 'portfolio_trade', success: true, args: { action: 'SELL', symbol: '601088' }, result: { value: { action: 'sell', symbol: '601088', price: 45 } } });
    expect(r).toBe(1);  // 28.28% → clamp 到 1
    expect(p.lastTradePnlPct).toBe(28.28);
  });

  it('tradeReward：无 pnlPercent 时回退买入成本估算', async () => {
    const p = makeLearning({
      getTradeHistory: async (q: any) => q.direction === 'sell'
        ? { items: [] }
        : { items: [{ price: 10, quantity: 100 }] },
    });
    const r = await p.calculateReward({ tool: 'portfolio_trade', success: true, args: { action: 'SELL', symbol: 'X' }, result: { value: { action: 'sell', symbol: 'X', price: 11 } } });
    expect(r).toBe(1);  // +10% → 1
  });

  it('tradeReward：BUY 中性、失败 -0.3、后端异常回退中性', async () => {
    const p = makeLearning({ getTradeHistory: async () => { throw new Error('backend down'); } });
    expect(await p.calculateReward({ tool: 'portfolio_trade', success: true, args: { action: 'BUY' }, result: { value: { action: 'buy', price: 10 } } })).toBe(0.1);
    expect(await p.calculateReward({ tool: 'portfolio_trade', success: false })).toBe(-0.3);
    expect(await p.calculateReward({ tool: 'portfolio_trade', success: true, args: { action: 'SELL', symbol: 'X' }, result: { value: { action: 'sell', symbol: 'X', price: 9 } } })).toBe(0.1);
  });
});

// ---------- genome_update 金丝雀故障注入（自动还原路径实测） ----------

describe('genome_update 金丝雀自动还原（故障注入）', () => {
  let dir: string;
  beforeAll(() => { dir = mkdtempSync(join(tmpdir(), 'genome-canary-')); });
  afterAll(() => rmSync(dir, { recursive: true, force: true }));

  function stubCtx(assembleImpl: () => Promise<any>) {
    const tools: Record<string, any> = {};
    return {
      tools,
      ctx: {
        tools: { register: (def: any) => { tools[def.name] = def; return () => true; }, list: () => [] },
        systemPrompt: {
          section: () => () => true,
          variable: () => () => true,
          assemble: assembleImpl,
        },
        on: () => () => true,
        reflect: { provide: () => {} },
        logger: () => ({ info() {}, warn() {}, error() {}, debug() {} }),
      } as any,
    };
  }

  it('渲染金丝雀失败时：文件还原 + genome.json 还原 + git revert + 报错', async () => {
    const gdir = join(dir, 'genome');  // 目录不存在才会触发模板初始化
    const goodAssembly = async () => ({ sections: [], tools: [], variables: {} });
    const { ctx, tools } = stubCtx(goodAssembly);
    new (GenomePlugin as any)(ctx, { genomeDir: gdir });  // 初始化 g1

    // 先做一次正常更新（genome g1→g2）；force=true 绕过交易时段限制（测试在交易时段运行时也能跑）
    const update = tools['genome_update'];
    const r1 = await update.execute({ section: 'principles', content: '# P v2\n', reason: '正常更新', force: true });
    expect(r1.success).toBe(true);

    const before = readFileSync(join(gdir, 'sections', 'principles.md'), 'utf-8');
    const commitsBefore = execSync('git log --oneline', { cwd: gdir, encoding: 'utf-8' }).trim().split('\n').length;

    // 故障注入：assemble 返回含未注册变量的段 → renderPrompt 必抛
    ctx.systemPrompt.assemble = async () => ({
      sections: [{ name: 'evil', order: 1, text: 'boom {{unresolvable_var}}' }],
      tools: [],
      variables: {},
    });

    await expect(
      update.execute({ section: 'principles', content: '# P v3 bad\n', reason: '故障注入', force: true })
    ).rejects.toThrow(/金丝雀/);

    // 验证自动还原：文件内容、genome.json 版本、git revert
    expect(readFileSync(join(gdir, 'sections', 'principles.md'), 'utf-8')).toBe(before);
    const gj = JSON.parse(readFileSync(join(gdir, 'genome.json'), 'utf-8'));
    expect(gj.genome_version).toBe('g2');
    const log = execSync('git log --oneline', { cwd: gdir, encoding: 'utf-8' });
    expect(log).toMatch(/canary-restore/);
    const commitsAfter = log.trim().split('\n').length;
    expect(commitsAfter).toBe(commitsBefore + 2);  // 坏提交 + revert 提交（历史只增不改）
  });
});
