/**
 * guard.ts 单测 —— quick_restart 的两道闸（互斥锁新鲜度 / 限流间隔）。
 * 纯函数，无 I/O；闸错了轻则与 self_restart 互杀进程，重则重蹈 tmp-restart 死循环。
 */
import { describe, expect, it } from 'vitest'
import {
  LOCK_FRESH_MS,
  MIN_INTERVAL_MS,
  isLockFresh,
  quickRestartAllowed,
} from '../src/guard.js'

describe('isLockFresh（self_restart 互斥）', () => {
  const now = 1_000_000_000_000

  it('锁不存在（undefined）→ 不新鲜，放行', () => {
    expect(isLockFresh(undefined, now)).toBe(false)
  })

  it('mtime 非法（NaN）→ 不新鲜，放行', () => {
    expect(isLockFresh(NaN, now)).toBe(false)
  })

  it('mtime 在 15 分钟内 → 新鲜，必须避让', () => {
    expect(isLockFresh(now - 60_000, now)).toBe(true)
    expect(isLockFresh(now - LOCK_FRESH_MS + 1, now)).toBe(true)
  })

  it('mtime 恰好/超过 15 分钟 → 过期，放行', () => {
    expect(isLockFresh(now - LOCK_FRESH_MS, now)).toBe(false)
    expect(isLockFresh(now - LOCK_FRESH_MS - 1, now)).toBe(false)
  })

  it('mtime 在未来（时钟漂移）→ 视为新鲜，宁可避让', () => {
    expect(isLockFresh(now + 60_000, now)).toBe(true)
  })
})

describe('quickRestartAllowed（5 分钟限流）', () => {
  const now = 1_000_000_000_000

  it('从未调用过（undefined）→ 放行', () => {
    expect(quickRestartAllowed(undefined, now)).toBe(true)
  })

  it('时间戳非法（NaN）→ 放行（当作没调过，避免坏文件永久锁死）', () => {
    expect(quickRestartAllowed(NaN, now)).toBe(true)
  })

  it('不足 5 分钟 → 拒绝', () => {
    expect(quickRestartAllowed(now - 60_000, now)).toBe(false)
    expect(quickRestartAllowed(now - MIN_INTERVAL_MS + 1, now)).toBe(false)
  })

  it('恰好/超过 5 分钟 → 放行', () => {
    expect(quickRestartAllowed(now - MIN_INTERVAL_MS, now)).toBe(true)
    expect(quickRestartAllowed(now - MIN_INTERVAL_MS - 1, now)).toBe(true)
  })

  it('自定义间隔生效', () => {
    expect(quickRestartAllowed(now - 1_000, now, 2_000)).toBe(false)
    expect(quickRestartAllowed(now - 2_000, now, 2_000)).toBe(true)
  })
})
