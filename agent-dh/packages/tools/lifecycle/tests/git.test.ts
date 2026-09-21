import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { GitRepo } from '../src/git.js';

describe('GitRepo', () => {
  let dir: string;
  let repo: GitRepo;
  const git = (args: string[]) =>
    execFileSync('git', args, { cwd: dir, encoding: 'utf8' }).trim();

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'lifecycle-git-'));
    git(['init', '-b', 'main']);
    git(['config', 'user.email', 'test@test.com']);
    git(['config', 'user.name', 'test']);
    mkdirSync(join(dir, 'agent-dh'));
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v1');
    git(['add', '-A']);
    git(['commit', '-m', 'init']);
    // 递增时钟：同一测试内连续建多个 wip 分支避免同秒撞名
    let tick = 0;
    repo = new GitRepo(dir, () => new Date(Date.now() + tick++ * 1000));
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it('currentBranch / head / hasChanges', () => {
    expect(repo.currentBranch()).toBe('main');
    expect(repo.head()).toMatch(/^[0-9a-f]{40}$/);
    expect(repo.hasChanges(['agent-dh/'])).toBe(false);
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    expect(repo.hasChanges(['agent-dh/'])).toBe(true);
  });

  it('isClean：干净返回 true，有改动返回 false', () => {
    expect(repo.isClean()).toBe(true);
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    expect(repo.isClean()).toBe(false);
    git(['add', '-A']);
    git(['commit', '-m', 'dirty']);
    expect(repo.isClean()).toBe(true);
  });

  it('createWipBranch：有改动建新分支并提交，工作区内容不变', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    const mainHead = repo.head();
    const wip = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: test');
    expect(wip).not.toBeNull();
    expect(wip!.branch).toMatch(/^agent-self\/\d{8}-\d{6}$/);
    expect(wip!.files).toEqual(['agent-dh/a.txt']);
    expect(repo.currentBranch()).toBe(wip!.branch);
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v2');
    // 回 main 后文件回到 v1，且 wip 分支可 ff 合回
    repo.checkout('main');
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v1');
    repo.mergeFfOnly(wip!.branch);
    expect(repo.head()).not.toBe(mainHead);
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v2');
    repo.deleteBranch(wip!.branch);
    expect(git(['branch', '--list', wip!.branch])).toBe('');
  });

  it('createWipBranch：只提交指定路径，其他会话的脏文件保留在工作区', () => {
    // 多会话并行常态：agent-dh/ 内有本次修复，其他目录有别的会话的未提交改动
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    writeFileSync(join(dir, 'other-session.txt'), 'not mine');
    const wip = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: scoped');
    expect(wip).not.toBeNull();
    expect(wip!.files).toEqual(['agent-dh/a.txt']); // 不裹入 other-session.txt
    expect(readFileSync(join(dir, 'other-session.txt'), 'utf8')).toBe('not mine'); // 仍留在工作区
    repo.checkout('main');
    expect(readFileSync(join(dir, 'other-session.txt'), 'utf8')).toBe('not mine'); // 切分支也不丢
  });

  it('createWipBranch：无改动返回 null 且不建分支', () => {
    expect(repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: noop')).toBeNull();
    expect(repo.currentBranch()).toBe('main');
  });

  it('resetHard：丢弃工作区改动与未推送提交（rollback 语义）', () => {
    const baseHead = repo.head();
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2-dirty');
    repo.resetHard(baseHead);
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v1'); // 工作区改动被丢弃
    expect(repo.isClean()).toBe(true);

    // 有未推送提交时也能回退
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v3');
    git(['add', '-A']);
    git(['commit', '-m', 'bad commit']);
    repo.resetHard(baseHead);
    expect(repo.head()).toBe(baseHead);
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v1');
  });

  it('commitOnCurrent：有改动提交到当前分支并返回 head；无改动返回 null 不提交', () => {
    expect(repo.commitOnCurrent(['agent-dh/'], 'noop')).toBeNull();
    expect(repo.head()).toBe(git(['rev-parse', 'HEAD']));
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    const h = repo.commitOnCurrent(['agent-dh/'], 'direct on main');
    expect(h).toMatch(/^[0-9a-f]{40}$/);
    expect(repo.currentBranch()).toBe('main'); // 不切分支
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v2');
  });

  it('finalizeMerge：干净 ff（main 未前进）→ ff-merged，分支保留由调用方删', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    const wip = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: v2')!;
    repo.checkout('main');
    const res = repo.finalizeMerge('main', wip.branch, 'merge(wip): 收尾');
    expect(res.outcome).toBe('ff-merged');
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v2');
    expect(repo.branchExists(wip.branch)).toBe(true); // 方法不删分支
    repo.deleteBranch(wip.branch); // 已合并 → -d 安全
    expect(git(['branch', '--list', wip.branch])).toBe('');
  });

  it('finalizeMerge：wip 已物理并入 base → already-merged，无操作', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    const wip = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: v2')!;
    repo.checkout('main');
    repo.mergeFfOnly(wip.branch); // 已并入
    const res = repo.finalizeMerge('main', wip.branch, 'merge(wip): 收尾');
    expect(res.outcome).toBe('already-merged');
    expect(res.merged_hash).toBe(repo.head());
  });

  it('finalizeMerge：wip 内容已等价并入且 main 前进 → already-cherried（旧版滞留场景，不抛错）', () => {
    // 审计实证：143233/143443/143536 内容被 cherry-pick 到 main 后 main 前进，旧 mergeFfOnly ff 必败
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2-wip');
    const wip = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: v2')!; // 从 main@v1 切出
    repo.checkout('main');
    // main 上等价重放（patch-id 相同、hash 不同）+ 前进
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2-wip');
    git(['add', '-A']);
    git(['commit', '-m', 'manual equivalent of wip']);
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v3-main');
    git(['add', '-A']);
    git(['commit', '-m', 'main advance']);
    const res = repo.finalizeMerge('main', wip.branch, 'merge(wip): 收尾');
    expect(res.outcome).toBe('already-cherried');
    expect(res.merged_hash).toBe(repo.head()); // 无新提交
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v3-main'); // main 领先内容保留
    repo.deleteBranch(wip.branch, true); // 非祖先 → -D
    expect(git(['branch', '--list', wip.branch])).toBe('');
  });

  it('finalizeMerge：main 前进但改不同文件 → 3-way 合并提交', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'wip-a');
    const wip = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: a')!;
    repo.checkout('main');
    writeFileSync(join(dir, 'b.txt'), 'main-b'); // 另一文件，无冲突
    git(['add', '-A']);
    git(['commit', '-m', 'main adds b']);
    const res = repo.finalizeMerge('main', wip.branch, 'merge(wip): 收尾');
    expect(res.outcome).toBe('merged');
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('wip-a');
    expect(readFileSync(join(dir, 'b.txt'), 'utf8')).toBe('main-b');
    repo.deleteBranch(wip.branch);
  });

  it('finalizeMerge：真冲突 → abort + 抛错，wip 保留不丢内容', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'wip-a');
    const wip = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: a')!;
    repo.checkout('main');
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'main-b'); // 同文件冲突
    git(['add', '-A']);
    git(['commit', '-m', 'main advances same file']);
    expect(() => repo.finalizeMerge('main', wip.branch, 'merge(wip): 收尾')).toThrow(/冲突|保留/);
    expect(repo.currentBranch()).toBe('main'); // abort 后回到调用方已 checkout 的分支
    expect(repo.isClean()).toBe(true); // 合并中止，无残留
    expect(repo.branchExists(wip.branch)).toBe(true); // wip 保留
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('main-b');
  });

  it('cleanupWipChain：清物理并入+等价并入的分支，保留内容未并入的分支', () => {
    // A：创建后 ff 合入 main（物理并入，分支仍存）
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'vA');
    const A = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: A')!;
    repo.checkout('main');
    repo.mergeFfOnly(A.branch);
    // B：从 main 切出，main 随后等价重放 B 内容（等价并入）
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'vB');
    const B = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: B')!;
    repo.checkout('main');
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'vB');
    git(['add', '-A']);
    git(['commit', '-m', 'manual equivalent of B']);
    // C：独立改动，未并入（如 144904 内容仍在 feat 分支）
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'vC');
    const C = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: C')!;
    repo.checkout('main');
    const removed = repo.cleanupWipChain('agent-self', 'main');
    expect(removed.sort()).toEqual([A.branch, B.branch].sort());
    expect(git(['branch', '--list', A.branch])).toBe('');
    expect(git(['branch', '--list', B.branch])).toBe('');
    expect(git(['branch', '--list', C.branch])).toBe(C.branch); // 未并入 → 保留
  });

  it('resolveChainBase：独立 wip 溯源到 main；链式 wip 溯源到链根 main', () => {
    // 独立 wip
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    const A = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: A')!;
    expect(repo.resolveChainBase(A.branch)).toBe('main');
    // 链式：在 A 上再切 B（旧版 wip-on-wip），B 的父在 A 上
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v3');
    const B = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: B on A')!;
    expect(repo.resolveChainBase(B.branch)).toBe('main'); // 沿 B→A→main
    expect(repo.resolveChainBase('nonexistent')).toBeNull();
  });
});