import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GitRepo } from '../src/git.js';
import { StateStore } from '../src/state.js';
import { onBoot } from '../src/boot-hook.js';

/**
 * boot 接线红测试：构造期调用 onBoot 的语义 = 修复滞留态 + 写机器审计（JSONL）+
 * 幂等 + 修复异常不得阻断 boot（fail-safe 由调用方 try/catch 保证，此处验核心路径）。
 */
describe('onBoot 接线语义', () => {
  let dir: string;
  let repo: GitRepo;
  let state: StateStore;
  let stateDir: string;
  let auditPath: string;
  const now = Date.UTC(2026, 8, 10, 12, 0, 0);

  const readAudit = (): Record<string, unknown>[] =>
    existsSync(auditPath)
      ? readFileSync(auditPath, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
      : [];

  const baseDeps = () => ({
    repo,
    state,
    readLockTs: () => {
      try { return Number(readFileSync(join(stateDir, 'restarting.lock'), 'utf8')); } catch { return null; }
    },
    releaseLock: () => state.releaseLock(),
    resolveBase: () => (repo.branchExists('main') ? 'main' : repo.branchExists('master') ? 'master' : null),
    now,
    auditPath,
  });

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'lifecycle-boothook-'));
    const git = (g: string[]) => execFileSync('git', g, { cwd: dir, encoding: 'utf8' }).trim();
    git(['init', '-b', 'main']);
    git(['config', 'user.email', 'test@test.com']);
    git(['config', 'user.name', 'test']);
    writeFileSync(join(dir, '.gitignore'), 'state/\n');
    mkdirSync(join(dir, 'agent-dh'));
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v1');
    git(['add', '-A']);
    git(['commit', '-m', 'init']);
    repo = new GitRepo(dir, () => new Date(now));
    stateDir = join(dir, 'state');
    state = new StateStore(stateDir);
    state.writeLastKnownGood(repo.head());
    auditPath = join(stateDir, 'boot-recovery-audit.jsonl');
  });

  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it('stranded（agent-self+无记录）→ 修复回 main + 审计落盘 + 二次 boot 幂等', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2-wip');
    repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: stranded');
    expect(repo.currentBranch()).toMatch(/^agent-self\//);

    const r1 = onBoot(baseDeps() as any);
    expect(r1.actions).toContainEqual(expect.objectContaining({ kind: 'checkoutBase', to: 'main' }));
    expect(repo.currentBranch()).toBe('main');
    const audit1 = readAudit();
    expect(audit1.length).toBe(1);
    expect(audit1[0]).toMatchObject({ actions: r1.actions, issues: [] });

    const r2 = onBoot(baseDeps() as any); // 二次 boot：无动作、无新审计（幂等）
    expect(r2.actions).toEqual([]);
    expect(readAudit().length).toBe(1);
    expect(repo.currentBranch()).toBe('main');
  });

  it('陈旧锁 + main → 释放锁并审计；新鲜锁不动', () => {
    writeFileSync(join(stateDir, 'restarting.lock'), String(now - 16 * 60 * 1000));
    const r1 = onBoot(baseDeps() as any);
    expect(r1.actions).toContainEqual({ kind: 'releaseStaleLock' });
    expect(existsSync(join(stateDir, 'restarting.lock'))).toBe(false);
    expect(readAudit().length).toBe(1);

    writeFileSync(join(stateDir, 'restarting.lock'), String(now - 1000)); // 新鲜锁
    const r2 = onBoot(baseDeps() as any);
    expect(r2.actions).toEqual([]);
    expect(existsSync(join(stateDir, 'restarting.lock'))).toBe(true); // 不动
  });

  it('正常续跑态 → 零动作零审计（不打扰）', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2-wip');
    const w = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: continue')!.branch;
    state.writePending({
      reason: 'r', resume_task: 'continue previous task', checkpoint_branch: w, base_branch: 'main',
      last_known_good: repo.head(), attempt: 1, ts: new Date(now).toISOString(),
    });
    const r = onBoot(baseDeps() as any);
    expect(r.actions).toEqual([]);
    expect(r.issues).toEqual([]);
    expect(existsSync(auditPath)).toBe(false);
    expect(repo.currentBranch()).toBe(w); // 不动，setupResume 接管
  });
});
