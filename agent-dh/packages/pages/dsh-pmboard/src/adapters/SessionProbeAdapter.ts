/**
 * 会话探测适配器（REQ-47939a t5 / ports.ts SessionProbe）——窗口身份 / 调用方权限 /
 * 工具痕迹 / 近期用户消息的唯一 I/O 入口。
 *
 * 从 host/capture-hook.ts 搬入会话痕迹的**纯缓冲逻辑**（tool/call 痕迹、近期用户消息
 * 缓冲及其判定），从 host/agent-tools.ts 搬入调用方认证（live driver / direct human）
 * 的判定文本——两处曾是"会话 I/O"与"工具壳认证"的耦合点，适配层是它们的正确归属。
 * host/capture-hook.ts 继续再导出这些符号，既有 import 路径（含 capture-hook.test）不变。
 *
 * 端口方法 requireLiveDriver / requireDirectHuman 保留搬迁前的错误码与消息（REQBOARD_*），
 * 以便 t8 切换调用方时行为逐字不变（端口文档里的 caller_not_live 是目标语义，映射在 t8）。
 *
 * @module dsh-pmboard/adapters/SessionProbeAdapter
 */
import type { SessionProbe } from '../application/ports.js'
import { emptyBuckets, type TokenBuckets, type TokenSnapshot } from '../shared/protocol.js'

// ---------------------------------------------------------------------------
// 工具痕迹（REQ-2e9473 t05）：窗口维度记录 tool/call 事件，供 done 凭证门判定"开工以来有无真实工具动作"。
// ---------------------------------------------------------------------------

export interface ToolTraceEntry {
  at: number
  /** 会话事件层的工具名（注意：PTC 模式下内部调用一律呈现为 run_code——弱信号，t06 的强信号是文件证据） */
  name: string
}

/** 每窗口痕迹上限（环形截断，防内存膨胀）。 */
export const TOOL_TRACE_CAP = 500

/** 记录一条工具调用痕迹（环形截断）。 */
export function recordToolTrace(trace: Map<string, ToolTraceEntry[]>, windowKey: string, name: string, at: number): void {
  const list = trace.get(windowKey) ?? []
  list.push({ at, name })
  if (list.length > TOOL_TRACE_CAP) list.splice(0, list.length - TOOL_TRACE_CAP)
  trace.set(windowKey, list)
}

/** 统计窗口在某时点之后的工具活动（done 凭证门用：since = 任务 claimedAt）。 */
export function toolActivitySince(
  trace: Map<string, ToolTraceEntry[]>,
  windowKey: string,
  since: number,
): { total: number; byTool: Record<string, number>; workLike: number } {
  const list = (trace.get(windowKey) ?? []).filter(e => e.at >= since)
  const byTool: Record<string, number> = {}
  let workLike = 0
  for (const e of list) {
    byTool[e.name] = (byTool[e.name] ?? 0) + 1
    // 干活类工具：文件改动/命令执行/代码执行（reqboard_* 台账动作不算干活证据）
    if (['edit', 'write', 'bash', 'pwsh', 'run_code'].includes(e.name)) workLike += 1
  }
  return { total: list.length, byTool, workLike }
}

// ---------------------------------------------------------------------------
// 近期用户消息缓冲（REQ-2e9473 t10）：文字确认核验用。
// ---------------------------------------------------------------------------

/** 文字确认核验缓冲：窗口 → 最近真实用户消息（清洗后文本），evidence 必须命中其中一条。 */
export interface RecentUserMsg { text: string; at: number }

/** 缓冲上限与有效窗口。 */
export const RECENT_USER_MSG_CAP = 20
export const CONFIRM_EVIDENCE_WINDOW_MS = 60 * 60 * 1000

/** 记录一条真实用户消息（环形截断）。 */
export function recordRecentUserMsg(buf: Map<string, RecentUserMsg[]>, windowKey: string, text: string, at: number): void {
  const t = text.replace(/\s+/g, ' ').trim()
  if (t.length === 0) return
  const list = buf.get(windowKey) ?? []
  list.push({ text: t, at })
  if (list.length > RECENT_USER_MSG_CAP) list.splice(0, list.length - RECENT_USER_MSG_CAP)
  buf.set(windowKey, list)
}

/**
 * 核验 evidence 是否引用了一段时间内真实存在的用户消息原文（REQ-2e9473 t10 三通道③）。
 * 判定：缓冲内某条消息是 evidence 的子串，或 evidence 是该消息的子串（互为引用），
 * 且消息落在时间窗内。消息过短（<4 字符）不作证（"嗯""好"太易撞库）。
 */
export function evidenceMatchesRecentUserMsg(
  buf: Map<string, RecentUserMsg[]>,
  windowKey: string,
  evidence: string,
  now: number,
): { ok: boolean; matchedText?: string; reason?: string } {
  const ev = evidence.replace(/\s+/g, ' ').trim()
  const list = (buf.get(windowKey) ?? []).filter(m => now - m.at <= CONFIRM_EVIDENCE_WINDOW_MS)
  if (list.length === 0) return { ok: false, reason: '时间窗内没有该窗口的真实用户消息记录' }
  for (const m of list) {
    if (m.text.length >= 4 && (ev.includes(m.text) || m.text.includes(ev))) {
      return { ok: true, matchedText: m.text }
    }
  }
  return { ok: false, reason: 'evidence 未引用时间窗内任何真实用户消息原文（可能是编造或曲解）' }
}

