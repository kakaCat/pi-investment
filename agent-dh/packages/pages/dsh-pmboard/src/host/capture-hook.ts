/**
 * reqboard 确定性消息捕获 hook —— 用户裁定 · 创建即立项落地的消息事件钩子。
 *
 * 裁定（用户三连，本模块即其可执行化）：
 *   1. 用户消息到达 unbound 窗口就应触发立项评估；
 *   2. 用户消息到达 → hook 检查该窗口是否需要立项捕获（需要 = 窗口 unbound 且无
 *      遗留 pending 建议卡；旧 pending 建议卡仅旧流程 triage 会残留，新流程不再产生）；
 *   3. hook 检查「需要」后注入提示词，让 LLM 弹「两问确认」弹框（ask_user_question：
 *      需求名称 + 需求类型）——**用户作答即立项确认**——随后调 reqboard_create
 *      直接建 REQ（创建即立项，无待归类/建议卡中间态）。
 *
 * 职责边界（与 legacy SessionSyncService 的本质区别）：
 *  - legacy（禁例，已不再装配）：turn/start 无条件建空 triage + 每条 user/message
 *    走 LLM 自动分类并自动立项，曾产出 228 条 [LLM 分类] 垃圾评论——自动立项
 *    违反模式 B（人工 gate 前置）且无 direct-human source 过滤；
 *  - 本 hook：不建空卡、不自动立项、不写评论。它只做**确定性触发 + 窗口条件
 *    判定**：把「需要走立项评估的用户消息」登记为待捕获候选（内存 Map，不进
 *    台账），capture section 在下一 LLM 回合组装时读到并注入针对性立项提示。
 *    立项动作由 LLM 经两问弹框确认后调 reqboard_create 直接完成（弹框作答 =
 *    人工 gate）。
 *
 * 判定链（全确定性，语义判断——值不值得立项——留给 LLM）：
 *   1. 事件类型 = user/message（用户输入到达 = 确定性触发点）；
 *   2. 会话非忽略（isIgnoredSession：subagent/child/session-reqboard-* /
 *      parentSession / delegationDepth > 0）；
 *   3. direct human：event.data.source?.kind === 'user'（agent.inject 文件通知/
 *      skill/cron 与 goal 续跑为 plugin 等其他 kind → 排除；source 缺失时退化
 *      放行，靠文本清洗兜底——source 显式为非 user kind 则跳过）；
 *   4. cleanUserMessageText 清洗后非空（剔除 checkpoint / runtime context 等
 *      系统注入块——纯系统块不触发立项评估）；
 *   5. 台账窗口状态：unbound && 无遗留 pending 建议卡 → 该窗口需要走一次立项捕获。
 * 满足则登记 pendingCapture（同窗口覆盖旧条目：只跟踪最新一条未消费消息）。
 * turn/end 清除该窗口 pendingCapture（该回合 LLM 已消费本次立项评估机会；
 * LLM 若已立项则台账 bound 会令 capture 自动返回 ''，防重复 nag）。
 *
 * @module dsh-pmboard/host/capture-hook
 */

import type { ReqboardLedger, StageKey, StagePromptKey } from '../shared/protocol.js'
import { stageEnabledFor } from '../shared/protocol.js'
import { isIgnoredSession, extractUserMessageText } from './session-sync.js'
import { cleanUserMessageText } from './classifier.js'
import { isWindowBound, hasPendingSuggestion, openRequirementsFor, type PendingCaptureMessage } from './capture.js'
import { STAGE_PROMPTS } from './stage-prompts.js'
// R1 接手推进：hook 只发信号（bound 窗口有人类消息），推进落库由 apply 侧注入的回调做

export interface CaptureHookLogger {
  /** 成员必填；logger 整体可选（deps.logger?:）→ logger?.info(...) 即安全。 */
  info(message: string): void
  debug(message: string): void
}

/** 工具痕迹条目（REQ-2e9473 t05）：窗口维度记录 tool/call 事件，供 done 凭证门判定"开工以来有无真实工具动作"。 */
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

