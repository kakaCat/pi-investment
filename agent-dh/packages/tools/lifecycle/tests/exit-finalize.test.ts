import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GitRepo } from '../src/git.js';
import { exitFinalize, describeExitFinalize } from '../src/exit-finalize.js';

/**
 * exit-finalize（P0 修复，2026-09-10）：self_finalize(action=exit) 的退出前收尾。
 * 回归的缺陷：exit 清 pending 却不回干线 → 下次 boot 的 boot-recovery I3 把设计性退出误判为
 * 崩溃滞留 → 静默 checkout 回干线 → 只存在于 wip 上的文件（其他窗口被检查点收走的未提交改动）
 * 从磁盘消失且无人告知。本测试用真实 git 断言"文件还在 + 有具名归属"。
 */
describe('exit-finalize', () => {
  let dir: string;
  let repo: GitRepo;
  const now = Date.UTC(2026, 8, 10, 13, 33, 0);
  const git = (g: string[]) => execFileSync('git', g, { cwd: dir, encoding: 'utf8' }).trim();

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'lifecycle-exit-'));
    git(['init', '-b', 'main']);
    git(['config', 'user.email', 'test@test.com']);
    git(['config', 'user.name', 'test']);
    writeFileSync(join(dir, 'base.txt'), 'base');
    writeFileSync(join(dir, 'foreign.txt'), 'original');
    git(['add', '-A']);
    git(['commit', '-m', 'init']);
    repo = new GitRepo(dir, () => new Date(now));
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  /** 复刻重启检查点：HEAD 落在 agent-self/*，wip 提交里含"其他窗口未提交的改动"+ 其新建文件 */
  const makeCheckpoint = (): string => {
    writeFileSync(join(dir, 'foreign.txt'), 'foreign-uncommitted-edit');
    writeFileSync(join(dir, 'new-by-other-window.txt'), 'draft');
    const w = repo.createWipBranch('agent-self', ['.'], 'wip: checkpoint')!.branch;
    expect(repo.currentBranch()).toBe(w);
    return w;
  };

  it('无检查点 → 跳过且无 git 动作', () => {
    const r = exitFinalize(repo, { checkpoint: null, base: 'main' });
    expect(r.skipped).toBe('no-checkpoint');
    expect(r.archived).toBeNull();
    expect(repo.currentBranch()).toBe('main');
  });

  it('不在检查点分支上（已 merge/rollback 过）→ 跳过', () => {
    const r = exitFinalize(repo, { checkpoint: 'agent-self/not-here', base: 'main' });
    expect(r.skipped).toMatch(/^not-on-checkpoint/);
    expect(r.checkedOutTo).toBeNull();
  });

  it('核心：归档到 wip/rescued-* + 取回工作区 + 回干线 + 收掉已归档的检查点分支', () => {
    const w = makeCheckpoint();
    const wHash = git(['rev-parse', w]); // 检查点提交（收尾后分支会被收掉，先记 hash）
    const r = exitFinalize(repo, { checkpoint: w, base: 'main', now });

    expect(r.error).toBeNull();
    expect(r.archived).toBeTruthy();
    expect(repo.branchExists(r.archived!)).toBe(true);
    // 归档分支 = 检查点提交本身（内容零丢失）
    expect(git(['rev-parse', r.archived!])).toBe(wHash);
    expect(git(['show', `${r.archived!}:new-by-other-window.txt`])).toBe('draft');

    // 回干线（与 boot-recovery I3 目标一致 → 下次 boot 不再有滞留态）
    expect(r.checkedOutTo).toBe('main');
    expect(repo.currentBranch()).toBe('main');

    // 关键回归：其他窗口的改动仍在磁盘上，且保持"未提交改动"形态（撤销=git status 可见）
    expect(readFileSync(join(dir, 'foreign.txt'), 'utf8')).toBe('foreign-uncommitted-edit');
    expect(readFileSync(join(dir, 'new-by-other-window.txt'), 'utf8')).toBe('draft');
    const st = git(['status', '--porcelain']);
    expect(st).toMatch(/^\s*M foreign\.txt$/m);
    expect(st).toMatch(/^\?\? new-by-other-window\.txt$/m);

    // 检查点分支收掉（内容在归档分支 + 工作区，双重保留）
    expect(r.deleted).toBe(w);
    expect(repo.branchExists(w)).toBe(false);
  });

  it('wip 与干线同提交（无独有内容）→ 不建归档分支，工作区保持干净', () => {
    git(['checkout', '-b', 'agent-self/20260910-empty']);
    const w = repo.currentBranch();
    const r = exitFinalize(repo, { checkpoint: w, base: 'main', now });
    expect(r.archived).toBeNull();
    expect(r.restored).toEqual([]);
    expect(repo.currentBranch()).toBe('main');
    expect(git(['status', '--porcelain'])).toBe('');
    expect(r.deleted).toBe(w); // 无内容可归档 → 分支照收（零丢失）
  });

  it('describeExitFinalize：有动作给摘要，无动作给空串', () => {
    const w = makeCheckpoint();
    const r = exitFinalize(repo, { checkpoint: w, base: 'main', now });
    const txt = describeExitFinalize(r);
    expect(txt).toContain(r.archived!);
    expect(txt).toContain('取回工作区');
    expect(describeExitFinalize({
      skipped: 'no-checkpoint', archived: null, restored: [], checkedOutTo: null, deleted: null, error: null,
    })).toBe('');
  });
});
