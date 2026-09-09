import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GitRepo } from '../src/git.js';
import { StateStore } from '../src/state.js';
import { planAndScheduleRestart, type RestartPlannerDeps, type RestartRequest } from '../src/restart-planner.js';

/**
 * restart-planner 重构等价测试：把 scheduleRestart 抽成纯模块后，用真实临时 git +
 * StateStore + 注入 spawn 验证原语义逐条不漂移。
 * 覆盖：限流、互斥锁、wip 检查点、wip-on-wip 续提交、pending 落盘、spawn、spawn 失败放锁。
 */
describe('planAndScheduleRestart', () => {
  let dir: string;
  let repo: GitRepo;
  let state: StateStore;
  const git = (args: string[]) => execFileSync('git', args, { cwd: dir, encoding: 'utf8' }).trim();
  const spawnCalls: Array<{ cmd: string; args: string[]; opts: object }> = [];
  let deps: RestartPlannerDeps;

  beforeEach(() => {
    spawnCalls.length = 0;
    dir = mkdtempSync(join(tmpdir(), 'lifecycle-planner-'));
    git(['init', '-b', 'main']);
    git(['config', 'user.email', 'test@test.com']);
    git(['config', 'user.name', 'test']);
    writeFileSync(join(dir, '.gitignore'), 'state/\n');
    mkdirSync(join(dir, 'agent-dh'));
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v1');
    git(['add', '-A']);
    git(['commit', '-m', 'init']);
    repo = new GitRepo(dir, () => new Date(Date.UTC(2026, 8, 10, 12, 0, 0)));
    state = new StateStore(join(dir, 'state'));
    state.writeLastKnownGood(repo.head());
    deps = {
      repo,
      state,
      resolveBase: () => 'main',
      resolveRestarterPath: () => '/fake/restarter.mjs',
      profileDir: dir,
      agentDhRoot: dir,
      repoRoot: dir,
      port: 12345,
      processPid: 4321,
      captureLastUserMessage: () => null,
      spawnRestarter: (cmd, args, opts) => spawnCalls.push({ cmd, args, opts }),
    };
  });

  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  const req = (over: Partial<RestartRequest> = {}): RestartRequest => ({
    reason: 'test restart',
    preserveContext: true,
    maxRestartsPerHour: 10,
    now: Date.UTC(2026, 8, 10, 12, 0, 0),
    ...over,
  });

  it('有改动：建 agent-self wip、写 pending、spawn 重启器、锁交给重启器', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    const plan = planAndScheduleRestart(deps, req());
    const branch = repo.currentBranch();
    expect(branch).toMatch(/^agent-self\/\d{8}-\d{6}$/);
    expect(plan.checkpointBranch).toBe(branch);
    expect(plan.baseBranch).toBe('main');
    const pending = state.readPending()!;
    expect(pending.checkpoint_branch).toBe(branch);
    expect(pending.base_branch).toBe('main');
    expect(pending.attempt).toBe(1);
    expect(pending.resume_task).toBe('continue previous task');
    expect(spawnCalls).toHaveLength(1);
    expect(spawnCalls[0].args[0]).toBe('/fake/restarter.mjs');
    expect(spawnCalls[0].args[1]).toBe('4321');
    expect(spawnCalls[0].args[2]).toBe('12345');
    expect(spawnCalls[0].args[4]).toBe(join(dir, 'state'));
    expect(spawnCalls[0].opts).toMatchObject({ detached: true, stdio: 'ignore', cwd: dir });
    expect(existsSync(join(dir, 'state', 'restarting.lock'))).toBe(true);
  });

  it('无改动：checkpoint=null 但仍写 pending 并 spawn', () => {
    const plan = planAndScheduleRestart(deps, req());
    expect(plan.checkpointBranch).toBeNull();
    expect(state.readPending()!.checkpoint_branch).toBeNull();
    expect(state.readPending()!.base_branch).toBe('main');
    expect(spawnCalls).toHaveLength(1);
  });

  it('wip-on-wip：续提交同一 agent-self 分支，不另起新链，base 溯源到 main', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    const first = planAndScheduleRestart(deps, req());
    const branch = first.checkpointBranch!;
    state.releaseLock(); // 模拟重启器 finish() 已释放锁；pending 保留（未 finalize 前 wip-on-wip 场景）
    const headBefore = repo.head();
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v3');
    const second = planAndScheduleRestart(deps, req());
    expect(second.checkpointBranch).toBe(branch);
    expect(second.baseBranch).toBe('main');
    expect(repo.currentBranch()).toBe(branch);
    expect(repo.head()).not.toBe(headBefore); // 续提交生效
    expect(git(['branch', '--list', 'agent-self/*']).split('\n').filter(Boolean)).toHaveLength(1);
    expect(state.readPending()!.attempt).toBe(2);
  });

  it('限流拒绝：不拿锁、不 spawn', () => {
    state.writeNamed('restart-counter.json', { window_start: Date.UTC(2026, 8, 10, 11, 59, 0), count: 10 });
    expect(() => planAndScheduleRestart(deps, req({ maxRestartsPerHour: 10 }))).toThrow(/达到上限/);
    expect(spawnCalls).toHaveLength(0);
    expect(state.acquireLock()).toBe(true); // 没有遗留锁
    state.releaseLock();
  });

  it('已有锁（新鲜）：拒绝重入且锁保持不动', () => {
    writeFileSync(join(dir, 'state', 'restarting.lock'), String(Date.now()));
    expect(() => planAndScheduleRestart(deps, req())).toThrow(/拒绝重入/);
    expect(spawnCalls).toHaveLength(0);
    expect(existsSync(join(dir, 'state', 'restarting.lock'))).toBe(true);
  });

  it('spawn 失败：释放锁并原样抛出', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    deps.spawnRestarter = () => { throw new Error('spawn boom'); };
    expect(() => planAndScheduleRestart(deps, req())).toThrow('spawn boom');
    expect(existsSync(join(dir, 'state', 'restarting.lock'))).toBe(false);
    expect(state.readPending()).not.toBeNull(); // 与现语义一致：pending 保留待修复器处理
  });
});
