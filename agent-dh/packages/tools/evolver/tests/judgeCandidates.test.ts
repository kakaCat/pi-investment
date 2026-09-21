import { describe, it, expect, afterEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { ValidationGateTool } from '../src/tools/ValidationGateTool/ValidationGateTool';

/**
 * 验证门 judgeCandidates 真实实现测试（2026-09-12，w-adb088f2 重写）
 *
 * 旧版本把判定逻辑**抄进测试**再断言副本（自证）：生产代码改坏了测试也不会红。
 * 本版直接实例化 ValidationGateTool、种入 candidates.json/genome.json、打桩 searchRewards，
 * 断言真实 verdict 与真实副作用（genome_promote / genome_rollback 调用）。
 */

const PAST = () => new Date(Date.now() - 86400000).toISOString();

const makeCand = (over: Record<string, any> = {}) => ({
  id: 'cand_jc_1',
  section: 'rules',
  section_version: 17,
  genome_version: 'g30',
  baseline_version: 'g29',
  created_at: new Date().toISOString(),
  observe_until: PAST(),
  status: 'watching',
  mutation_type: 'prompt',
  health_check: { passed: true, checked_at: new Date().toISOString(), issues: [], size_delta: 100, substantive: true },
  ...over,
});

function makeGate(opts: {
  candidate: any;
  currentVersion?: number;
  candRewards?: { count: number; avg: number };
  baseRewards?: { count: number; avg: number };
}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gate-jc-'));
  fs.mkdirSync(path.join(dir, 'sections'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'candidates.json'), JSON.stringify([opts.candidate], null, 2), 'utf-8');
  fs.writeFileSync(
    path.join(dir, 'genome.json'),
    JSON.stringify({ genome_version: 'g31', sections: { rules: { version: opts.currentVersion ?? opts.candidate.section_version } } }),
    'utf-8',
  );
  const calls: Array<{ name: string; args: any }> = [];
  const ctx: any = {
    genome: { genomeDir: dir },
    tools: { execute: async (req: any) => { calls.push({ name: req.name, args: req.arguments }); return { value: { success: true } }; } },
  };
  const tool: any = new ValidationGateTool(ctx, {} as any, 5);
  const candR = opts.candRewards ?? { count: 5, avg: 0.0 };
  const baseR = opts.baseRewards ?? { count: 5, avg: 0.0 };
  tool.searchRewards = async (v: string) => (v === opts.candidate.genome_version ? candR : baseR);
  return { tool, calls, dir };
}

describe('judgeCandidates（驱动真实实现）', () => {
  const dirs: string[] = [];
  afterEach(() => { for (const d of dirs) fs.rmSync(d, { recursive: true, force: true }); dirs.length = 0; });

  it('零样本 → 延期（extended）且不转正不调工具', async () => {
    const h = makeGate({ candidate: makeCand(), candRewards: { count: 0, avg: 0 } });
    dirs.push(h.dir);
    const v: any[] = await h.tool.judgeCandidates(false, 5);
    expect(v[0].verdict).toBe('extended');
    expect(h.calls.length).toBe(0);
    const saved = JSON.parse(fs.readFileSync(path.join(h.dir, 'candidates.json'), 'utf-8'));
    expect(saved[0].status).toBe('watching');
    expect(Date.parse(saved[0].observe_until)).toBeGreaterThan(Date.now());
  });

  it('样本不足（< minSamples）→ 延期', async () => {
    const h = makeGate({ candidate: makeCand(), candRewards: { count: 2, avg: 0.0 } });
    dirs.push(h.dir);
    const v: any[] = await h.tool.judgeCandidates(false, 5);
    expect(v[0].verdict).toBe('extended');
    expect(h.calls.filter((c) => c.name !== 'genome_promote' && c.name !== 'genome_rollback').length).toBe(0);
  });

  it('显著恶化（drop>0.1）→ 回滚到上一版（候选仍为当前版本时）', async () => {
    const h = makeGate({
      candidate: makeCand(),
      candRewards: { count: 5, avg: -0.5 },
      baseRewards: { count: 5, avg: 0.0 },
    });
    dirs.push(h.dir);
    const v: any[] = await h.tool.judgeCandidates(true, 1);
    expect(v[0].verdict).toBe('rejected');
    const rb = h.calls.filter((c) => c.name === 'genome_rollback');
    expect(rb.length).toBe(1);
    expect(rb[0].args.to_section_version).toBe(16);
  });

  it('未显著恶化 → 转正（带 genome_version 绑定）', async () => {
    const h = makeGate({
      candidate: makeCand(),
      candRewards: { count: 5, avg: 0.05 },
      baseRewards: { count: 5, avg: 0.10 },
    });
    dirs.push(h.dir);
    const v: any[] = await h.tool.judgeCandidates(true, 1);
    expect(v[0].verdict).toBe('promoted');
    const pr = h.calls.filter((c) => c.name === 'genome_promote');
    expect(pr.length).toBe(1);
    expect(pr[0].args.genome_version).toBe('g30');
  });

  it('结构复核不通过 → 直接拒绝且不调 rollback', async () => {
    const bad = makeCand({ health_check: { passed: false, checked_at: new Date().toISOString(), issues: [{ code: 'empty_update', message: '空更新' }], size_delta: 0, substantive: false } });
    const h = makeGate({ candidate: bad });
    dirs.push(h.dir);
    const v: any[] = await h.tool.judgeCandidates(true, 1);
    expect(v[0].verdict).toBe('rejected');
    expect(h.calls.filter((c) => c.name === 'genome_rollback').length).toBe(0);
    expect(h.calls.filter((c) => c.name === 'genome_promote').length).toBe(0);
  });

  it('force=true 时零样本仍延期（不得凭零证据转正）', async () => {
    const h = makeGate({ candidate: makeCand(), candRewards: { count: 0, avg: 0 } });
    dirs.push(h.dir);
    const v: any[] = await h.tool.judgeCandidates(true, 1);
    expect(v[0].verdict).toBe('extended');
    expect(h.calls.filter((c) => c.name === 'genome_promote').length).toBe(0);
  });

  it('未到观察期且 force=false → watching（不做任何动作）', async () => {
    const future = new Date(Date.now() + 86400000).toISOString();
    const h = makeGate({ candidate: makeCand({ observe_until: future }) });
    dirs.push(h.dir);
    const v: any[] = await h.tool.judgeCandidates(false, 1);
    expect(v[0].verdict).toBe('watching');
    expect(h.calls.length).toBe(0);
  });
});