export interface CaptureHookDeps {
  /** 台账快照（同步读取；判定窗口 unbound / pending 状态）。 */
  snapshot: () => ReqboardLedger
  /** 待捕获候选共享 Map（windowKey → 最新未消费消息；capture section 同引用读取）。 */
  pending: Map<string, PendingCaptureMessage>
  now: () => number
  /**
   * 接手推进回调（R1）：**已绑定**窗口出现直接人类消息 = 该窗口在继续推进其需求 →
   * 调用方把它绑定的 draft 需求推进到 brainstorming。可选（未注入 = 关闭该自动推进）。
   */
  onBoundWindowActivity?: (windowKey: string, text: string) => void
  /**
   * 阶段提示词注入回调（REQ-31e11f t5）：需求状态转移后，向绑定会话注入新阶段的
   * STAGE_PROMPTS 纪律提示词。可选（未注入 = 关闭该注入）。
   */
  onStagePrompt?: (windowKey: string, prompt: string) => void
  /** 工具痕迹表（REQ-2e9473 t05）：hook 写入，done 凭证门（t06）读取。可选（未注入 = 关闭跟踪）。 */
  toolTrace?: Map<string, ToolTraceEntry[]>
  /** 最近用户消息缓冲（REQ-2e9473 t10）：hook 写入，confirm_artifact 文字确认核验读取。可选。 */
  recentUserMsgs?: Map<string, RecentUserMsg[]>
  logger?: CaptureHookLogger
}

/** 文字确认核验缓冲（REQ-2e9473 t10）：窗口 → 最近真实用户消息（清洗后文本），confirm_artifact 的 evidence 必须命中其中一条。 */
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

/** 里程碑提醒阈值（REQ-2e9473 t09/W1.5）：产物登记超过此时长未确认 → 主动提醒弹框。 */
export const MILESTONE_REMINDER_MS = 30 * 60 * 1000

/**
 * 里程碑超时提醒（REQ-2e9473 t09，解决"agent 不主动弹框"）：
 * 绑定窗口的最新 open 需求存在"当前阶段已登记但超时未确认"的产物 → 返回提醒文本。
 * 每产物只提醒一次由调用方（hook 闭包里的 remindedAt Map）保证。
 */
export function milestoneReminderFor(
  ledger: ReqboardLedger,
  windowKey: string,
  now: number,
): { text: string; artifactKey: string } | undefined {
  const open = openRequirementsFor(ledger, windowKey)
  const req = [...open].sort((a, b) => b.updatedAt - a.updatedAt)[0]
  if (req === undefined) return undefined
  const stale = (req.artifacts ?? []).find(a =>
    a.stage === req.status
    && a.confirmedAt === undefined
    && now - a.registeredAt > MILESTONE_REMINDER_MS,
  )
  if (stale === undefined) return undefined
  const minutes = Math.round((now - stale.registeredAt) / 60000)
  return {
    artifactKey: req.id + ':' + stale.kind,
    text: '【里程碑提醒】产物 kind=' + stale.kind + '（' + stale.path + '）已登记 ' + minutes + ' 分钟未确认。'
      + '请立即调 reqboard_ask_confirm（target=artifact, kind=' + stale.kind + '）弹框请人确认——'
      + '用户点肯定项即自动落章并推进节点；或提示用户在看板点「确认产物」。',
  }
}

/** 该窗口是否「需要走一次立项捕获」：unbound 且无遗留 pending 建议卡（旧流程 triage 产物）。 */
export function shouldCaptureWindow(ledger: ReqboardLedger, windowKey: string): boolean {
  return !isWindowBound(ledger, windowKey) && !hasPendingSuggestion(ledger, windowKey)
}

/** 从 user/message 事件 data 提取 source.kind（缺失 → undefined）。 */
function eventSourceKind(data: unknown): unknown {
  if (typeof data !== 'object' || data === null) return undefined
  const source = (data as { source?: unknown }).source
  if (typeof source !== 'object' || source === null) return undefined
  return (source as { kind?: unknown }).kind
}

/**
 * 创建 session/event 事件处理器（订阅 'session/event'，回调签名 (session, event)，
 * 与 legacy SessionSyncService 同形状）。返回 (session, event) => void。
 * 纯同步、无异步 IO；幂等（重复触发同消息只保留最新登记）。
 */
