/**
 * Dive 回合驱动器的**纯数据契约与判定**（REQ-260926215013-1568 T-1 · serves: FR-1, FR-5, FR-7, FR-8, FR-10）。
 *
 * 为什么单独一个模块：这五条纪律（竞态栅栏 / 准入计数 / 终态上限 / 内容不变量 / 检查点前置）
 * 的判定必须能被独立单测，且 **application 层禁 @deepseek-ai/* 运行时 import**（层边界门禁）。
 * 本模块零 I/O、零框架依赖，只做「给定状态 → 布尔/数值」的纯计算。
 *
 * @module dsh-pmboard/application/dive/round-state
 */
import type { DiveRoundSource, RequirementRecord, RequirementStatus } from '../../shared/protocol.js'
import { isDiveRoundSource } from '../../shared/protocol.js'
import { getStageConfig } from './stage-configs.js'

/** 预留的相位：queued（已入队）→ claimed（已被 step 认领）→ admitted（已进入 history）。单向。 */
export type RoundPhase = 'queued' | 'claimed' | 'admitted'

/** 一次回合预留（对齐 dsh-goal-round-driver 的 attempt）。 */
export interface RoundAttempt {
  requirementId: string
  /** 预留时的需求 revision */
  revision: number
  /** 预留的回合号 = 预留时 roundsInStage + 1 */
  round: number
  /** 消息身份（user/message 事件据此认领） */
  messageId: string
  /** 模型可见内容（逐字比对，防旧/伪造消息混入） */
  content: unknown
  phase: RoundPhase
  /** 被 discard / aborted / cancel → 永不计数 */
  cancelled: boolean
  /** revision 失效 / 竞争让位 → 永不计数 */
  stale: boolean
}

/** 每 agent 一个驱动状态（进程内存态，不落盘）。 */
export interface DriverState {
  /** 精确活体句柄（agents.get(id) === state.agent 才算存活） */
  agent: unknown
  /** 至多一个在飞预留 */
  attempt?: RoundAttempt
  /** 有非本回合的入队输入 → 让位到下次空闲 */
  competingQueued: boolean
  /** 有耐久义务待兑现（排队前必须落盘） */
  needsCheckpoint: boolean
  /** 合并触发标志 */
  requested: boolean
  /** 串行驱动链（withoutInitiator） */
  run?: Promise<void>
  /** teardown 已关闭准入 */
  stopping: boolean
}

/** 逐字（结构）相等：只吃 JSON 值（消息 content 是 JSON）。 */
export function deepEqualJson(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (typeof a !== 'object' || typeof b !== 'object' || a === null || b === null) return false
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false
    return a.every((v, i) => deepEqualJson(v, b[i]))
  }
  const ao = a as Record<string, unknown>
  const bo = b as Record<string, unknown>
  const ka = Object.keys(ao)
  const kb = Object.keys(bo)
  if (ka.length !== kb.length) return false
  return ka.every(k => Object.prototype.hasOwnProperty.call(bo, k) && deepEqualJson(ao[k], bo[k]))
}

/** 来源逐字段相等（requirementId / revision / round）。 */
export function sameRound(source: DiveRoundSource, attempt: RoundAttempt): boolean {
  return source.requirementId === attempt.requirementId
    && source.revision === attempt.revision
    && source.round === attempt.round
}

/**
 * 是否为本驱动器登记的回合消息（**仅此判据认领**）：
 * source 是合法 Dive 来源、字段与预留一致、内容与登记逐字一致。
 */
export function sameQueued(content: unknown, source: unknown, attempt: RoundAttempt): boolean {
  if (!isDiveRoundSource(source)) return false
  if (!sameRound(source, attempt)) return false
  return deepEqualJson(content, attempt.content)
}

/** 进入 step 前/后的完整栅栏（fail-closed）。任何一条不成立即不得放行。 */
export interface ReservationCheck {
  state: DriverState
  content: unknown
  source: DiveRoundSource
  req: RequirementRecord | undefined
  /** 驱动所在插件 fiber 是否 active（对齐 Goal 的 ctx.fiber.state === 2） */
  fiberActive: boolean
  /** agents.get(req.sourceSessionId) === state.agent（精确活体） */
  agentLive: boolean
}

export function roundReservationValid(c: ReservationCheck): boolean {
  const { state, content, source, req } = c
  const a = state.attempt
  if (!c.fiberActive) return false
  if (state.stopping) return false
  if (!c.agentLive) return false
  if (a === undefined) return false
  if (a.phase !== 'claimed' || a.stale || a.cancelled) return false
  if (!sameQueued(content, source, a)) return false
  if (req === undefined) return false
  if (req.id !== source.requirementId || req.version !== source.revision) return false
  const dive = req.dive
  if (dive === undefined) return false
  if (dive.activation !== 'armed' || dive.phase !== 'active') return false
  return source.round === (dive.roundsInStage ?? 0) + 1
}

/** 回合上限（权威来源 = stage-configs 的每阶段 maxRounds；未知阶段回落 10）。 */
export function roundLimitFor(status: RequirementStatus | string): number {
  return getStageConfig(status as RequirementStatus)?.maxRounds ?? 10
}

/** 回合消息正文（纯函数，供端口注入与测试固定；内容不变量据此逐字比对）。 */
export function renderDiveRoundText(input: { requirementId: string; round: number; status: string }): string {
  return '继续执行需求 ' + input.requirementId + '（Dive 模式自动续跑，第 ' + input.round + ' 回合）\n\n当前状态：' + input.status
}

/** 是否「可起轮」的需求（armed + active）。 */
export function isDrivableRequirement(req: RequirementRecord | undefined): boolean {
  return req !== undefined && req.dive?.activation === 'armed' && req.dive?.phase === 'active'
}

// ── 宿主对象的结构访问器（零框架依赖；防 application 反向 import adapters/框架） ──

export interface InboxLike {
  nextStep?: { id?: unknown }[]
  nextTurn?: { id?: unknown }[]
  prepend?: (target: string, message: unknown) => void
}

export function agentIdOf(agent: unknown): string | undefined {
  if (typeof agent !== 'object' || agent === null) return undefined
  const a = agent as { id?: unknown; session?: { id?: unknown } }
  if (typeof a.id === 'string' && a.id.length > 0) return a.id
  const sid = a.session?.id
  return typeof sid === 'string' && sid.length > 0 ? sid : undefined
}
export function agentStatusOf(agent: unknown): string | undefined {
  return typeof agent === 'object' && agent !== null ? (agent as { status?: string }).status : undefined
}
export function inboxOf(agent: unknown): InboxLike | undefined {
  return typeof agent === 'object' && agent !== null ? (agent as { inbox?: InboxLike }).inbox : undefined
}
export function messageIdOf(m: unknown): string | undefined {
  const id = (m as { id?: unknown } | undefined)?.id
  return typeof id === 'string' ? id : undefined
}
export function sourceOf(m: unknown): unknown { return (m as { source?: unknown } | undefined)?.source }
export function contentOf(m: unknown): unknown { return (m as { content?: unknown } | undefined)?.content }

