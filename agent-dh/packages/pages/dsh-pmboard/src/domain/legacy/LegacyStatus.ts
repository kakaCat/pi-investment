/**
 * 迁移专属：legacy 状态名与历史时间线回填（REQ-47939a t10）。
 *
 * 为什么单独成模块：这几个函数**只服务于 v4→v5 迁移**（脚本 scripts/migrate-ledger.ts、
 * 用例 application/use-cases/MigrateLedger.ts）。t10 收口后**运行时读路径不再需要**它们——
 * 台账已迁移、statusHistory 已固化，故从 shared/protocol.ts（运行时契约枢纽）里整块搬出，
 * 避免"为了迁移把兼容分支永久钉在运行时读路径上"。
 *
 * 为什么在 domain/legacy：纯函数（不碰 I/O / 时间 / 随机数），且 domain 不得 import shared——
 * 这里只依赖 domain 内的 ActorRef 与两张状态表（状态名集合从 REQ_TRANSITIONS / TASK_TRANSITIONS
 * 的键派生，与运行时同一份事实源，不手抄第二份名单）。
 *
 * 搬迁口径（t10 硬约束）：函数体逐字搬入，行为零改动。
 *
 * @module dsh-pmboard/domain/legacy/LegacyStatus
 */

import type { ActorRef } from '../actor.js'
import { REQ_TRANSITIONS, type RequirementStatus } from '../requirement/RequirementStatus.js'
import { TASK_TRANSITIONS } from '../task/TaskStatus.js'

/**
 * 旧状态名迁移。迁移只改名字，不改语义。
 *   2026-09-13：reviewing → brainstorming（状态机第一次改名）
 *   2026-09-17：planning → design（设计节点英文键与中文名对齐，REQ-81aabd FR-7）
 */
export const LEGACY_REQ_STATUS_ALIASES: Readonly<Record<string, RequirementStatus>> = {
  reviewing: 'brainstorming',
  planning: 'design',
}

/**
 * 载入校验用的状态名集合。与 shared/protocol 的 ALL_REQ_STATUSES / ALL_TASK_STATUSES **同集合**
 * （前者的唯一事实源是 REQ_TRANSITIONS / TASK_TRANSITIONS 的键，后者是 MAIN+done/canceled），
 * 另加历史别名（reviewing / planning），保证老评论里的旧状态名也能被解析出来。
 */
const ALL_REQ_STATUS_NAMES: readonly string[] = [...Object.keys(REQ_TRANSITIONS), ...Object.keys(LEGACY_REQ_STATUS_ALIASES)]
const ALL_TASK_STATUS_NAMES: readonly string[] = Object.keys(TASK_TRANSITIONS)

/**
 * 时间线的原子单位（形状与 shared/protocol 的 StatusEvent **逐字段一致**；此处按 domain 的
 * ActorRef 声明，避免 domain→shared 的越界依赖）。
 */
export interface LegacyStatusEvent {
  status: string
  at: number
  by: ActorRef
  reason?: string
  inferred?: boolean
}

/** 本模块真正读到的评论字段（台账 CommentRecord 是其超集，结构兼容）。 */
export interface LegacyComment {
  body: string
  createdAt: number
  createdBy?: ActorRef
}

/** 本模块真正读写的记录字段（需求/任务记录的超集接口，结构兼容）。 */
export interface LegacyBackfillRecord {
  status: string
  createdAt: number
  updatedAt: number
  createdBy: ActorRef
  updatedBy: ActorRef
  comments: readonly LegacyComment[]
  statusHistory?: LegacyStatusEvent[]
}

/**
 * 从评论正文解析转移目标状态。覆盖历史上的三种留痕格式：
 *   `[自动推进] draft → brainstorming：…`（rollup）
 *   `[窗口推进] brainstorming → decomposing：…`（reqboard_move 工具）
 *   `[状态] decomposing ← 转移说明：…`（需求路由 move，箭头指向新状态）
 *   `[状态] → in_progress：…`（任务路由 move）
 * 解析不出或状态非法 → undefined（宁缺毋滥，绝不猜）。
 */
