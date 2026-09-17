/**
 * 里程碑超时提醒规约（REQ-47939a t3 / REQ-2e9473 t09/W1.5）。
 *
 * 规则：绑定窗口的最新 open 需求，若其**当前阶段**已登记但超时（默认 30min）未确认的产物
 * 存在 → 应当提醒。判定从 host/capture-hook.ts 的 milestoneReminderFor 抽出——提醒文案
 * （含分钟数、调用指引）留在 host，规则（哪个产物算超时未确认）进 domain 可独立单测。
 *
 * 纯函数：不碰时间（now 由参数注入）、不碰随机数。
 */

export interface MilestoneArtifactLike {
  stage: string
  kind: string
  path: string
  registeredAt: number
  confirmedAt?: number
}

export interface MilestoneReqLike {
  status: string
  artifacts?: readonly MilestoneArtifactLike[]
}

/**
 * 找出「当前阶段已登记、未确认、且登记已超时」的产物（无则 undefined）。
 * 只检查 stage === req.status 的产物：其它阶段的未确认产物不属本节点。
 */
export function findStaleUnconfirmedArtifact(
  req: MilestoneReqLike,
  now: number,
  reminderAfterMs: number,
): MilestoneArtifactLike | undefined {
  return (req.artifacts ?? []).find(a =>
    a.stage === req.status
    && a.confirmedAt === undefined
    && now - a.registeredAt > reminderAfterMs,
  )
}

/** 是否需要提醒人确认（存在超时未确认的本阶段产物）。 */
export function shouldRemindConfirm(req: MilestoneReqLike, now: number, reminderAfterMs: number): boolean {
  return findStaleUnconfirmedArtifact(req, now, reminderAfterMs) !== undefined
}