// ---------------------------------------------------------------------------
// SessionProbe 适配器（端口实现）
// ---------------------------------------------------------------------------

/** 结构化认证失败：message 自带（CODE）文本；code 属性仅测试/直接执行消费。 */
function rejectSession(message: string, code: string): never {
  throw Object.assign(new Error(`${message}（${code}）`), { code })
}

export interface SessionProbeAdapterOptions {
  /** 工具痕迹表（done 凭证门）。 */
  toolTrace?: Map<string, ToolTraceEntry[]>
  /** 最近用户消息缓冲（文字确认核验）。 */
  recentUserMsgs?: Map<string, RecentUserMsg[]>
  /** 当前 agents 服务（unavailable → undefined）；live-driver 校验用。 */
  agents?: () => unknown
  /** 当前 sessionProjections 服务（unavailable → undefined）；direct-human 校验用。 */
  sessionProjections?: () => unknown
  /** 时间源（matchesRecentUserMessage 的时间窗起点）；默认 Date.now。 */
  now?: () => number
}

export class SessionProbeAdapter implements SessionProbe {
  private readonly opts: SessionProbeAdapterOptions

  constructor(options: SessionProbeAdapterOptions = {}) {
    this.opts = options
  }

  /** 工具痕迹表（供 hook 写入 / 凭证门读取）。 */
  toolTrace(): Map<string, ToolTraceEntry[]> | undefined {
    return this.opts.toolTrace
  }

  /** 窗口码：执行器 agent 的 id（缺失/非字符串 → 抛 REQBOARD_AGENT_REQUIRED）。 */
  windowKey(exec: unknown): string {
    const raw = ((exec as { agent?: { id?: unknown } } | undefined)?.agent)?.id
    if (typeof raw !== 'string' || raw.length === 0) {
      rejectSession('reqboard 工具需要由执行窗口的 agent 调用（缺 exec.agent）', 'REQBOARD_AGENT_REQUIRED')
    }
    return raw
  }

  /**
   * 尽力而为的 live-driver 认证（从 agent-tools 搬入）：agents 服务可得时要求调用者就是
   * 注册表中正在运行且当前发起回合的同一 agent；服务不可得（测试/降级环境）只做 identity。
   */
  requireLiveDriver(exec: unknown): void {
    const svc = this.opts.agents?.()
    if (svc === undefined) return
    const agents = svc as { get?: (id: string) => unknown; currentInitiator?: () => unknown }
    if (typeof agents.get !== 'function' || typeof agents.currentInitiator !== 'function') return
    const agent = (exec as { agent?: unknown } | undefined)?.agent
    if (agent === undefined) {
      rejectSession('reqboard 工具需要由执行窗口的 agent 调用（缺 exec.agent）', 'REQBOARD_AGENT_REQUIRED')
    }
    const id = (agent as { id: string }).id
    const live =
      agents.get(id) === agent &&
      (agent as { status?: string }).status === 'running' &&
      agents.currentInitiator() === agent
    if (!live) {
      rejectSession('reqboard_create 需要确切的在线调用 agent 且在其 live driver 回合内', 'REQBOARD_DRIVER_REQUIRED')
    }
  }

  /**
   * 直接人工回合认证（从 agent-tools 搬入）：agents + sessionProjections 服务都可得时，
   * 要求本 agent 是 root 且当前 open turn 含 source.kind==='user' 的用户消息；任一服务
   * 不可得 → 降级放行（无法证伪即放行）。
   */
  requireDirectHuman(exec: unknown): void {
    const svc = this.opts.agents?.()
    const projSvc = this.opts.sessionProjections?.()
    if (svc === undefined || projSvc === undefined) return
    const agents = svc as { roots?: () => unknown[] }
    const projections = projSvc as {
      stateOf?: (session: unknown, kind: string) => { openTurnStartSeq: number | null } | undefined
    }
    if (typeof agents.roots !== 'function' || typeof projections.stateOf !== 'function') return
    const agent = (exec as { agent?: unknown } | undefined)?.agent
    if (agent === undefined) {
      rejectSession('reqboard 工具需要由执行窗口的 agent 调用（缺 exec.agent）', 'REQBOARD_AGENT_REQUIRED')
    }
    if (!agents.roots().includes(agent)) {
      rejectSession('reqboard_create 需要顶层 agent 窗口的直接人工回合', 'REQBOARD_DIRECT_HUMAN_REQUIRED')
    }
    const session = (agent as { session?: unknown }).session
    const boundary = projections.stateOf(session, 'turnBoundary')
    if (boundary === undefined || boundary.openTurnStartSeq === null) {
      rejectSession('reqboard_create 需要 open 的模型回合（turnBoundary 不可得）', 'REQBOARD_DRIVER_REQUIRED')
    }
    const events = (agent as { session?: { snapshotEvents?: () => unknown[] } }).session?.snapshotEvents?.() ?? []
    for (let seq = boundary.openTurnStartSeq + 1; seq < events.length; seq += 1) {
      const event = events[seq] as { type?: string; data?: { source?: { kind?: string } } } | undefined
      if (event !== undefined && event.type === 'user/message' && event.data?.source?.kind === 'user') return
    }
    rejectSession('reqboard_create 需要本次直接人工回合的用户消息（自主回合禁止立项）', 'REQBOARD_DIRECT_HUMAN_REQUIRED')
  }