export function parseTransitionTarget(body: string, allowed: readonly string[]): string | undefined {
  const candidates: Array<{ re: RegExp; group: number }> = [
    { re: /\[(?:自动推进|窗口推进|人工推进)\]\s*\w+\s*→\s*(\w+)/, group: 1 },
    { re: /\[状态\]\s*(\w+)\s*←/, group: 1 },
    { re: /\[状态\]\s*→\s*(\w+)/, group: 1 },
  ]
  for (const { re, group } of candidates) {
    const m = re.exec(body)
    const hit = m?.[group]
    if (hit !== undefined && allowed.includes(hit)) return hit
  }
  return undefined
}

function backfill(
  record: { status: string; createdAt: number; updatedAt: number; createdBy: ActorRef; updatedBy: ActorRef; comments: readonly LegacyComment[] },
  initialStatus: string,
  allowed: readonly string[],
  statusHistory: LegacyStatusEvent[] | undefined,
): LegacyStatusEvent[] | undefined {
  if (statusHistory !== undefined && statusHistory.length > 0) return undefined
  const events: LegacyStatusEvent[] = [
    { status: initialStatus, at: record.createdAt, by: record.createdBy, reason: '创建', inferred: true },
  ]
  for (const c of [...record.comments].sort((a, b) => a.createdAt - b.createdAt)) {
    const raw = parseTransitionTarget(c.body, allowed)
    if (raw === undefined) continue
    // 历史评论里可能写的是旧状态名（reviewing / planning）——按别名表映射回新名，别丢历史
    const target = LEGACY_REQ_STATUS_ALIASES[raw] ?? raw
    const prev = events[events.length - 1]
    if (prev !== undefined && prev.status === target) continue
    events.push({
      status: target,
      at: c.createdAt,
      by: c.createdBy ?? { kind: 'system' },
      reason: (c.body.split('\n')[0] ?? '').slice(0, 120),
      inferred: true,
    })
  }
  const tail = events[events.length - 1]
  if (tail === undefined || tail.status !== record.status) {
    // 评论里没有该状态的留痕（老格式/直接改库）→ 用 updatedAt 兜底并标注不可考
    events.push({
      status: record.status,
      at: Math.max(record.updatedAt, record.createdAt),
      by: record.updatedBy,
      reason: '按 updatedAt 回填（当时无事件留痕）',
      inferred: true,
    })
  }
  return events
}

/** 需求时间线回填（已有事件 → 返回 undefined 不动）。旧状态名（reviewing / planning）一并接受。 */
export function backfillRequirementHistory(req: LegacyBackfillRecord): LegacyStatusEvent[] | undefined {
  return backfill(
    req,
    'draft',
    ALL_REQ_STATUS_NAMES,
    req.statusHistory,
  )
}

/**
 * 旧状态名迁移（reviewing → brainstorming、planning → design）：状态字段 + 时间线事件。
 * 迁移只改名字，不改语义；返回 true 表示发生过迁移（调用方据此决定是否落盘）。
 */
export function migrateRequirementStatusNames(req: LegacyBackfillRecord): boolean {
  let changed = false
  const alias = LEGACY_REQ_STATUS_ALIASES[req.status as string]
  if (alias !== undefined) {
    req.status = alias
    changed = true
  }
  for (const e of req.statusHistory ?? []) {
    const mapped = LEGACY_REQ_STATUS_ALIASES[e.status]
    if (mapped !== undefined) {
      e.status = mapped
      changed = true
    }
  }
  return changed
}

/**
 * 产物 stage 字段的旧名迁移（planning → design）。台账里 artifacts[].stage 与需求状态同用一套键，
 * 状态改名时**必须同步改名**，否则「产物归属哪个节点」与「需求处在哪个节点」会指向两个名字。
 * 返回 true 表示发生过迁移。
 */
export function migrateArtifactStageNames(req: { artifacts?: Array<{ stage?: string }> }): boolean {
  let changed = false
  for (const a of req.artifacts ?? []) {
    const mapped = a.stage === undefined ? undefined : LEGACY_REQ_STATUS_ALIASES[a.stage]
    if (mapped !== undefined) { a.stage = mapped; changed = true }
  }
  return changed
}

/** 任务时间线回填（已有事件 → 返回 undefined 不动）。 */
export function backfillTaskHistory(task: LegacyBackfillRecord): LegacyStatusEvent[] | undefined {
  return backfill(task, 'todo', ALL_TASK_STATUS_NAMES, task.statusHistory)
}
