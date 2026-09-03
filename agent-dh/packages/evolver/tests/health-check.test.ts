import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import * as path from 'node:path';
import { execSync } from 'node:child_process';
import {
  runHealthCheck,
  getSectionBaseline,
  getSectionContentAtGenome,
  attachHealthCheck,
  registerCandidate,
  readCandidates,
} from '../src/candidates';

/**
 * L4-B（2026-09-03，w-8366e526）：candidate 健康检查（静态腿）单测。
 * 背景：g1→g18 审计发现 38% 版本是验收/测试噪声（R-005→R-010 只增不验），
 * genome_update 写入时 guard 拦结构非法；health_check 在登记期复核留痕 +
 * 捕获空更新噪声 + 采集 diff 画像。测试分两层：
 *   1) 纯函数 runHealthCheck —— 无 IO，直接断言各检查项
 *   2) git 集成 —— 临时 git 仓库模拟 genome 历史，验证基线/登记快照取数与不漂移
 */

describe('candidates/runHealthCheck 纯函数', () => {
  it('实质变更 + 规则新增：passed=true，diff 画像正确', () => {
    const cand = [
      '# R-011 测试',
      '正文内容',
      '## R-001 旧规则保留',
    ].join('\n');
    const base = [
      '# R-001 旧规则保留',
      '正文内容（旧）',
    ].join('\n');
    const hc = runHealthCheck({ section: 'rules', candidateContent: cand, baselineContent: base });

    expect(hc.passed).toBe(true);
    expect(hc.substantive).toBe(true);
    expect(hc.issues).toEqual([]);
    expect(hc.size_delta).toBe(cand.length - base.length);
    expect(hc.rule_changes?.added).toContain('R-011');
    expect(hc.rule_changes?.removed).toEqual([]);
  });

  it('未知花括号变量 → braces 问题，passed=false', () => {
    const hc = runHealthCheck({
      section: 'lessons',
      candidateContent: '规则 {{unknown_var}} 引用',
      baselineContent: '规则 旧引用',
    });
    expect(hc.passed).toBe(false);
    expect(hc.issues.map(i => i.code)).toContain('braces');
    expect(hc.issues.find(i => i.code === 'braces')?.message).toContain('{{unknown_var}}');
  });

  it('已知变量 {{genome_version}} 不触发 braces', () => {
    const hc = runHealthCheck({
      section: 'lessons',
      candidateContent: '当前基因组版本 {{genome_version}} 新内容',
      baselineContent: '旧内容',
    });
    expect(hc.issues.map(i => i.code)).not.toContain('braces');
  });

  it('内容超 8000 字符 → size 问题', () => {
    const hc = runHealthCheck({
      section: 'lessons',
      candidateContent: 'x'.repeat(8001),
      baselineContent: 'y'.repeat(100),
    });
    expect(hc.passed).toBe(false);
    expect(hc.issues.map(i => i.code)).toContain('size');
  });

  it('rules 段重复标题定义 → dup_rule_id', () => {
    const cand = [
      '## R-007 回撤熔断',
      '## R-007 回撤熔断（重复）',
      '正文',
    ].join('\n');
    const hc = runHealthCheck({ section: 'rules', candidateContent: cand, baselineContent: '旧' });
    expect(hc.issues.map(i => i.code)).toContain('dup_rule_id');
  });

  it('空更新（与基线去空白相同）→ empty_update，passed=false', () => {
    const content = '## R-001 规则\n\n正文内容  多空格';
    const baseline = '## R-001 规则\n正文内容多空格';  // 去空白后相同
    const hc = runHealthCheck({ section: 'rules', candidateContent: content, baselineContent: baseline });
    expect(hc.substantive).toBe(false);
    expect(hc.passed).toBe(false);
    expect(hc.issues.map(i => i.code)).toContain('empty_update');
  });

  it('无基线（首次/历史缺失）→ 不判空更新，substantive 视有无内容', () => {
    const hc = runHealthCheck({
      section: 'principles',
      candidateContent: '核心原则一',
      baselineContent: null,
    });
    expect(hc.substantive).toBe(true);
    expect(hc.issues.map(i => i.code)).not.toContain('empty_update');
    expect(hc.passed).toBe(true);
    expect(hc.note).toContain('基线不可得');
  });
});

