import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GitRepo } from '../src/git.js';
import { StateStore } from '../src/state.js';
import { runRestarter, type RestarterArgs, type RestarterEnv } from '../src/restarter/restarter.js';

/**
 * restarter 故障注入测试（真实 git 仓库 + 假 start.sh + 死 pid）：
 * 不依赖真实进程/端口，全部路径确定性可复现。
 * 守护的不变量：结果文件必写、restarting.lock 必释放、wip 分支内容只增不减、
 * 失败路径必回基线分支、pending 缺失/checkout 失败有明确 dead 语义。
 */
describe('runRestarter 故障注入', () => {
  let dir: string;
  let repo: GitRepo;
  let state: StateStore;
  let stateDir: string;
  let startScript: string;
  let wipBranch: string;
  const deadPid = 999_999; // 不存在 → killOld 无操作
  const deadPort = 36_000 + Math.floor(Math.random() * 1000); // 无监听 → 健康检查必失败

  const readResult = () =>
    JSON.parse(readFileSync(join(stateDir, 'restart-result.json'), 'utf8')) as Record<string, unknown>;

  const env = (over: Partial<RestarterEnv> = {}): RestarterEnv => ({
    dryRun: false,
    preKillDelayMs: 0,
    healthTimeoutMs: 600,
    ...over,
  });

  const args = (over: Partial<RestarterArgs> = {}): RestarterArgs => ({
    pid: deadPid,
    port: deadPort,
    repoRoot: dir,
    stateDir,
    startScript,
    logPath: join(stateDir, 'restart-test.log'),
    ...over,
  });

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'lifecycle-restarter-'));
    const git = (g: string[]) => execFileSync('git', g, { cwd: dir, encoding: 'utf8' }).trim();
    git(['init', '-b', 'main']);
    git(['config', 'user.email', 'test@test.com']);
    git(['config', 'user.name', 'test']);
    writeFileSync(join(dir, '.gitignore'), 'state/\n');
    mkdirSync(join(dir, 'agent-dh'));
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v1');
    git(['add', '-A']);
    git(['commit', '-m', 'init']);
    repo = new GitRepo(dir, () => new Date(Date.UTC(2026, 8, 10, 12, 0, 0)));
    stateDir = join(dir, 'state');
    state = new StateStore(stateDir);
    state.writeLastKnownGood(repo.head());
    startScript = join(dir, 'start.sh');
    writeFileSync(startScript, '#!/bin/bash\nexit 0\n', { mode: 0o755 }); // 永不启动服务 → 健康检查必失败
    // 建 wip 检查点（模拟 scheduleRestart 已 spawn 前的状态：HEAD 在 agent-self 上）
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2-wip');
    wipBranch = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: fault test')!.branch;
  });

  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it('启动失败→回滚基线也失败→dead：结果已写、锁已释放、HEAD 回基线、wip 内容保留', async () => {
    state.writePending({
      reason: 'fault', resume_task: 't', checkpoint_branch: wipBranch, base_branch: 'main',
      last_known_good: repo.head(), attempt: 1, ts: new Date().toISOString(),
    });
    await runRestarter(args(), env());
    const r = readResult();
    expect(r.status).toBe('dead');
    expect(r.failed_branch).toBe(wipBranch);
    expect(existsSync(join(stateDir, 'restarting.lock'))).toBe(false);
    // 回滚成功前停在 wip；最终在 main（基线）
    expect(repo.currentBranch()).toBe('main');
    // wip 内容只增不减（快照仍在，等 finalize/人工）
    const wipContent = execFileSync('git', ['show', `${wipBranch}:agent-dh/a.txt`], { cwd: dir, encoding: 'utf8' });
    expect(wipContent).toBe('v2-wip');
  });

  it('回滚时基线分支不存在→dead（rollback checkout failed），锁释放、wip 保留', async () => {
    state.writePending({
      reason: 'fault', resume_task: 't', checkpoint_branch: wipBranch, base_branch: 'no-such-base',
      last_known_good: repo.head(), attempt: 1, ts: new Date().toISOString(),
    });
    await runRestarter(args(), env());
    const r = readResult();
    expect(r.status).toBe('dead');
    expect(String(r.error)).toContain('rollback checkout failed');
    expect(existsSync(join(stateDir, 'restarting.lock'))).toBe(false);
    expect(repo.currentBranch()).toBe(wipBranch); // checkout 失败，仍停在原处不破坏
  });

  it('pending 缺失→dead（无法回滚），结果已写、锁已释放', async () => {
    await runRestarter(args(), env());
    const r = readResult();
    expect(r.status).toBe('dead');
    expect(String(r.error)).toContain('pending-resume.json 不存在');
    expect(existsSync(join(stateDir, 'restarting.lock'))).toBe(false);
  });

  it('dry-run：无任何 git 副作用，结果 ok + dry_run=true', async () => {
    state.writePending({
      reason: 'fault', resume_task: 't', checkpoint_branch: wipBranch, base_branch: 'main',
      last_known_good: repo.head(), attempt: 1, ts: new Date().toISOString(),
    });
    await runRestarter(args(), env({ dryRun: true }));
    const r = readResult();
    expect(r).toMatchObject({ status: 'ok', dry_run: true });
    expect(repo.currentBranch()).toBe(wipBranch); // 未动 git
    expect(existsSync(join(stateDir, 'restarting.lock'))).toBe(false);
  });
});