  /**
   * 执行会话的累计 token 快照（REQ-a33899 t2）。读 sessionProjections 的 tokenUsage 投影；
   * 任一环节不可得（服务未装配 / 窗口无会话 / 投影未产出）→ source='unavailable' 空桶，**不抛错**。
   */
  tokenTotals(windowKey: string): TokenSnapshot {
    const now = this.opts.now?.() ?? Date.now()
    const unavailable = (): TokenSnapshot => ({ at: now, totals: emptyBuckets(), source: 'unavailable' })
    const agents = this.opts.agents?.() as { get?: (id: string) => unknown } | undefined
    const projections = this.opts.sessionProjections?.() as
      { stateOf?: (session: unknown, kind: string) => unknown } | undefined
    if (typeof agents?.get !== 'function' || typeof projections?.stateOf !== 'function') return unavailable()
    let session: unknown
    try {
      session = (agents.get(windowKey) as { session?: unknown } | undefined)?.session
    } catch {
      return unavailable()
    }
    if (session === undefined || session === null) return unavailable()
    let state: unknown
    try {
      state = projections.stateOf(session, 'tokenUsage')
    } catch {
      return unavailable()
    }
    const totals = readTokenTotals(state)
    if (totals === undefined) return unavailable()
    const sessionId = readSessionId(session)
    const seq = readSessionSeq(session)
    return {
      ...(sessionId !== undefined ? { sessionId } : {}),
      ...(seq !== undefined ? { seq } : {}),
      at: now,
      totals,
      source: 'projection',
    }
  }

  /** 某窗口"自 since 以来最后一次真实工具动作"的 workLike 计数；无痕迹表 → 0。 */
  toolActivitySince(windowKey: string, since: number): number {
    if (this.opts.toolTrace === undefined) return 0
    return toolActivitySince(this.opts.toolTrace, windowKey, since).workLike
  }

  /**
   * evidence 原文是否命中该窗口近期（withinMs 内）的真实用户消息。
   * 缓冲未注入 → undefined（核验通道不可用，调用方放行并标注"核验未启用"）；
   * 否则返回 {ok, reason}（REQ-47939a t6：保留搬迁前的失败原因文案）。
   */
  matchesRecentUserMessage(
    windowKey: string,
    evidence: string,
    withinMs: number,
  ): { ok: boolean; matchedText?: string; reason?: string } | undefined {
    void withinMs
    if (this.opts.recentUserMsgs === undefined) return undefined
    const now = this.opts.now?.() ?? Date.now()
    return evidenceMatchesRecentUserMsg(this.opts.recentUserMsgs, windowKey, evidence, now)
  }
}

// ---------------------------------------------------------------------------
// tokenUsage 投影解析（REQ-a33899 t2）——兼容两种状态形状：{totals:{...}} 包裹 或 直接四桶
// ---------------------------------------------------------------------------

function readBucketNumber(raw: unknown, key: string): number | undefined {
  const v = (typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>)[key] : undefined)
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined
}

/** 从投影状态读四桶；缺任一桶/形状不符 → undefined（视为不可得，不猜 0）。 */
export function readTokenTotals(state: unknown): TokenBuckets | undefined {
  if (typeof state !== 'object' || state === null) return undefined
  const wrapped = (state as { totals?: unknown }).totals
  const src = (typeof wrapped === 'object' && wrapped !== null) ? wrapped : state
  const a = readBucketNumber(src, 'uncachedInputTokens')
  const o = readBucketNumber(src, 'outputTokens')
  const r = readBucketNumber(src, 'cacheReadTokens')
  const w = readBucketNumber(src, 'cacheWriteTokens')
  if (a === undefined || o === undefined || r === undefined || w === undefined) return undefined
  return { uncachedInputTokens: a, outputTokens: o, cacheReadTokens: r, cacheWriteTokens: w }
}

/** 会话 id（缺省 → undefined）。 */
function readSessionId(session: unknown): string | undefined {
  const id = (session as { id?: unknown } | undefined)?.id
  return typeof id === 'string' && id.length > 0 ? id : undefined
}

/** 会话日志序号（snapshotEvents 末条下标；不可得 → undefined）。 */
function readSessionSeq(session: unknown): number | undefined {
  const events = (session as { snapshotEvents?: () => unknown } | undefined)?.snapshotEvents
  if (typeof events !== 'function') return undefined
  try {
    const list = events.call(session) as unknown
    return Array.isArray(list) && list.length > 0 ? list.length - 1 : undefined
  } catch {
    return undefined
  }
}

