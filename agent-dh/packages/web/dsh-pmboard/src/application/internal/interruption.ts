/**
 * 断点常驻逻辑（REQ-260924213231-b1c4 T-9 · serves: FR-6 / I-8）——纯逻辑，零 I/O。
 *
 * 为什么要有它：回合被上游超时掐断后，pmboard 已经没有执行机会再记录"停在哪、下一步
 * 该干什么"。故断点必须在死亡**之前**就已存在——交棒用例在 mutate 尾部调
 * `stampCheckpoint`（写入器 A）；`turn/end` 事件只负责把原因补新（写入器 B /
 * `stampInterruption`）。两者都只改内存里的 `RequirementRecord.interruption`，
 * 持久化由调用方的 `repo.mutate` 负责。
 *
 * 分层（tests/layer-boundary.test.ts）：application 层不 import node:/adapters/
 * @deepseek-ai/；不碰时钟与随机数——`now` 一律由调用方传入。
 *
 * @module dsh-pmboard/application/internal/interruption
 */
import type { InterruptionRecord, RequirementRecord } from '../../shared/protocol.js'

/** `turn/end` 的规范化结论。形态不认识 → 调用方不写、不报错（不猜、不误报）。 */
export interface TurnEndOutcome {
  /** 是否异常收尾（aborted / error / interrupted）。 */
  abnormal: boolean
  /** 写进 `interruption.reason` 的原因原文。 */
  reason: string
}

/**
 * 解析宿主 `turn/end` 的 `data`（值域取自 dsh-session 的 `TurnEndReasonMap`）：
 *   · completed / max-tokens / blocked → 非异常（可续，不算中断）；
 *   · aborted   → `aborted:<cause.kind>`；
 *   · error     → `error:<code>:<message>`（**上游流超时落这里**）；
 *   · interrupted → `interrupted`（崩溃孤儿回合）。
 * 形态不认识（缺 data/reason/kind）→ `undefined`（不猜）。
 */
export function turnEndOutcome(data: unknown): TurnEndOutcome | undefined {
  const reason = reasonOf(data)
  if (reason === undefined) return undefined
  switch (reason.kind) {
    case 'completed': return { abnormal: false, reason: 'completed' }
    case 'max-tokens': return { abnormal: false, reason: 'max-tokens' }
    case 'blocked': return { abnormal: false, reason: 'blocked' }
    case 'interrupted': return { abnormal: true, reason: 'interrupted' }
    case 'aborted': {
      const cause = reasonObj(reason, 'reason')
      const causeKind = cause !== undefined && typeof cause.kind === 'string' ? cause.kind : 'unknown'
      return { abnormal: true, reason: 'aborted:' + causeKind }
    }
    case 'error': {
      const error = reasonObj(reason, 'error')
      const code = error !== undefined && typeof error.code === 'string' ? error.code : ''
      const message = error !== undefined && typeof error.message === 'string' ? error.message : ''
      return { abnormal: true, reason: 'error:' + code + ':' + message }
    }
    default: return undefined
  }
}

function reasonOf(data: unknown): Record<string, unknown> | undefined {
  if (typeof data !== 'object' || data === null) return undefined
  return reasonObj(data as Record<string, unknown>, 'reason')
}

function reasonObj(parent: Record<string, unknown>, key: string): Record<string, unknown> | undefined {
  const value = parent[key]
  if (typeof value !== 'object' || value === null) return undefined
  return value as Record<string, unknown>
}

/**
 * 下一步命令的**唯一事实源**（断点 / 输入包共用）：按当前状态 + 产物态给出下一步
 * 该调哪个 reqboard 工具。状态映射见 design/architecture.md 的 FR-6 部件 1。
 */
export function nextActionFor(req: RequirementRecord): string {
  const artifacts = req.artifacts ?? []
  switch (req.status) {
    case 'draft':
      return 'reqboard_move(to=brainstorming)'
    case 'brainstorming': {
      const arts = artifacts.filter(a => a.kind === 'requirement')
      if (arts.length === 0) return 'reqboard_submit(kind=requirement)'
      if (arts.some(a => a.confirmedAt === undefined)) return 'reqboard_ask_confirm(target=artifact, kind=requirement)'
      return 'reqboard_move(to=design)'
    }
    case 'design': {
      const arts = artifacts.filter(a => a.kind === 'design')
      if (arts.length === 0) return 'reqboard_submit(kind=design)'
      if (arts.some(a => a.confirmedAt === undefined)) return 'reqboard_ask_confirm(target=artifact, kind=design)'
      return 'reqboard_move(to=decomposing)'
    }
    case 'decomposing':
      if (req.plan === undefined) return 'reqboard_submit(kind=plan)'
      if (req.plan.approvedAt === undefined) return 'reqboard_ask_confirm(target=plan)'
      return 'reqboard_decompose'
    case 'implementing':
      return 'reqboard_task_run'
    case 'accepting':
      return 'reqboard_accept_sheet'
    case 'done':
      return 'reqboard_submit(kind=archive)'
    default:
      // archived / canceled：终态无待办动作（仍返回非空字符串，保持 pendingAction 必填契约）。
      return 'reqboard_status'
  }
}

/**
 * 写入器 A：交棒用例 mutate 尾部调用——`reason="checkpoint"`，stage/pendingAction
 * 取自当前记录。**幂等**：stage 与 pendingAction 都未变时不写、不 bump updatedAt
 * （避免每个工具都制造一次变更）。返回是否落笔。
 */
export function stampCheckpoint(req: RequirementRecord, now: number, tool?: string): boolean {
  const pendingAction = nextActionFor(req)
  const prev = req.interruption
  if (prev !== undefined && prev.reason === 'checkpoint' && prev.stage === req.status && prev.pendingAction === pendingAction) {
    return false
  }
  req.interruption = buildInterruption(req, now, 'checkpoint', pendingAction, tool)
  return true
}

/**
 * 写入器 B / B′：显式补写/覆盖 `reason`（保留由状态重算的 `pendingAction`）。
 * 后写覆盖前写（同一需求只保留一个 interruption 对象，避免两份真相）。
 */
export function stampInterruption(req: RequirementRecord, now: number, reason: string, tool?: string): boolean {
  const pendingAction = nextActionFor(req)
  const prev = req.interruption
  if (prev !== undefined && prev.reason === reason && prev.stage === req.status && prev.pendingAction === pendingAction) {
    return false
  }
  req.interruption = buildInterruption(req, now, reason, pendingAction, tool)
  return true
}

function buildInterruption(
  req: RequirementRecord,
  now: number,
  reason: string,
  pendingAction: string,
  tool: string | undefined,
): InterruptionRecord {
  return {
    at: now,
    reason,
    stage: req.status,
    pendingAction,
    ...(tool === undefined || tool.length === 0 ? {} : { tool }),
  }
}
