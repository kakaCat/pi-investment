/**
 * reqboard 确定性消息捕获 hook —— 用户裁定 · 创建即立项落地的消息事件钩子。
 *
 * 裁定（用户三连，本模块即其可执行化）：
 *   1. 用户消息到达 unbound 窗口就应触发立项评估；
 *   2. 用户消息到达 → hook 检查该窗口是否需要立项捕获（需要 = 窗口 unbound 且无
 *      遗留 pending 建议卡；旧 pending 建议卡仅旧流程 triage 会残留，新流程不再产生）；
 *   3. hook 检查「需要」后注入提示词，让 LLM 调 reqboard_capture（pm 专有立项弹框：
 *      立项三问 = 需求名称 + 需求类型 + 提示词难度）——**用户作答即立项确认**——
 *      工具在同一次调用内建 REQ 并绑定窗口（创建即立项，无待归类/建议卡中间态）。
 *
 * 职责边界（与 legacy SessionSyncService 的本质区别）：
 *  - legacy（禁例，已不再装配）：turn/start 无条件建空 triage + 每条 user/message
 *    走 LLM 自动分类并自动立项，曾产出 228 条 [LLM 分类] 垃圾评论——自动立项
 *    违反模式 B（人工 gate 前置）且无 direct-human source 过滤；
 *  - 本 hook：不建空卡、不自动立项、不写评论。它只做**确定性触发 + 窗口条件
 *    判定**：把「需要走立项评估的用户消息」登记为待捕获候选（内存 Map，不进
 *    台账），capture section 在下一 LLM 回合组装时读到并注入针对性立项提示。
 *    立项动作由 LLM 经 reqboard_capture 的三问弹框确认后在同一次调用内完成（弹框
 *    作答 = 人工 gate）。
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
 * REQ-47939a t9：由 host/capture-hook.ts **逐字搬入** adapters（行为零改动，仅 import 换到新分层）。
 * 会话痕迹/消息缓冲的符号不再从这里再导出——调用方直接 import adapters/SessionProbeAdapter。
 *
 * @module dsh-pmboard/adapters/CaptureHook
 */

import type { ReqboardLedger, StageKey, RequirementRecord } from '../shared/protocol.js'
import { stageEnabledFor } from '../shared/protocol.js'
import { isIgnoredSession, extractUserMessageText, cleanUserMessageText } from './SessionMessageFilter.js'
import {
  isWindowBound,
  openRequirementsFor,
  shouldCaptureWindow,
} from '../application/internal/window.js'
import type { PendingCaptureMessage } from '../application/internal/capture-section.js'
import type { NodeSettlement } from '../application/internal/node-settlement.js'
import { resolveStagePrompt, isPromptStage } from '../domain/prompt/index.js'
import { augmentResolvedPrompt } from '../application/internal/injection-address.js'
import { isInProgressTask } from '../domain/status/Predicates.js'
import {
  injectionLogInputFromResolved,
  type InjectionLogPort,
} from '../application/internal/injection-log.js'
import { findStaleUnconfirmedArtifact } from '../domain/workflow/MilestoneSpec.js'
import { captureDiag } from '../application/internal/diag-log.js'
import {
  recordToolTrace,
  recordRecentUserMsg,
  type RecentUserMsg,
  type ToolTraceEntry,
} from './SessionProbeAdapter.js'
// R1 接手推进：hook 只发信号（bound 窗口有人类消息），推进落库由 apply 侧注入的回调做

export interface CaptureHookLogger {
  /** 成员必填；logger 整体可选（deps.logger?:）→ logger?.info(...) 即安全。 */
  info(message: string): void
  debug(message: string): void
}

// 工具痕迹逻辑（ToolTraceEntry / TOOL_TRACE_CAP / recordToolTrace / toolActivitySince）在
// adapters/SessionProbeAdapter.ts（t5），顶部导入并在下方判定链中直接使用。

