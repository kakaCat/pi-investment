import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { canAutoRollback } from '../src/rollbackGuard';
import { ValidationGateTool } from '../src/tools/ValidationGateTool/ValidationGateTool';

/**
 * 自动回滚守卫测试（2026-09-12，w-adb088f2）
 *
 * 风险：validation_gate 的"显著恶化→回滚"分支用固化在候选记录里的
 * to_section_version = c.section_version - 1 调 genome_rollback，而该工具无 staleness 守卫
 * （按绝对版本取内容后直接覆盖当前段）。rules 段同时挂多条 watching 候选时，
 * 任一条迟到裁决都可能抹掉其后的变更。
 *
 * 契约：**只有候选 section_version === 该段当前版本时才允许自动回滚**；信息缺失 fail-closed。
 * 集成用例直接驱动真实 judgeCandidates（不抄逻辑自证）。
 */

const CAND = (over: Record<string, any> = {}) => ({
  id: 'cand_test_stale',
  section: 'rules',
  section_version: 17,
  genome_version: 'g99',
  baseline_version: 'g98',
  created_at: new Date().toISOString(),
  observe_until: new Date(Date.now() - 86400000).toISOString(),
  status: 'watching',
  mutation_type: 'prompt',
  health_check: { passed: true, checked_at: new Date().toISOString(), issues: [], size_delta: 622, substantive: true },
  ...over,
});

function makeGate(opts: { candidates: any[]; currentVersion: number | null }) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gate-guard-'));
  fs.mkdirSync(path.join(dir, 'sections'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'candidates.json'), JSON.stringify(opts.candidates, null, 2), 'utf-8');
  if (opts.currentVersion !== null) {
    fs.writeFileSync(
      path.join(dir, 'genome.json'),
      JSON.stringify({ genome_version: 'g99', sections: { rules: { version: opts.currentVersion } } }, null, 2),
      'utf-8',
    );
  }
  const calls: Array<{ name: string; args: any }> = [];
  const ctx: any = {
    genome: { genomeDir: dir },
    tools: {
      execute: async (req: any) => {
        calls.push({ name: req.name, args: req.arguments });
        return { value: { success: true } };
      },
    },
  };
  const tool: any = new ValidationGateTool(ctx, {} as any, 5);
  // 打桩奖励查询：candidate 期 -0.5 vs 基准 0.0 → drop=0.5 > 0.1，稳定进入回滚分支
  tool.searchRewards = async (v: string) => ({ count: 5, avg: v === 'g99' ? -0.5 : 0.0 });
  return { tool, calls, dir };
}

describe('canAutoRollback 纯函数', () => {
  it('候选仍是当前版本 → 允许', () => {
    const d = canAutoRollback({ id: 'c', section: 'rules', section_version: 17 }, 17);
    expect(d.allowed).toBe(true);
    expect(d.reason).toContain('v17');
  });

  it('候选已被后续变更取代 → 拒绝（核心不变量）', () => {
    const d = canAutoRollback({ id: 'c', section: 'rules', section_version: 17 }, 18);
    expect(d.allowed).toBe(false);
    expect(d.reason).toContain('已被后续变更取代');
  });

  it('当前版本不可读 → 拒绝（fail-closed）', () => {
    expect(canAutoRollback({ id: 'c', section: 'rules', section_version: 17 }, null).allowed).toBe(false);
    expect(canAutoRollback({ id: 'c', section: 'rules', section_version: 17 }, undefined).allowed).toBe(false);
  });

  it('候选 section_version 非法 → 拒绝', () => {
    expect(canAutoRollback({ id: 'c', section: 'rules' } as any, 17).allowed).toBe(false);
    expect(canAutoRollback({ id: 'c', section: 'rules', section_version: 0 }, 0).allowed).toBe(false);
  });
});