describe('candidates/git 集成（临时 genome 仓库）', () => {
  let genomeDir: string;

  const git = (args: string, opts?: { dir?: string }) =>
    execSync(`git ${args}`, {
      cwd: opts?.dir ?? genomeDir,
      encoding: 'utf-8',
    });

  /** 提交当前 sections/{name}.md，返回 commit hash，并把 history 条目写进 genome.json */
  const commitSection = (section: string, version: string, sectionVersion: number, content: string) => {
    writeFileSync(path.join(genomeDir, 'sections', `${section}.md`), content);
    git(`add -A`);
    git(`-c user.name=test -c user.email=test@t commit -m "v${version} ${section}"`);
    const hash = git(`rev-parse HEAD`).trim();

    const gp = path.join(genomeDir, 'genome.json');
    const data = existsSync(gp) ? JSON.parse(readFileSync(gp, 'utf-8')) : { history: [] };
    data.history.push({
      version,
      section,
      section_version: sectionVersion,
      parent: version === 'g1' ? null : `g${sectionVersion - 1}`,
      reason: `test commit ${version}`,
      ts: new Date().toISOString(),
      git_commit: hash,
      author: 'unit-test',
      type: 'update',
      force: false,
    });
    writeFileSync(gp, JSON.stringify(data, null, 2));
    git(`add -A`);
    git(`-c user.name=test -c user.email=test@t commit -m "meta v${version}" --allow-empty`);
    return hash;
  };

  beforeAll(() => {
    genomeDir = mkdtempSync(path.join(tmpdir(), 'l4b-genome-'));
    mkdirSync(path.join(genomeDir, 'sections'), { recursive: true });
    git(`init`);
    // v1: R-001 旧规则
    commitSection('rules', 'g1', 1, '## R-001 旧规则\n旧正文\n');
  });

  afterAll(() => {
    rmSync(genomeDir, { recursive: true, force: true });
  });

  it('getSectionBaseline 按 history 的 git_commit 取指定 section_version 内容', () => {
    // v2: R-001 微调 + 新增 R-002
    const v2 = '## R-001 旧规则微调\n## R-002 新规则\n正文2\n';
    commitSection('rules', 'g2', 2, v2);
    // v3: 覆盖当前文件（模拟后续版本）
    commitSection('rules', 'g3', 3, '## R-003 最新\n当前文件内容\n');

    const baseline2 = getSectionBaseline(genomeDir, 'rules', 2);
    expect(baseline2).toBe(v2);  // 取 v2 快照而非当前文件

    const baseline1 = getSectionBaseline(genomeDir, 'rules', 1);
    expect(baseline1).toContain('R-001 旧规则');
  });

  it('getSectionContentAtGenome 取登记时 genome 版本快照，事后不漂移', () => {
    const v4 = '## R-004 快照校验规则\n快照正文\n';
    commitSection('rules', 'g4', 4, v4);

    const snap = getSectionContentAtGenome(genomeDir, 'rules', 'g4');
    expect(snap).toBe(v4);

    // 覆盖当前文件后，快照仍返回 g4 内容
    writeFileSync(path.join(genomeDir, 'sections', 'rules.md'), '## R-099 覆盖\n');
    expect(getSectionContentAtGenome(genomeDir, 'rules', 'g4')).toBe(v4);
  });

  it('attachHealthCheck 基于登记快照做空更新判定（复核不因当前文件漂移）', () => {
    // 登记一个 section_version=4（g4）的候选，candidate 内容即当前文件（g4 刚提交）
    // 若当前文件 = g4 快照 → attach 计算 candidate=当前文件快照 g4、基线=section_version 3
    const rec = registerCandidate({
      genomeDir,
      section: 'rules',
      sectionVersion: 4,
      genomeVersion: 'g4',
      baselineVersion: 'g3',
      mutationType: 'prompt',
    });
    const stored = readCandidates(genomeDir).find(r => r.id === rec.id);
    expect(stored?.health_check).toBeDefined();
    expect(stored?.health_check?.passed).toBe(true);
    expect(stored?.health_check?.rule_changes).toBeDefined();
    // g4 vs g3：g3=R-003，g4=R-004 → added 含 R-004
    expect(stored?.health_check?.rule_changes?.added).toContain('R-004');
  });

  it('registerCandidate 对空更新登记同样留痕（health_check 捕获 empty_update）', () => {
    // g5：内容与 g4 去空白相同（模拟蒸馏无实质产出但版本推进）→ 空更新候选
    const dup = '## R-004 快照校验规则\n快照正文\n';
    commitSection('rules', 'g5', 5, dup);
    const rec = registerCandidate({
      genomeDir,
      section: 'rules',
      sectionVersion: 5,
      genomeVersion: 'g5',
      baselineVersion: 'g4',
      mutationType: 'prompt',
    });
    const stored = readCandidates(genomeDir).find(r => r.id === rec.id);
    expect(stored?.health_check?.passed).toBe(false);
    expect(stored?.health_check?.substantive).toBe(false);
    expect(stored?.health_check?.issues.map(i => i.code)).toContain('empty_update');
  });

  it('版本号越界/无 history 条目 → 基线为 null（不 throw）', () => {
    expect(getSectionBaseline(genomeDir, 'rules', 0)).toBeNull();
    expect(getSectionBaseline(genomeDir, 'rules', 999)).toBeNull();
    expect(getSectionContentAtGenome(genomeDir, 'rules', 'g999')).toBeNull();
  });
});
