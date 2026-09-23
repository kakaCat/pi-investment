/**
 * quick_restart 护栏判定（纯函数 —— 单测直接覆盖这一层）。
 *
 * 两道闸，spawn 重启器之前必须全过：
 *   1. 互斥：lifecycle 的 self_restart 进行中（restarting.lock 新鲜）时拒绝——
 *      两个重启器并发 = 互相杀对方刚拉起的进程（2026-09-23 tmp-restart 事故的同类风险）。
 *   2. 限流：距上次 quick_restart 不足 MIN_INTERVAL_MS 拒绝——轻量重启不是心跳，
 *      agent 连着调说明在打转，拦下来让它换思路。
 *
 * @module web-liveness/guard
 */

/** restarting.lock 的新鲜度阈值（与 lifecycle 的锁 stale 接管口径一致：15 分钟）。 */
export const LOCK_FRESH_MS = 15 * 60 * 1000

/** 两次 quick_restart 的最小间隔（5 分钟）。 */
export const MIN_INTERVAL_MS = 5 * 60 * 1000

/** 重启器给 agent 留的说话/落盘时间（kill 前的宽限）。 */
export const PRE_KILL_DELAY_S = 10

/**
 * self_restart 的锁是否新鲜（新鲜 = 有重启正在进行，quick_restart 必须避让）。
 * @param lockMtimeMs - restarting.lock 的 mtime；锁不存在传 undefined。
 * @param now - 当前时间戳（ms）。
 */
export function isLockFresh(lockMtimeMs: number | undefined, now: number): boolean {
  if (lockMtimeMs === undefined || !Number.isFinite(lockMtimeMs)) return false
  return now - lockMtimeMs < LOCK_FRESH_MS
}

/**
 * 距上次 quick_restart 是否已超过最小间隔。
 * @param lastRequestedAt - 上次请求时间戳；从未调用过传 undefined。
 * @param now - 当前时间戳（ms）。
 * @param minIntervalMs - 最小间隔，默认 {@link MIN_INTERVAL_MS}。
 */
export function quickRestartAllowed(
  lastRequestedAt: number | undefined,
  now: number,
  minIntervalMs = MIN_INTERVAL_MS,
): boolean {
  if (lastRequestedAt === undefined || !Number.isFinite(lastRequestedAt)) return true
  return now - lastRequestedAt >= minIntervalMs
}
