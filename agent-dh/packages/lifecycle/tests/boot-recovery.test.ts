import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GitRepo } from '../src/git.js';
import { StateStore } from '../src/state.js';
import { planBootRecovery, runBootRecovery, type BootRecoveryDeps } from '../src/boot-recovery.js';

/** boot 修复器不变量测试（I1-I5）：真实 git + StateStore + 磁盘 restarting.lock */
describe('boot-recovery', () => {
  let dir: string;
  let repo: GitRepo;
  let state: StateStore;
  let stateDir: string;
  const now = Date.UTC(2026, 8, 10, 12, 0, 0);

  const lockPath = () => join(stateDir, 'restarting.lock');
  const writeLock = (ts: number) => writeFileSync(lockPath(), String(ts));
  const readLockTs = () => {
    try { return Number(readFileSync(lockPath(), 'utf8')); } catch { return null; }
  };

  const deps = (over: Partial<BootRecoveryDeps> = {}): BootRecoveryDeps => ({
    repo,
    state,
    readLockTs,
    releaseLock: () => state.releaseLock(),
    now,
    resolveBase: () => (repo.branchExists('main') ? 'main' : repo.branchExists('master') ? 'master' : null),
    ...over,
  });

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'lifecycle-boot-'));
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
  });

  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  const makeStrandedWip = (): string => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2-wip');
    const w = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: stranded')!.branch;
    expect(repo.currentBranch()).toBe(w);
    return w;
  };

  it('I1 陈旧锁（>15min）→ 移除', () => {
    writeLock(now - 16 * 60 * 1000);
    const r = planBootRecovery(deps());
    expect(r.actions.map((a) => a.kind)).toContain('releaseStaleLock');
    runBootRecovery(deps());
    expect(existsSync(lockPath())).toBe(false);
    expect(planBootRecovery(deps()).actions).toEqual([]); // 幂等：修复后无动作
  });

  it('I2 新鲜锁 → 不动', () => {
    writeLock(now - 1000);
    const r = planBootRecovery(deps());
    expect(r.actions).toEqual([]);
    expect(existsSync(lockPath())).toBe(true);
  });

  it('I3 stranded（agent-self + 无 pending）→ checkout 回 main，分支与内容保留', () => {
    const w = makeStrandedWip();
    const r = runBootRecovery(deps());
    expect(r.actions).toContainEqual({ kind: 'checkoutBase', from: w, to: 'main' });
    expect(repo.currentBranch()).toBe('main');
    expect(repo.branchExists(w)).toBe(true); // 分支不删
    expect(execFileSync('git', ['show', `${w}:agent-dh/a.txt`], { cwd: dir, encoding: 'utf8' })).toBe('v2-wip');
    expect(planBootRecovery(deps()).actions).toEqual([]); // 幂等
  });

  it('I3 正常续跑态（agent-self + pending 匹配）→ 不动', () => {
    const w = makeStrandedWip();
    state.writePending({
      reason: 'r', resume_task: 'continue previous task', checkpoint_branch: w, base_branch: 'main',
      last_known_good: repo.head(), attempt: 1, ts: new Date(now).toISOString(),
    });
    const r = planBootRecovery(deps());
    expect(r.actions).toEqual([]);
    expect(r.issues).toEqual([]);
  });

  it('I4 pending 与 HEAD 不匹配（不同 wip）→ 只报 issue 不动', () => {
    const a = makeStrandedWip();
    state.writePending({
      reason: 'r', resume_task: 'continue previous task', checkpoint_branch: a, base_branch: 'main',
      last_known_good: repo.head(), attempt: 1, ts: new Date(now).toISOString(),
    });
    repo.checkout('main');
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v3-wip');
    const b = 'agent-self/20260910-second';
    execFileSync('git', ['checkout', '-b', b], { cwd: dir }); // 新 wip，与 pending.checkpoint_branch=a 不一致
    expect(b).not.toBe(a);
    const r = planBootRecovery(deps());
    expect(r.actions).toEqual([]); // 不擅动（setupResume/人工裁决）
    expect(r.issues.length).toBe(1);
  });
});
