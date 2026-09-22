// serves: FR-5
/**
 * 立项拒绝留痕（REQ-260922012924-2e29 FR-5）——「用户在立项弹框点了 ✖️ 不需要立项」
 * 的可查台账：回答"这个窗口最近是不是拒绝过立项"，让 reqboard_capture 弹框前置检查
 * 能拦截超时重弹（用户答复因调用方死亡而丢失的场景——2026-09-21 现场事故）。
 *
 * 与 isolation-trace 同款纪律：本模块是**纯逻辑**（容量 + 追加 + 校验 + TTL 判定），
 * 不 import node:、不取时间（at 由用例经注入的 Clock 落章）。落盘由
 * adapters/CaptureRejectionFile.ts 实现（原子写 + 串行队列）。
 *
 * TTL 语义在消费方：30 分钟内的同窗口拒绝视为"用户刚说过不"，reqboard_capture 不再弹框；
 * 不设主动清理，ring buffer 自然淘汰（拒绝是低频事件，50 条足够回查）。
 *
 * @module dsh-pmboard/application/internal/capture-rejections
 */
import { fmt } from '../../domain/text/fmt.js'
import type { CaptureRejection } from '../ports.js'

/** ring buffer 保留条数。 */
export const CAPTURE_REJECTION_CAP = 50

/** 留痕文件的相对位置（相对 DSH 主目录）。 */
export const CAPTURE_REJECTION_REL = 'state/capture-rejections.json'

/** 拒绝粘滞时长：30 分钟内的同窗口拒绝 → 不再弹框。 */
export const CAPTURE_REJECTION_TTL_MS = 30 * 60 * 1000

/** ring buffer 追加：保留最近 cap 条（超界丢最旧）。cap 非法 → 响亮抛错。 */
export function appendCaptureRejection(
  existing: readonly CaptureRejection[],
  entry: CaptureRejection,
  cap: number = CAPTURE_REJECTION_CAP,
): CaptureRejection[] {
  if (!Number.isInteger(cap) || cap <= 0) {
    throw new Error(fmt('capture-rejections cap 必须是正整数，收到 {cap}', { cap }))
  }
  const next = [...existing, entry]
  return next.length > cap ? next.slice(next.length - cap) : next
}

/** 一条记录是否可信（读回时防残缺记录混入）：windowKey 字符串 + at 有限数。 */
export function isCaptureRejection(raw: unknown): raw is CaptureRejection {
  if (typeof raw !== 'object' || raw === null) return false
  const o = raw as Record<string, unknown>
  if (typeof o.windowKey !== 'string' || o.windowKey.length === 0) return false
  if (typeof o.at !== 'number' || !Number.isFinite(o.at)) return false
  if (o.title !== undefined && typeof o.title !== 'string') return false
  return true
}

/**
 * 同窗口最近一条**仍在粘滞期**的拒绝（TTL 内）；无 → undefined。
 * 多条取最新（at 最大者）。
 */
export function recentCaptureRejection(
  list: readonly CaptureRejection[],
  windowKey: string,
  now: number,
  ttl: number = CAPTURE_REJECTION_TTL_MS,
): CaptureRejection | undefined {
  let latest: CaptureRejection | undefined
  for (const r of list) {
    if (r.windowKey !== windowKey) continue
    if (now - r.at > ttl) continue
    if (latest === undefined || r.at > latest.at) latest = r
  }
  return latest
}
