import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { registerCandidate, readCandidates, writeCandidates, candidatesFilePath, CandidateRecord } from '../src/candidates';

/**
 * RFC 008 候选登记闭环测试（Fix① 回归，2026-09-03）
 *
 * 断裂根因：BaseTool 重构后 PromptEvolverTool 只调 genome_update(stage='candidate')
 * 写 genome.json history，从不写 candidates.json → ValidationGateTool 永远无案可裁。
 *
 * 本测试用临时 genomeDir 验证：registerCandidate 写入的记录能被
 * ValidationGateTool 同款读取逻辑（filter status==='watching'）找到。
 */
describe('evolver/candidates 登记闭环（Fix①）', () => {
  let genomeDir: string;

  beforeEach(() => {
    genomeDir = fs.mkdtempSync(path.join(os.tmpdir(), 'genome-cand-'));
  });

  afterEach(() => {
    fs.rmSync(genomeDir, { recursive: true, force: true });
  });

  it('registerCandidate 写入 watching 记录，能被 gate 读取侧发现', () => {
    const rec = registerCandidate({
      genomeDir,
      section: 'rules',
      sectionVersion: 12,
      genomeVersion: 'g23',
      baselineVersion: 'g22',
      observeDays: 5,
      mutationType: 'prompt',
    });

    // 1. 文件真实存在且 JSON 可解析
    expect(fs.existsSync(candidatesFilePath(genomeDir))).toBe(true);
    const all = readCandidates(genomeDir);
    expect(all.length).toBe(1);

    // 2. 字段契约与 ValidationGateTool 读取侧一致
    expect(rec.id).toMatch(/^cand_\d+_/);           // id 带时间戳+随机后缀防并发撞车
    expect(rec.section).toBe('rules');
    expect(rec.section_version).toBe(12);
    expect(rec.genome_version).toBe('g23');
    expect(rec.baseline_version).toBe('g22');
    expect(rec.status).toBe('watching');
    expect(rec.mutation_type).toBe('prompt');
    expect(rec.observe_until).toBeTruthy();

    // 3. 观察期 ≈ 5 天后（±1s 容差）
    const diffMs = Date.parse(rec.observe_until) - Date.parse(rec.created_at);
    expect(diffMs).toBeGreaterThanOrEqual(5 * 86400000 - 1000);
    expect(diffMs).toBeLessThanOrEqual(5 * 86400000 + 1000);

    // 4. ValidationGateTool.judgeCandidates 的过滤前提：status='watching' 能命中
    const watching = all.filter(x => x.status === 'watching');
    expect(watching.length).toBe(1);
    expect(watching[0].id).toBe(rec.id);
  });

  it('并发多次登记（3 路模拟）id 不冲突', () => {
    const recs = Array.from({ length: 3 }, () =>
      registerCandidate({
        genomeDir,
        section: 'rules',
        sectionVersion: 12,
        genomeVersion: 'g23',
        baselineVersion: 'g22',
        observeDays: 5,
      })
    );
    const ids = new Set(recs.map(r => r.id));
    expect(ids.size).toBe(3);
    expect(readCandidates(genomeDir).length).toBe(3);
  });

  it('writeCandidates 原子写（tmp+rename），可整体替换', () => {
    const rec1 = registerCandidate({ genomeDir, section: 'rules', sectionVersion: 1, genomeVersion: 'g1', baselineVersion: 'g0' });
    const list = readCandidates(genomeDir);
    list[0].status = 'promoted';
    list[0].note = '裁决通过转正';
    writeCandidates(genomeDir, list);
    const after = readCandidates(genomeDir);
    expect(after.length).toBe(1);
    expect(after[0].status).toBe('promoted');
    expect(after[0].note).toContain('转正');
    expect(rec1.status).toBe('watching');  // 原对象不受影响（读写按值）
  });

  it('空 genomeDir 读返回 []（不存在文件不抛错）', () => {
    const empty = path.join(genomeDir, 'nested-nonexist');
    expect(readCandidates(empty)).toEqual([]);
  });
});
