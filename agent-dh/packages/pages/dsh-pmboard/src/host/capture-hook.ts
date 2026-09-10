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

import type { ReqboardLedger } from '../shared/protocol.js'
import { isIgnoredSession, extractUserMessageText } from './session-sync.js'
import { cleanUserMessageText } from './classifier.js'
import { isWindowBound, hasPendingSuggestion, type PendingCaptureMessage } from './capture.js'
// R1 接手推进：hook 只发信号（bound 窗口有人类消息），推进落库由 apply 侧注入的回调做

export interface CaptureHookLogger {
  /** 成员必填；logger 整体可选（deps.logger?:）→ logger?.info(...) 即安全。 */
  info(message: string): void
  debug(message: string): void
}

export interface CaptureHookDeps {
  /** 台账快照（同步读取；判定窗口 unbound / pending 状态）。 */
  snapshot: () => ReqboardLedger
  /** 待捕获候选共享 Map（windowKey → 最新未消费消息；capture section 同引用读取）。 */
  pending: Map<string, PendingCaptureMessage>
  now: () => number
  /**
   * 接手推进回调（R1）：**已绑定**窗口出现直接人类消息 = 该窗口在继续推进其需求 →
   * 调用方把它绑定的 draft 需求推进到 reviewing。可选（未注入 = 关闭该自动推进）。
   */
  onBoundWindowActivity?: (windowKey: string, text: string) => void
  logger?: CaptureHookLogger
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

  return (session: unknown, event: unknown): void => {
    const sessionObj = (typeof session === 'object' && session !== null ? session : {}) as { id?: unknown }
    const windowKey = typeof sessionObj.id === 'string' && sessionObj.id.length > 0 ? sessionObj.id : ''
    if (!windowKey) return

    const evt = (typeof event === 'object' && event !== null ? event : {}) as { type?: unknown; data?: unknown }
    const type = typeof evt.type === 'string' ? evt.type : ''

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

    // 窗口条件：unbound && 无遗留 pending → 需要立项捕获（确定性判定，语义判断留给 LLM）。
    if (!shouldCaptureWindow(snapshot(), windowKey)) {
      debug(`reqboard-capture: window ${windowKey.slice(0, 16)} bound or has pending — no capture needed`)
      // 已绑定窗口 + 直接人类消息 = 该窗口仍在实际推进其需求 → 通知接手推进（R1）
      const ledger = snapshot()
      if (isWindowBound(ledger, windowKey)) deps.onBoundWindowActivity?.(windowKey, text)
      return
    }

    const replaced = pending.has(windowKey)
    pending.set(windowKey, { windowKey, text, capturedAt: now() })
    logger?.info(
      `reqboard-capture: window ${windowKey.slice(0, 16)} 用户消息到达且需立项评估 → 登记待捕获（len=${text.length}${replaced ? ', 覆盖旧条目' : ''}）`,
    )
  }
}