/** T-3 地址段增强：开关关/根缺失/渲染异常 → 原样返回（与其它注入点同一纯函数）。 */
function withAddressSection(
  resolved: ReturnType<typeof resolveStagePrompt>,
  deps: CaptureHookDeps,
  ledger: ReqboardLedger,
  requirement: RequirementRecord,
  stage: string,
): ReturnType<typeof resolveStagePrompt> {
  const address = deps.address
  if (address === undefined || address.enabled === false || address.templateRoot === undefined) return resolved
  const currentTask = ledger.tasks.find(t => t.requirementId === requirement.id && isInProgressTask(t))
  try {
    return augmentResolvedPrompt(resolved, {
      stage,
      category: requirement.category,
      requirement,
      ...(currentTask === undefined ? {} : { currentTask: { id: currentTask.id, title: currentTask.title, cardDoc: currentTask.cardDoc } }),
      templateRoot: address.templateRoot,
    })
  } catch {
    return resolved
  }
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
  /**
   * 回合结束回调（REQ-e3b6a0 t7）：**闸门后置链 Phase B 的唯一时机**。
   *
   * 为什么必须挂在这里：弹框作答发生在工具调用内（agent 忙），而压缩/唤醒要求轮次边界；
   * 且监听器内不得做会话写操作（D-17）——故本回调只发信号，真正的执行由组合根放到异步边界。
   * 可选（未注入 = 不触发链）。
   */
  onTurnEnd?: (windowKey: string, session: unknown) => void
  /** 工具痕迹表（REQ-2e9473 t05）：hook 写入，done 凭证门（t06）读取。可选（未注入 = 关闭跟踪）。 */
  toolTrace?: Map<string, ToolTraceEntry[]>
  /** 最近用户消息缓冲（REQ-2e9473 t10）：hook 写入，confirm_artifact 文字确认核验读取。可选。 */
  recentUserMsgs?: Map<string, RecentUserMsg[]>
  /** 注入留痕端口（REQ-422af1 t6）：状态转移注入后调用 record。可选（未注入 = 不留痕）。 */
  injectionLog?: InjectionLogPort
  /** 模板地址注入（REQ-260922213356-4a45 T-3）：绝对模板根 + 开关；缺省不注入。 */
  address?: { templateRoot?: string; enabled?: boolean }
  /**
   * 节点结算回调（REQ-422af1 t10）：绑定窗口的**回合结束**（turn/end）且该回合登记过
   * 「可注入节点结算」时发信号，并携带会话句柄（隔离端口由组合根按会话构造）。
   * **本回调不得在事件派发内做会话写操作**（D-17：监听器内同步 append 会被框架拒绝
   * "session append cannot reenter while another append is being published"）——
   * hook 只发信号，真正执行的异步边界在 application/internal/node-settlement.ts。
   * 可选（未注入 = 关闭结算信号）。
   */
  onNodeSettled?: (settle: NodeSettlement, session: unknown) => void
  logger?: CaptureHookLogger
}

// 近期用户消息缓冲（RecentUserMsg / RECENT_USER_MSG_CAP / CONFIRM_EVIDENCE_WINDOW_MS /
// recordRecentUserMsg / evidenceMatchesRecentUserMsg）在 adapters/SessionProbeAdapter.ts（t5），
// 顶部导入并在下方判定链中直接使用。

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
  // 判定（当前阶段已登记但超时未确认）在 domain/workflow/MilestoneSpec.ts（REQ-47939a t3）。
  const stale = findStaleUnconfirmedArtifact(req, now, MILESTONE_REMINDER_MS)
  if (stale === undefined) return undefined
  const minutes = Math.round((now - stale.registeredAt) / 60000)
  return {
    artifactKey: req.id + ':' + stale.kind,
    text: '【里程碑提醒】产物 kind=' + stale.kind + '（' + stale.path + '）已登记 ' + minutes + ' 分钟未确认。'
      + '请立即调 reqboard_ask_confirm（target=artifact, kind=' + stale.kind + '）弹框请人确认——'
      + '用户点肯定项即自动落章并推进节点；或提示用户在看板点「确认产物」。',
  }
}

