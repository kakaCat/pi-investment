import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync, readdirSync, unlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import * as path from 'node:path';
import { ValidationGateTool } from '../src/tools/ValidationGateTool/ValidationGateTool';

/**
 * F1 状态一致性诊断腿单测（2026-09-06，w-a8a89c6a）。
 * 背景：进化状态存本地文件（candidates.json / genome.json），业务 DB 无表无错误通道——
 * 状态漂移/孤儿残留不产生任何 DB 错误，只能人工审计发现（2026-09-06 实证：8/25 孤儿
 * candidates.json 曾误导审计得出错误结论）。本次为 validation_gate 增加 runConsistencyCheck：
 *   C1 孤儿候选：watching 候选 genome_version ∉ genome history（promote/rollback 无依据）
 *   C2 未登记版本：history stage=candidate 条目无 candidates.json 对应（registerCandidate 断链，
 *      g16 principles v6 即 9/3 修复前历史 bug 的真实残留——观察版滞留从未被裁决）
 *   C3 原子写残留：genomeDir 下 *.tmp（tmp+rename 原子写中途崩溃痕迹）
 * healthy=false 不阻断裁决，但 summary 带警告，执行方按 SOP 落 decision_audit + 飞书。
 * 通过真实实例化 ValidationGateTool 直调 private runConsistencyCheck 验证。
 */
describe('validation_gate / 状态一致性诊断腿（F1）', () => {
  let genomeDir: string;
  let tool: ValidationGateTool;
  let osMemoryMock: { searchMemory: () => Promise<any> };

  const writeCandidates = (list: any[]) =>
    writeFileSync(path.join(genomeDir, 'candidates.json'), JSON.stringify(list, null, 2));

  const writeGenomeHistory = (history: any[]) =>
    writeFileSync(
      path.join(genomeDir, 'genome.json'),
      JSON.stringify({ genome_version: 'g20', updated_at: new Date().toISOString(), sections: {}, history }, null, 2)
    );

  const makeWatching = (overrides: Record<string, any> = {}) => ({
    id: 'cand_test_watch_1',
    section: 'rules',
    section_version: 8,
    genome_version: 'g19',
    baseline_version: 'g18',
    created_at: new Date(Date.now() - 10 * 86400000).toISOString(),
    observe_until: new Date(Date.now() + 5 * 86400000).toISOString(),
    status: 'watching' as const,
    mutation_type: 'prompt' as const,
    ...overrides,
  });

  beforeAll(() => {
    genomeDir = mkdtempSync(path.join(tmpdir(), 'f1-gate-consistency-'));
    mkdirSync(path.join(genomeDir, 'sections'), { recursive: true });
    osMemoryMock = { searchMemory: async () => ({ items: [] }) };
    const ctx = { genome: { genomeDir }, tools: { execute: async () => ({}) } } as any;
    tool = new ValidationGateTool(ctx, osMemoryMock as any, 5);
  });

  afterAll(() => {
    rmSync(genomeDir, { recursive: true, force: true });
  });

  afterEach(() => {
    // 清理用例间污染（C3 用例写入的 .tmp 残留会影响后续用例的一致性判定）
    for (const f of readdirSync(genomeDir)) {
      if (f.endsWith('.tmp')) unlinkSync(path.join(genomeDir, f));
    }
  });

  const runCheck = () => (tool as any).runConsistencyCheck();

  it('healthy：watching 候选与 history stage=candidate 一一对应、无 .tmp → healthy=true', () => {
    writeGenomeHistory([
      { version: 'g19', section: 'rules', section_version: 8, stage: 'candidate', ts: new Date().toISOString(), reason: 'R-011 观察' },
    ]);
    writeCandidates([makeWatching()]);

    const r = runCheck();
    expect(r.healthy).toBe(true);
    expect(r.orphan_candidates).toEqual([]);
    expect(r.unregistered_versions).toEqual([]);
    expect(r.atomic_leftovers).toEqual([]);
    expect(r.issues).toEqual([]);
  });

  it('C1：watching 候选 genome_version 不在 genome history → 孤儿候选报出', () => {
    writeGenomeHistory([
      { version: 'g20', section: 'rules', section_version: 9, ts: new Date().toISOString(), reason: '直写 active' },
    ]);
    writeCandidates([makeWatching({ id: 'cand_orphan_1', genome_version: 'g99' })]);

    const r = runCheck();
    expect(r.healthy).toBe(false);
    expect(r.orphan_candidates).toHaveLength(1);
    expect(r.orphan_candidates[0]).toMatchObject({ id: 'cand_orphan_1', genome_version: 'g99' });
    expect(r.issues.some(i => i.includes('孤儿候选'))).toBe(true);
  });

  it('C2：history stage=candidate 无 candidates.json 对应 → 未登记版本报出（g16 型残留）', () => {
    writeGenomeHistory([
      { version: 'g16', section: 'principles', section_version: 6, stage: 'candidate', ts: '2026-08-28T02:59:58.000Z', reason: '某修补' },
      { version: 'g19', section: 'rules', section_version: 8, stage: 'candidate', ts: '2026-09-05T02:02:35.000Z', reason: 'R-011 观察' },
    ]);
    // candidates.json 只有 g19 登记，缺 g16
    writeCandidates([makeWatching()]);

    const r = runCheck();
    expect(r.healthy).toBe(false);
    expect(r.unregistered_versions).toHaveLength(1);
    expect(r.unregistered_versions[0]).toMatchObject({ section: 'principles', genome_version: 'g16' });
    expect(r.issues.some(i => i.includes('未登记候选版本 g16'))).toBe(true);
  });

  it('C3：genomeDir 存在 *.tmp → 原子写残留报出', () => {
    writeGenomeHistory([
      { version: 'g19', section: 'rules', section_version: 8, stage: 'candidate', ts: new Date().toISOString() },
    ]);
    writeCandidates([makeWatching()]);
    writeFileSync(path.join(genomeDir, 'candidates.json.tmp'), '{"broken":');

    const r = runCheck();
    expect(r.healthy).toBe(false);
    expect(r.atomic_leftovers).toContain('candidates.json.tmp');
  });

  it('execute 结果携带 consistency 字段且 healthy 时 summary 无警告', async () => {
    writeGenomeHistory([
      { version: 'g19', section: 'rules', section_version: 8, stage: 'candidate', ts: new Date().toISOString() },
    ]);
    // 观察期未满 → force=false 走 watching 分支（零记忆样本不触发回测/转正）
    writeCandidates([makeWatching({ observe_until: new Date(Date.now() + 5 * 86400000).toISOString() })]);

    const res = await (tool as any).execute({}, {});
    expect(res.consistency).toBeDefined();
    expect(res.consistency.healthy).toBe(true);
    expect(res.summary).not.toContain('一致性');
    expect(res.verdicts[0].verdict).toBe('watching');
  });

  it('execute：C2 异常时 summary 带一致性警告', async () => {
    writeGenomeHistory([
      { version: 'g16', section: 'principles', section_version: 6, stage: 'candidate', ts: '2026-08-28T02:59:58.000Z' },
      { version: 'g19', section: 'rules', section_version: 8, stage: 'candidate', ts: new Date().toISOString() },
    ]);
    writeCandidates([makeWatching()]);

    const res = await (tool as any).execute({}, {});
    expect(res.consistency.healthy).toBe(false);
    expect(res.summary).toContain('一致性');
  });
});
