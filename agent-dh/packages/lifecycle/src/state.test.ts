import { mkdtempSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { StateStore } from './state.js';

describe('StateStore', () => {
  let dir: string;
  let store: StateStore;
  beforeEach(() => { dir = mkdtempSync(join(tmpdir(), 'lifecycle-')); store = new StateStore(dir); });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it('pending 写读回环 + markDone 改名', () => {
    expect(store.readPending()).toBeNull();
    store.writePending({
      reason: 'r', resume_task: 't', checkpoint_branch: 'agent-self/x',
      base_branch: 'main', last_known_good: 'abc', attempt: 1, ts: '2026-08-19T00:00:00Z',
    });
    expect(store.readPending()?.checkpoint_branch).toBe('agent-self/x');
    store.markPendingDone();
    expect(store.readPending()).toBeNull();
    expect(existsSync(join(dir, 'pending-resume.done.json'))).toBe(true);
    expect(JSON.parse(readFileSync(join(dir, 'pending-resume.done.json'), 'utf8')).resume_task).toBe('t');
  });

  it('速率限制：窗口内计数，超窗重置', () => {
    const now = Date.parse('2026-08-19T10:00:00Z');
    expect(store.checkRateLimit(3, now).allowed).toBe(true);
    store.bumpCounter(now);
    store.bumpCounter(now);
    store.bumpCounter(now);
    expect(store.checkRateLimit(3, now).allowed).toBe(false);
    const later = now + 3_700_000; // 超过 1 小时
    expect(store.checkRateLimit(3, later).allowed).toBe(true);
  });

  it('锁文件互斥获取与释放', () => {
    expect(store.acquireLock()).toBe(true);
    expect(store.acquireLock()).toBe(false); // 重入被拒
    store.releaseLock();
    expect(store.acquireLock()).toBe(true);
  });

  it('attempt 计数：同任务累加，换任务重置，clearAttempt 清零', () => {
    expect(store.nextAttempt('修复A')).toBe(1);
    expect(store.nextAttempt('修复A')).toBe(2);
    expect(store.nextAttempt('修复B')).toBe(1);
    store.clearAttempt();
    expect(store.nextAttempt('修复B')).toBe(1);
  });

  it('last-known-good 读写', () => {
    expect(store.readLastKnownGood()).toBeNull();
    store.writeLastKnownGood('deadbeef');
    expect(store.readLastKnownGood()).toBe('deadbeef');
  });
});