// shouldCaptureWindow（unbound 且无遗留 pending）已迁 application/internal/window.ts（t9）。

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

  // 节点结算（REQ-422af1 t10）：窗口 → 本回合登记的结算；turn/end（轮次边界）时消费。
  // 去重键 = 窗口:节点——同一节点只结算一次，否则每个回合都会遗弃一次上下文。
  const pendingSettlements = new Map<string, NodeSettlement>()
  const settledNodes = new Set<string>()

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

    // 回合结束 → 消费完毕，清除待捕获候选（防跨回合/跨 step 重复 nag）；
    // 同时是**节点结算点**（REQ-422af1 t10）：本回合登记过结算则在此发信号。
    if (type === 'turn/end') {
      // REQ-e3b6a0 t-3e11bf（E2E 走查返工）：消费即留痕——"这条立项提示有没有活到本回合结束、
      // 活了多久"可查。注意 PTC（programmatic tool calling）下 tool/call 事件一律呈现为
      // run_code（见 SessionProbeAdapter.ToolTraceEntry 注释），**无法从 toolTrace 判定是否
      // 调过 reqboard_capture**；故这里只记"提示已被消费"，不做"漏执行"判定，避免误报。
      const consumed = pending.get(windowKey)
      if (consumed !== undefined) {
        pending.delete(windowKey)
        debug(
          `reqboard-capture: turn/end consumes pending capture for ${windowKey.slice(0, 16)}`
          + ` (提示存活 ${Math.max(0, now() - consumed.capturedAt)}ms)`,
        )
      }
      // D-17：这里**只发信号**，不做任何会话写操作（监听器内同步 append 会被框架拒绝）；
      // 真正的隔离动作由组合根经异步边界（setImmediate）执行，且开关默认关。
      const settle = pendingSettlements.get(windowKey)
      if (settle !== undefined) {
        pendingSettlements.delete(windowKey)
        settledNodes.add(windowKey + ':' + settle.stage)
        deps.onNodeSettled?.(settle, session)
        debug(`reqboard-settle: node ${settle.stage} settled at turn/end (${windowKey.slice(0, 16)})`)
      }
      // REQ-e3b6a0 t7：无论有没有节点结算，都问一次「该窗口有没有待处理闸门」——
      // 闸门作答不一定伴随用户消息，故不能只靠上面的 settlement 分支。
      deps.onTurnEnd?.(windowKey, session)
      return
    }

    // 触发点：仅 user/message（用户输入到达）。
    // 【诊断日志-节点2】user/message 事件到达
    if (type === 'user/message') {
      captureDiag(`reqboard-capture [NODE-2]: user/message event ARRIVED (windowKey=${windowKey.slice(0, 16)}, type=${type})`);
    }
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

    // 窗口条件：unbound → 需要立项捕获（确定性判定，语义判断留给 LLM）。
    if (!shouldCaptureWindow(snapshot(), windowKey)) {
      debug(`reqboard-capture: window ${windowKey.slice(0, 16)} bound — no capture needed`)
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
          const stage = stageReq.status
          // draft/done/canceled 不是可注入节点（types.ts）：先过闸，避免只捞到 ⑤ 铁律而误触发注入。
          if (isPromptStage(stage) && stageEnabledFor(stageReq.category, stage as StageKey)) {
            // INV-1：与 capture-section 同一取词入口（resolveStagePrompt）。
            const located = resolveStagePrompt({ stage, category: stageReq.category })
            // T-3：与 capture-section/H3/输入包同源折入地址段（第四处注入点）。
            const resolved = withAddressSection(located, deps, ledger, stageReq, stage)
            if (resolved.text.length > 0) {
              deps.onStagePrompt?.(windowKey, resolved.text)
              // INV-6：注入即留痕（与 capture-section 同一组装入口）。
              deps.injectionLog?.record(injectionLogInputFromResolved(resolved, windowKey))
              // REQ-422af1 t10：登记「本节点结算」——到 turn/end（轮次边界）才发信号并执行隔离。
              // 已结算过的节点不再登记（同一节点只遗弃一次上下文）；回合内重复消息只覆盖登记。
              if (deps.onNodeSettled !== undefined && !settledNodes.has(windowKey + ':' + stage)) {
                pendingSettlements.set(windowKey, {
                  windowKey,
                  stage,
                  requirementId: stageReq.id,
                  ...(stageReq.category === undefined ? {} : { category: stageReq.category }),
                })
              }
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
    // 【诊断日志-节点3】pendingCapture 填充状态（文件双写，防 stdout 死管道）
    captureDiag(`reqboard-capture [NODE-3]: pendingCapture SET (windowKey=${windowKey.slice(0, 16)}, size=${pending.size}, text.length=${text.length}, replaced=${replaced})`);
    logger?.info(
      `reqboard-capture: window ${windowKey.slice(0, 16)} 用户消息到达且需立项评估 → 登记待捕获（len=${text.length}${replaced ? ', 覆盖旧条目' : ''}）`,
    )
  }
}
