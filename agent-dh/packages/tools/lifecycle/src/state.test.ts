import { mkdtempSync, readFileSync, existsSync, rmSync, writeFileSync } from 'node:fs';
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

  it('锁过期接管：超过 staleMs 的残留锁可被强行获取，新锁不可', () => {
    // 模拟机器掉电/重启器被强杀留下的 20 分钟前的死锁
    writeFileSync(join(dir, 'restarting.lock'), String(Date.now() - 20 * 60 * 1000));
    expect(store.acquireLock()).toBe(true); // stale → 接管成功
    expect(store.acquireLock()).toBe(false); // 新锁未过期 → 仍互斥
    // 损坏的锁内容（非数字时间戳）不接管，按未获取处理
    store.releaseLock();
    writeFileSync(join(dir, 'restarting.lock'), 'garbage');
    expect(store.acquireLock()).toBe(false);
  });

  it('readJson 容错：损坏的 JSON 按无状态返回 null，不抛异常', () => {
    writeFileSync(join(dir, 'pending-resume.json'), '{"reason": "被强杀截断');
    expect(store.readPending()).toBeNull();
    writeFileSync(join(dir, 'restart-counter.json'), 'not json at all');
    expect(store.checkRateLimit(3, Date.now()).count).toBe(0);
  });

  it('clearPendingDone：清除 done 文件，重复调用不报错', () => {
    store.writePending({
      reason: 'r', resume_task: 't', checkpoint_branch: 'agent-self/x',
      base_branch: 'main', last_known_good: 'abc', attempt: 1, ts: '2026-08-19T00:00:00Z',
    });
    store.markPendingDone();
    expect(store.readPendingDone()).not.toBeNull();
    store.clearPendingDone();
    expect(store.readPendingDone()).toBeNull();
    store.clearPendingDone(); // 幂等
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
