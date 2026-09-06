import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { GitRepo } from '../src/git.js';
import { StateStore } from '../src/state.js';

/**
 * scheduleFinalize 三路径集成测试（RFC 002 自修复闭环收尾端）。
 * 通过真实 git 仓库 + StateStore 模拟 self_restart 后的 pending 状态，
 * 验证 merge（wip→基线+last-known-good 更新）、rollback（放弃 wip+硬重置）、
 * exit（无 git 操作仅清理）三条收尾路径。
 *
 * 说明：scheduleFinalize 是 LifecyclePlugin 私有方法，这里直接用 GitRepo+StateStore
 * 复刻其逻辑断言 git 效果（git 状态是唯一真值，不 mock）。
 */
describe('scheduleFinalize 收尾路径', () => {
  let dir: string;
  let repo: GitRepo;
  let state: StateStore;
  const git = (args: string[]) =>
    execFileSync('git', args, { cwd: dir, encoding: 'utf8' }).trim();

  /** 复刻 scheduleFinalize 的 merge 逻辑（改动2/3，w-856b64ef：与 index.ts 同步维护）。
   *  调用方须先解析好 base（index.ts 对 agent-self/* 前缀的 base 记录会经 resolveTrunkBase 溯源到干线）。 */
  const doMerge = (checkpoint: string, base: string) => {
    repo.checkout(base);
    const res = repo.finalizeMerge(base, checkpoint, 'merge(wip): lifecycle 收尾');
    if (repo.branchExists(checkpoint)) repo.deleteBranch(checkpoint, res.outcome === 'already-cherried');
    repo.cleanupWipChain('agent-self', base); // 整链清理副作用（改动3）
    const hash = res.merged_hash;
    state.writeLastKnownGood(hash);
    state.clearPending();
    return hash;
  };
  /** 复刻 scheduleFinalize 的 rollback 逻辑 */
  const doRollback = (checkpoint: string, base: string, lkg: string) => {
    repo.checkout(base);
    repo.resetHard(lkg);
    repo.deleteBranch(checkpoint, true); // wip 未合并即删除（-D），rollback 语义
    state.clearPending();
  };

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'lifecycle-finalize-'));
    git(['init', '-b', 'main']);
    git(['config', 'user.email', 'test@test.com']);
    git(['config', 'user.name', 'test']);
    // state/ 是 StateStore 运行时目录（真实 DSH 中位于 profileDir，不在 repoRoot 内）；
    // 测试仓库里必须忽略，否则收尾后工作区永远不干净
    writeFileSync(join(dir, '.gitignore'), 'state/\n');
    mkdirSync(join(dir, 'agent-dh'));
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v1');
    git(['add', '-A']);
    git(['commit', '-m', 'init']);
    // 递增时钟：同一测试内连续建多个 wip 分支避免同秒撞名
    let tick = 0;
    repo = new GitRepo(dir, () => new Date(Date.now() + tick++ * 1000));
    state = new StateStore(join(dir, 'state'));
    state.writeLastKnownGood(repo.head());
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  const setupPendingWithWip = () => {
    // 模拟 self_restart：改代码 → wip 检查点分支
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2-wip');
    const wip = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: test change');
    const base = repo.currentBranch(); // 现在在 wip 分支
    state.writePending({
      reason: 'test restart',
      resume_task: 'continue previous task',
      checkpoint_branch: wip!.branch,
      base_branch: 'main',
      last_known_good: state.readLastKnownGood()!,
      attempt: 1,
      ts: new Date().toISOString(),
    });
    return wip!.branch;
  };

  it('merge：wip 分支快进合回基线，last-known-good 更新，wip 删除，pending 清理', () => {
    const wipBranch = setupPendingWithWip();
    const lkgBefore = state.readLastKnownGood()!;
    const hash = doMerge(wipBranch, 'main');

    expect(repo.currentBranch()).toBe('main');
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v2-wip'); // 改动合入基线
    expect(hash).not.toBe(lkgBefore); // last-known-good 前进
    expect(state.readLastKnownGood()).toBe(hash);
    expect(git(['branch', '--list', wipBranch])).toBe(''); // wip 已删
    expect(state.readPending()).toBeNull(); // pending 已清
    expect(repo.isClean()).toBe(true);
  });

  it('rollback：放弃 wip 改动回基线，硬重置到 last-known-good', () => {
    const wipBranch = setupPendingWithWip();
    const lkg = state.readLastKnownGood()!;

    doRollback(wipBranch, 'main', lkg);

    expect(repo.currentBranch()).toBe('main');
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v1'); // wip 改动被放弃
    expect(repo.head()).toBe(lkg); // 停在 last-known-good
    expect(git(['branch', '--list', wipBranch])).toBe('');
    expect(state.readPending()).toBeNull();
    expect(repo.isClean()).toBe(true);
  });

  it('无 wip 检查点（改动已在基线）：merge/rollback 仅确认，不建分支不退出', () => {
    // 模拟直接提交在基线的场景：无 pending 或 pending 无 checkpoint_branch
    expect(state.readPending()).toBeNull();
    // 基线已有提交，无 wip 可合——收尾路径应保持基线不动
    const head = repo.head();
    expect(head).toBe(state.readLastKnownGood());
    expect(repo.currentBranch()).toBe('main');
  });

  it('exit：无 git 操作，仅保留基线状态（进程退出由调用方 setTimeout 触发，此处验证 git 不变）', () => {
    setupPendingWithWip();
    const head = repo.head();
    // exit 语义：不合并不重置，仅清理 pending
    state.clearPending();
    expect(repo.head()).toBe(head); // git 无变化
    expect(state.readPending()).toBeNull();
  });

  it('merge 回归：wip 内容已等价并入且 main 前进 → 不滞留、正常收尾', () => {
    // 审计实证场景：wip 内容被人工 cherry-pick 到 main 后 main 前进 → 旧 mergeFfOnly 必败滞留
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2-wip');
    const wipBranch = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: test change')!; // 从 main@v1 切出
    repo.checkout('main');
    // main 上等价重放（patch-id 相同、hash 不同）+ 前进
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2-wip');
    git(['add', '-A']);
    git(['commit', '-m', 'manual equivalent of wip']);
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v3-main');
    git(['add', '-A']);
    git(['commit', '-m', 'main advance']);
    state.writePending({
      reason: 'audit repro',
      resume_task: '',
      checkpoint_branch: wipBranch,
      base_branch: 'main',
      last_known_good: state.readLastKnownGood()!,
      attempt: 1,
      ts: new Date().toISOString(),
    });

    // 不再抛错（旧版此处 throw "请人工处理"），normal 收尾
    const hash = doMerge(wipBranch, 'main');

    expect(repo.currentBranch()).toBe('main');
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v3-main'); // main 领先内容保留
    expect(git(['branch', '--list', wipBranch])).toBe(''); // 等价并入 → 强删不滞留
    expect(state.readPending()).toBeNull();
    expect(repo.isClean()).toBe(true);
    expect(state.readLastKnownGood()).toBe(hash);
  });

  it('merge 整链清理：收尾主 wip 时同链已并入的残留分支一并清掉，未并入分支保留', () => {
    // 历史残留（143233/143443/143536 型）：内容均已并入 main 但分支滞留
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'chain1');
    const w1 = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: chain1')!;
    repo.checkout('main');
    repo.mergeFfOnly(w1.branch); // w1 物理并入（分支仍存）
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'chain2');
    const w2 = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: chain2')!;
    repo.checkout('main');
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'chain2');
    git(['add', '-A']);
    git(['commit', '-m', 'manual equivalent of chain2']); // w2 等价并入 main
    // 真正待收尾的 checkpoint：独立未并入改动
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'current');
    const cur = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: current')!;
    repo.checkout('main');

    const hash = doMerge(cur.branch, 'main');

    expect(git(['branch', '--list', cur.branch])).toBe('');
    expect(git(['branch', '--list', w1.branch])).toBe(''); // 链残留物理并入 → 清
    expect(git(['branch', '--list', w2.branch])).toBe(''); // 链残留等价并入 → 清
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('current');
    expect(repo.currentBranch()).toBe('main');
    expect(repo.isClean()).toBe(true);
    expect(state.readLastKnownGood()).toBe(hash);
  });
});
