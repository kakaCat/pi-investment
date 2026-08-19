import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { GitRepo } from './git.js';

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
    repo = new GitRepo(dir);
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it('currentBranch / head / hasChanges', () => {
    expect(repo.currentBranch()).toBe('main');
    expect(repo.head()).toMatch(/^[0-9a-f]{40}$/);
    expect(repo.hasChanges(['agent-dh/'])).toBe(false);
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    expect(repo.hasChanges(['agent-dh/'])).toBe(true);
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
});
