/**
 * quick_restart 工作快照与续跑判定（纯函数 —— 单测直接覆盖这一层）。
 *
 * 场景（RFC 016 增补，2026-09-24）：轻量重启会杀死所有窗口的在飞 turn，
 * 断线前必须记下「谁还在工作」，重启后逐窗注入续跑消息，让它们把活干完。
 *
 * 判据：Agent.status === 'running' = 正在跑 turn（DSH 权威状态机，
 * idle 窗口的 inbox 排队消息是持久化的，重启不丢，无需续跑）。
 *
 * @module web-liveness/resume
 */

/** 一条「断线时还在工作」的窗口记录。 */
export interface ResumeEntry {
  /** 窗口（agent）id。 */
  agentId: string
  /** 快照时刻的 status（恒为 'running'，留字段供审计）。 */
  status: string
  /** 快照时间戳（ms）。 */
  at: number
}

/** 快照文件 state/quick-restart-resume.json 的格式。 */
export interface ResumeFile {
  /** 触发本次快照的 quick_restart 原因。 */
  reason: string
  /** 快照时间戳（ms）。 */
  at: number
  /** 尚未投递续跑消息的窗口。 */
  sessions: ResumeEntry[]
}

/** 续跑消息等待窗口出现的时长（与 lifecycle setupResume 口径一致：30 分钟）。 */
export const RESUME_WAIT_MS = 30 * 60 * 1000

/** 快照条目过期阈值：超过 24h 未投递的条目视为死信，重启后不再投递。 */
export const RESUME_ENTRY_TTL_MS = 24 * 60 * 60 * 1000

interface StatusLike {
  id: unknown
  status: string
}

/**
 * 从活窗口清单挑出「正在工作」的窗口 id（快照口径）。
 * 只认 running：idle 窗口没有被打断的工作（排队 inbox 持久化，重启后照常消费）。
 */
export function selectBusyAgentIds(agents: StatusLike[]): string[] {
  return agents.filter((a) => a.status === 'running').map((a) => String(a.id))
}

/**
 * 读入快照文件后分流：仍有效的待投递条目 vs 已过期死信。
 * @param entries - 文件里的 sessions
 * @param now - 当前时间戳（ms）
 * @param ttlMs - 条目过期阈值，默认 {@link RESUME_ENTRY_TTL_MS}
 */
export function partitionResumeEntries(
  entries: ResumeEntry[] | undefined,
  now: number,
  ttlMs = RESUME_ENTRY_TTL_MS,
): { active: ResumeEntry[]; expired: ResumeEntry[] } {
  const active: ResumeEntry[] = []
  const expired: ResumeEntry[] = []
  for (const e of entries ?? []) {
    if (!e || typeof e.agentId !== 'string' || !Number.isFinite(e.at)) {
      expired.push(e) // 坏条目按死信处理，不阻塞其余投递
    } else if (now - e.at >= ttlMs) {
      expired.push(e)
    } else {
      active.push(e)
    }
  }
  return { active, expired }
}

/**
 * 渲染续跑消息（与 lifecycle 的「自修复续跑」措辞区分——那条绑定 git 检查点语义）。
 */
export function renderResumeMessage(reason: string): string {
  return [
    '【轻量重启续跑】此消息由 web-liveness 插件自动注入，不是用户消息。',
    `服务刚执行了 quick_restart（原因：${reason}），你被断线前正在工作（turn 被杀死）。`,
    '请检查你手头任务的状态：继续未完成的部分；若任务已无法从中断点接续，向用户汇报中断点和已完成的部分。',
  ].join('\n')
}