describe('集成：验证门遇到陈旧候选不执行破坏性回滚', () => {
  let dirs: string[] = [];
  afterEach(() => {
    for (const d of dirs) fs.rmSync(d, { recursive: true, force: true });
    dirs = [];
  });

  it('陈旧候选（记 17 / 当前 18）→ 不调 genome_rollback，判 rejected_no_rollback 并留 note', async () => {
    const h = makeGate({ candidates: [CAND()], currentVersion: 18 });
    dirs.push(h.dir);
    const verdicts: any[] = await h.tool.judgeCandidates(true, 1);

    expect(h.calls.filter((c) => c.name === 'genome_rollback').length).toBe(0);
    expect(verdicts[0].verdict).toBe('rejected_no_rollback');
    expect(String(verdicts[0].note)).toContain('守卫');
    const saved = JSON.parse(fs.readFileSync(path.join(h.dir, 'candidates.json'), 'utf-8'));
    expect(saved[0].status).toBe('rejected');
    expect(String(saved[0].note)).toContain('已被后续变更取代');
  });

  it('候选仍为当前版本（记 18 / 当前 18）→ 正常回滚到 v17', async () => {
    const h = makeGate({ candidates: [CAND({ id: 'cand_head', section_version: 18 })], currentVersion: 18 });
    dirs.push(h.dir);
    const verdicts: any[] = await h.tool.judgeCandidates(true, 1);

    const rb = h.calls.filter((c) => c.name === 'genome_rollback');
    expect(rb.length).toBe(1);
    expect(rb[0].args.to_section_version).toBe(17);
    expect(verdicts[0].verdict).toBe('rejected');
  });

  it('当前版本不可读（无 genome.json）→ fail-closed，不调 genome_rollback', async () => {
    const h = makeGate({ candidates: [CAND()], currentVersion: null });
    dirs.push(h.dir);
    const verdicts: any[] = await h.tool.judgeCandidates(true, 1);

    expect(h.calls.filter((c) => c.name === 'genome_rollback').length).toBe(0);
    expect(verdicts[0].verdict).toBe('rejected_no_rollback');
  });

  it('双登记场景：第一条回滚成功后（版本推进），第二条同版本候选被守卫拦下', async () => {
    // 复刻 genome_rollback 的真实副作用：回滚后段版本推进（17 → 18），
    // 于是"同 section_version=17"的第二条候选不再是当前版本 → 必须被拦。
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gate-guard-dup-'));
    dirs.push(dir);
    fs.mkdirSync(path.join(dir, 'sections'), { recursive: true });
    fs.writeFileSync(
      path.join(dir, 'candidates.json'),
      JSON.stringify([CAND({ id: 'dup_a' }), CAND({ id: 'dup_b' })], null, 2),
      'utf-8',
    );
    fs.writeFileSync(
      path.join(dir, 'genome.json'),
      JSON.stringify({ genome_version: 'g99', sections: { rules: { version: 17 } } }),
      'utf-8',
    );

    const calls: Array<{ name: string; args: any }> = [];
    const ctx: any = {
      genome: { genomeDir: dir },
      tools: {
        execute: async (req: any) => {
          calls.push({ name: req.name, args: req.arguments });
          if (req.name === 'genome_rollback') {
            // 真推进版本，模拟破坏性动作的后果
            const gp = path.join(dir, 'genome.json');
            const g = JSON.parse(fs.readFileSync(gp, 'utf-8'));
            g.sections.rules.version = 18;
            fs.writeFileSync(gp, JSON.stringify(g), 'utf-8');
          }
          return { value: { success: true } };
        },
      },
    };
    const tool: any = new ValidationGateTool(ctx, {} as any, 5);
    tool.searchRewards = async (v: string) => ({ count: 5, avg: v === 'g99' ? -0.5 : 0.0 });

    const verdicts: any[] = await tool.judgeCandidates(true, 1);
    expect(verdicts.length).toBe(2);
    expect(verdicts[0].verdict).toBe('rejected');                 // 第一条仍为当前版本 → 正常回滚
    expect(verdicts[1].verdict).toBe('rejected_no_rollback');      // 第二条已被取代 → 守卫拦下
    expect(calls.filter((c) => c.name === 'genome_rollback').length).toBe(1);
    expect(String(verdicts[1].note)).toContain('守卫');
  });
});