export function createSessionEventCaptureHook(deps: CaptureHookDeps): (session: unknown, event: unknown) => void {
  const { snapshot, pending, now, logger } = deps
  const debug = (m: string) => logger?.debug?.(m)

  // 里程碑提醒去重（t09）：每产物只提醒一次（确认后 stage/confirmedAt 变化自然失效）。
  const remindedAt = new Map<string, number>()

  return (session: unknown, event: unknown): void => {
    const sessionObj = (typeof session === 'object' && session !== null ? session : {}) as { id?: unknown }
    const windowKey = typeof sessionObj.id === 'string' && sessionObj.id.length > 0 ? sessionObj.id : ''
    if (!windowKey) return

    const evt = (typeof event === 'object' && event !== null ? event : {}) as { type?: unknown; data?: unknown }
    const type = typeof evt.type === 'string' ? evt.type : ''

    // 工具痕迹（REQ-2e9473 t05）：tool/call 事件按窗口落痕，done 凭证门据此判定
    // "开工以来有无真实工具动作"。忽略会话（subagent 等）不记——各算各账。
    if (type === 'tool/call') {
      if (deps.toolTrace !== undefined && !isIgnoredSession(windowKey, session)) {
        const data = (typeof evt.data === 'object' && evt.data !== null ? evt.data : {}) as { name?: unknown }
        recordToolTrace(deps.toolTrace, windowKey, typeof data.name === 'string' ? data.name : '?', now())
      }
      return
    }

    // 回合结束 → 消费完毕，清除待捕获候选（防跨回合/跨 step 重复 nag）。
    if (type === 'turn/end') {
      if (pending.delete(windowKey)) {
        debug(`reqboard-capture: turn/end clears pending capture for ${windowKey.slice(0, 16)}`)
      }
      return
    }

    // 触发点：仅 user/message（用户输入到达）。
    if (type !== 'user/message') return

    // 忽略会话（子代理/内部会话/父会话派生子会话）。
    if (isIgnoredSession(windowKey, session)) {
      debug(`reqboard-capture: ignored session ${windowKey.slice(0, 16)}`)
      return
    }

    // direct human：source.kind === 'user'；source 缺失 → 退化放行（文本清洗兜底）。
    const sourceKind = eventSourceKind(evt.data)
    if (sourceKind !== undefined && sourceKind !== 'user') {
      debug(`reqboard-capture: non-direct-human source kind=${String(sourceKind)} skipped (${windowKey.slice(0, 16)})`)
      return
    }

    // 清洗：剔除 checkpoint / runtime context / system-reminder 等系统注入块。
    const raw = extractUserMessageText(evt.data)
    const text = cleanUserMessageText(raw)
    if (text.trim().length === 0) {
      debug(`reqboard-capture: noise-only message skipped (${windowKey.slice(0, 16)})`)
      return
    }

    // 文字确认核验缓冲（REQ-2e9473 t10）：记录清洗后的真实用户消息原文，
    // confirm_artifact 的 evidence 必须命中缓冲内消息（防 agent 编造"用户同意了"）。
    if (deps.recentUserMsgs !== undefined) {
      recordRecentUserMsg(deps.recentUserMsgs, windowKey, text, now())
    }

    // 窗口条件：unbound && 无遗留 pending → 需要立项捕获（确定性判定，语义判断留给 LLM）。
    if (!shouldCaptureWindow(snapshot(), windowKey)) {
      debug(`reqboard-capture: window ${windowKey.slice(0, 16)} bound or has pending — no capture needed`)
      // 已绑定窗口 + 直接人类消息 = 该窗口仍在实际推进其需求 → 通知接手推进（R1）
      const ledger = snapshot()
      if (isWindowBound(ledger, windowKey)) {
        deps.onBoundWindowActivity?.(windowKey, text)
        // REQ-31e11f t5：状态转移后向绑定会话注入新阶段纪律提示词。
        // 取该窗口最近更新的 open 需求，若其当前阶段有对应提示词且分类档案未跳过，
        // 则注入。systemPrompt 组装处（capture.ts boundSectionText）已按当前阶段注入，
        // 此处覆盖「转移发生在回合中途、下一回合才组装 systemPrompt」的时序——
        // 确保转移后绑定会话下一回合收到对应阶段提示词。
        const open = openRequirementsFor(ledger, windowKey)
        const stageReq = [...open].sort((a, b) => b.updatedAt - a.updatedAt)[0]
        if (stageReq !== undefined) {
          const stage = stageReq.status as StagePromptKey
          if (stageEnabledFor(stageReq.category, stage as StageKey)) {
            const prompt = STAGE_PROMPTS[stage]
            if (prompt !== undefined && prompt.length > 0) {
              deps.onStagePrompt?.(windowKey, prompt)
            }
          }
        }
        // 里程碑超时提醒（REQ-2e9473 t09）：产物登记超时未确认 → 主动提醒弹框确认，
        // 每产物只提醒一次（解决"agent 不主动弹框"——从软纪律升级为到时触发）。
        const reminder = milestoneReminderFor(ledger, windowKey, now())
        if (reminder !== undefined && !remindedAt.has(reminder.artifactKey)) {
          remindedAt.set(reminder.artifactKey, now())
          deps.onStagePrompt?.(windowKey, reminder.text)
          debug('reqboard-capture: milestone reminder injected → ' + reminder.artifactKey)
        }
      }
      return
    }

    const replaced = pending.has(windowKey)
    pending.set(windowKey, { windowKey, text, capturedAt: now() })
    logger?.info(
      `reqboard-capture: window ${windowKey.slice(0, 16)} 用户消息到达且需立项评估 → 登记待捕获（len=${text.length}${replaced ? ', 覆盖旧条目' : ''}）`,
    )
  }
}
