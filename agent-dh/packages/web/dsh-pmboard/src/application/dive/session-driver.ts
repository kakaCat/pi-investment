/**
 * Dive 会话驱动器（2026-09-26 由 adapters/CaptureHook.ts 迁入；**CaptureHook 已废弃**）。
 *
 * 它是 pmboard 会话事件的**唯一扇出点**：把"会话里发生了什么"翻译成确定性动作。
 * 归 Dive 的理由（用户裁定）：**pm 各节点只干本节点的活，Dive 负责把节点串起来**。
 *
 * ── 采集点/驱动点对齐 DSH Goal round driver（用户裁定 2026-09-26）─────────────────────
 * 参照 `@deepseek-ai/dsh-goal-round-driver`（lib/index.js）：
 *   · 它把 **`agent/status === 'idle'`（整 agent 空闲）当作唯一驱动点**
 *     （`:213` ctx.on('agent/status', …)、`:80` readyToDrive 要求 status === 'idle'）；
 *   · `session/event` 只做簿记（`:258` user/message 认领、`:261` turn/end 异常取消），不驱动。
 * 本驱动器同款拆法：
 *   · **采集/簿记** —— session/event：tool/call 落工具痕迹；user/message 落证据缓冲 +
 *     本回合「有直接人类消息」这一事实（原文另行留存，供 idle 跑批引用）。
 *   · **判定/动作** —— agent/status === 'idle' 跑一批：立项候选登记 / 接手推进 /
 *     阶段纪律注入 / 节点结算 / 里程碑催办。
 *
 * 为什么旧触发点（user/message 即扇出）是错的：pendingCapture 的消费点是 systemPrompt
 * 组装（gate-wiring.ts:124），旧实现"消息到达即登记、同一回合 turn/end 清除"——登记与消费
 * 挤在同一回合内互相抵消，动态立项提示要么赶不上组装、要么已被清掉（REQ-99f5fe 现象）。
 * 改到 idle 登记 → 存活到下一回合组装时必命中。
 *
 * ⚠️ 不变量：以上任何一项都**不得**加 if (!armed) return。Dive 的语义是"armed 才自动推进"，
 * 而这些是"人点头后的必要收尾/交接/记录"；全仓至今 0 个需求开过 armed，一旦被门控，流水线立刻停摆。
 *
 * 判定链（全确定性，语义判断——值不值得立项——留给 LLM）：
 *   1. 事件类型 = user/message（用户输入到达 = 采集点）；
 *   2. 会话非忽略（isIgnoredSession：subagent/child/session-reqboard-* / parentSession / delegationDepth > 0）；
 *   3. direct human：event.data.source?.kind === 'user'（plugin/其他 kind → 排除；source 缺失退化放行，靠文本清洗兜底）；
 *   4. cleanUserMessageText 清洗后非空（剔除 checkpoint / runtime context 等系统注入块）；
 *   5. 落 roundHuman（同窗口覆盖旧条目），等 agent 空闲时统一驱动。
 *
 * 迁移口径：函数体自 CaptureHook 逐字搬移，仅**触发时点**从 user/message 收拢到 agent idle
 * （REQ-47939a t9 建 → 2026-09-26 收编进 Dive 并对齐 dsh-goal-round-driver）。
 *
 * @module dsh-pmboard/application/dive/session-driver
 */

import type { ReqboardLedger, StageKey } from '../../shared/protocol.js'
import { stageEnabledFor } from '../../shared/protocol.js'
import { isIgnoredSession, extractUserMessageText, cleanUserMessageText } from '../internal/session-message-filter.js'
import {
  openRequirementsFor,
  shouldCaptureWindow,
} from '../internal/window.js'
import type { PendingCaptureMessage } from '../internal/capture-section.js'
import type { NodeSettlement } from '../internal/node-settlement.js'
import { resolveStagePrompt, isPromptStage } from '../../domain/prompt/index.js'
import {
  injectionLogInputFromResolved,
  type InjectionLogPort,
} from '../internal/injection-log.js'
import { captureDiag } from '../internal/diag-log.js'
import { turnEndOutcome, type TurnEndOutcome } from '../internal/interruption.js'
import {
  recordToolTrace,
  recordRecentUserMsg,
  type RecentUserMsg,
  type ToolTraceEntry,
} from '../internal/session-buffers.js'
import { addressSectionFor, milestoneReminderFor } from './idle-capture-actions.js'
import type { DiveRoundDriver } from './round-driver.js'

export interface DiveSessionDriverLogger {
  /** 成员必填；logger 整体可选（deps.logger?:）→ logger?.info(...) 即安全。 */
  info(message: string): void
  debug(message: string): void
}

export interface DiveSessionDriverDeps {
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
   * 为什么必须挂在 turn/end：弹框作答发生在工具调用内（agent 忙），而压缩/唤醒要求轮次边界；
   * 且监听器内不得做会话写操作（D-17）——故本回调只发信号，真正的执行由组合根放到异步边界。
   * 可选（未注入 = 不触发链）。
   */
  onTurnEnd?: (windowKey: string, session: unknown) => void
  /**
   * 回合结束的断点信号（REQ-260924213231-b1c4 T-9 / FR-6）：读 `turn/end.data.reason`，
   * 规范化后**只发信号**（沿用 D-17：监听器内不做会话写操作）——写台账由组合根放到
   * 异步边界（setImmediate）执行。形态不认识 → 不调用（不猜、不误报）。
   * 可选（未注入 = 不发信号）。
   */
  onTurnFinished?: (windowKey: string, outcome: TurnEndOutcome, session: unknown) => void
  /** 工具痕迹表（REQ-2e9473 t05）：hook 写入，done 凭证门（t06）读取。可选（未注入 = 关闭跟踪）。 */
  toolTrace?: Map<string, ToolTraceEntry[]>
  /** 最近用户消息缓冲（REQ-2e9473 t10）：hook 写入，confirm_artifact 文字确认核验读取。可选。 */
  recentUserMsgs?: Map<string, RecentUserMsg[]>
  /** 注入留痕端口（REQ-422af1 t6）：状态转移注入后调用 record。可选（未注入 = 不留痕）。 */
  injectionLog?: InjectionLogPort
  /** 模板地址注入（REQ-260922213356-4a45 T-3）：绝对模板根 + 开关；缺省不注入。 */
  address?: { templateRoot?: string; enabled?: boolean }
  /**
   * 节点结算回调（REQ-422af1 t10）：绑定窗口**整 agent 空闲**（agent/status === 'idle'）且
   * 本回合登记过「可注入节点结算」时发信号，并携带会话句柄（隔离端口由组合根按会话构造）。
   * **本回调不得在事件派发内做会话写操作**（D-17：监听器内同步 append 会被框架拒绝
   * "session append cannot reenter while another append is being published"）——
   * hook 只发信号，真正执行的异步边界在 application/internal/node-settlement.ts。
   * 可选（未注入 = 关闭结算信号）。
   */
  onNodeSettled?: (settle: NodeSettlement, session: unknown) => void
  /**
   * round 半（REQ-260926215013-1568 T-4）：idle 拍由它定序（复位 competingQueued → 采集跑批 →
   * requestDrive），session/event 的回合簿记也经它（admission / turn-end 收尾）。
   * 可选（未注入 = 纯采集/簿记，行为与改动前逐字一致——旧调用方与脚本不受影响）。
   */
  round?: DiveRoundDriver
  logger?: DiveSessionDriverLogger
}

/**
 * 驱动器双入口（对齐 dsh-goal-round-driver：一个状态机、两路订阅）。
 *   · 调用自身 = session/event 簿记入口（tool/call、user/message、turn/end 收尾）
 *   · onAgentStatus = agent/status 驱动入口；仅整 agent 空闲（idle）时跑批
 */
export interface DiveSessionDriver {
  (session: unknown, event: unknown): void
  onAgentStatus(agent: unknown, status: unknown): void
}

/** 从 user/message 事件 data 提取 source.kind（缺失 → undefined）。 */
function eventSourceKind(data: unknown): unknown {
  if (typeof data !== 'object' || data === null) return undefined
  const source = (data as { source?: unknown }).source
  if (typeof source !== 'object' || source === null) return undefined
  return (source as { kind?: unknown }).kind
}

/** 从 agent/status 载荷取 windowKey 与会话句柄（会话 id 即窗口键；goal driver 同口径）。 */
function agentRef(agent: unknown): { windowKey: string; session: unknown } | undefined {
  if (typeof agent !== 'object' || agent === null) return undefined
  const a = agent as { id?: unknown; session?: unknown }
  const session = a.session
  const sessionId = (typeof session === 'object' && session !== null)
    ? (session as { id?: unknown }).id
    : undefined
  const id = typeof sessionId === 'string' && sessionId.length > 0
    ? sessionId
    : (typeof a.id === 'string' && a.id.length > 0 ? a.id : undefined)
  if (id === undefined) return undefined
  return { windowKey: id, session: session ?? agent }
}

/**
 * 创建 Dive 驱动器。返回可调用对象（session/event 簿记入口），并挂 `onAgentStatus`
 * 作为 agent/status 驱动入口——与 dsh-goal-round-driver 的「一个状态机 + 两路订阅」同形。
 * 纯同步、无异步 IO；幂等（重复触发同消息只保留最新登记）。
 */
export function createDiveSessionDriver(deps: DiveSessionDriverDeps): DiveSessionDriver {
  const { snapshot, pending, now, logger } = deps
  const debug = (m: string) => logger?.debug?.(m)

  // 里程碑提醒去重（t09）：每产物只提醒一次（确认后 stage/confirmedAt 变化自然失效）。
  const remindedAt = new Map<string, number>()

  // 已结算节点去重键 = 窗口:节点——同一节点只结算一次，否则每次空闲都会重复遗弃一次上下文。
  const settledNodes = new Set<string>()

  // 本回合采集到的「直接人类消息」（user/message 落，agent idle 消费）。
  const roundHuman = new Map<string, PendingCaptureMessage>()

  /**
   * idle 跑批（对齐 dsh-goal-round-driver 的 drive）：判定 + 动作全在这一拍。
   * 采集留、判定/动作走——证据缓冲与工具痕迹仍留在各自事件的采集点。
   */
  function driveIdle(windowKey: string, session: unknown): void {
    const human = roundHuman.get(windowKey)
    if (human !== undefined) roundHuman.delete(windowKey)

    // 上一拍登记的立项候选，已被本回合 systemPrompt 组装的取词点消费 → 清除。
    if (pending.has(windowKey)) pending.delete(windowKey)

    const ledger = snapshot()

    // ── unbound：立项候选登记（在 idle 登记 → 存活到下一回合 systemPrompt 组装时命中）
    if (shouldCaptureWindow(ledger, windowKey)) {
      if (human !== undefined) {
        pending.set(windowKey, human)
        captureDiag(`reqboard-capture [NODE-3]: pendingCapture SET at idle (windowKey=${windowKey.slice(0, 16)}, size=${pending.size}, text.length=${human.text.length})`)
        logger?.info(
          `reqboard-capture: idle 登记待立项评估（len=${human.text.length}）——下一回合 systemPrompt 取词时注入针对性立项提示`,
        )
      }
      return
    }

    const open = openRequirementsFor(ledger, windowKey)
    const stageReq = [...open].sort((a, b) => b.updatedAt - a.updatedAt)[0]

    if (human !== undefined) {
      // R1 接手推进：已绑定窗口出现直接人类消息 = 该窗口仍在推进其需求 → 其 draft 需求进评审。
      deps.onBoundWindowActivity?.(windowKey, human.text)

      if (stageReq !== undefined) {
        const stage = stageReq.status
        // draft/done/canceled 不是可注入节点：先过闸，避免只捞到 ⑤ 铁律而误触发注入。
        if (isPromptStage(stage) && stageEnabledFor(stageReq.category, stage as StageKey)) {
          // INV-1：与 capture-section 同一取词入口（resolveStagePrompt）。
          const located = resolveStagePrompt({ stage, category: stageReq.category })
          // T-3：与 capture-section/H3/输入包同源折入地址段（第四处注入点）。
          const resolved = addressSectionFor(located, deps.address, ledger, stageReq, stage)
          if (resolved.text.length > 0) {
            deps.onStagePrompt?.(windowKey, resolved.text)
            // INV-6：注入即留痕（与 capture-section 同一组装入口）。
            deps.injectionLog?.record(injectionLogInputFromResolved(resolved, windowKey))
            // REQ-422af1 t10：idle = 上一回合的轮次边界 → 立即发节点结算信号（隔离在异步边界执行）。
            // 已结算过的节点不再结算（同一节点只遗弃一次上下文）。
            if (deps.onNodeSettled !== undefined && !settledNodes.has(windowKey + ':' + stage)) {
              settledNodes.add(windowKey + ':' + stage)
              deps.onNodeSettled({
                windowKey,
                stage,
                requirementId: stageReq.id,
                ...(stageReq.category === undefined ? {} : { category: stageReq.category }),
              }, session)
              debug(`reqboard-settle: node ${stage} settled at idle (${windowKey.slice(0, 16)})`)
            }
          }
        }
      }
    }

    // 里程碑超时提醒（REQ-2e9473 t09）：时间型，不依赖本回合是否有消息——每产物只提醒一次。
    const reminder = milestoneReminderFor(ledger, windowKey, now())
    if (reminder !== undefined && !remindedAt.has(reminder.artifactKey)) {
      remindedAt.set(reminder.artifactKey, now())
      deps.onStagePrompt?.(windowKey, reminder.text)
      debug('reqboard-capture: milestone reminder injected → ' + reminder.artifactKey)
    }
  }

  /** session/event 簿记入口：只采集/只收尾，不做任何「判定 + 动作」扇出。 */
  const driver = ((session: unknown, event: unknown): void => {
    const sessionObj = (typeof session === 'object' && session !== null ? session : {}) as { id?: unknown }
    const windowKey = typeof sessionObj.id === 'string' && sessionObj.id.length > 0 ? sessionObj.id : ''
    if (!windowKey) return

    const evt = (typeof event === 'object' && event !== null ? event : {}) as { type?: unknown; data?: unknown }
    const type = typeof evt.type === 'string' ? evt.type : ''

    // 回合侧簿记（T-4）：admission（user/message 身份匹配 → 准入计数）与 turn/end 异常收尾经 round 半。
    if (deps.round !== undefined) deps.round.onSessionEvent(session, event)

    // 工具痕迹（REQ-2e9473 t05）：tool/call 事件按窗口落痕，done 凭证门据此判定
    // "开工以来有无真实工具动作"。忽略会话（subagent 等）不记——各算各账。
    if (type === 'tool/call') {
      if (deps.toolTrace !== undefined && !isIgnoredSession(windowKey, session)) {
        const data = (typeof evt.data === 'object' && evt.data !== null ? evt.data : {}) as { name?: unknown }
        recordToolTrace(deps.toolTrace, windowKey, typeof data.name === 'string' ? data.name : '?', now())
      }
      return
    }

    // 回合结束：只做簿记（对齐 dsh-goal-round-driver —— 它也只在这里做认领/异常取消）。
    // 判定与动作不在这里，等 agent/status 空闲后统一跑批。
    if (type === 'turn/end') {
      // REQ-e3b6a0 t7：无论有没有节点结算，都问一次「该窗口有没有待处理闸门」——
      // 闸门作答不一定伴随用户消息，故不能只靠 idle 跑批。
      deps.onTurnEnd?.(windowKey, session)
      // REQ-260924213231-b1c4 T-9 / FR-6（写入器 B）：回合异常收尾（aborted/error/
      // interrupted）时补写断点原因；此处只发信号，写台账走组合根异步边界（D-17）。
      // 形态不认识 → turnEndOutcome 返回 undefined → 不发信号（A 的 checkpoint 仍在）。
      const outcome = turnEndOutcome((evt as { data?: unknown }).data)
      if (outcome !== undefined) deps.onTurnFinished?.(windowKey, outcome, session)
      return
    }

    // 采集点：仅 user/message（用户输入到达）。
    // 【诊断日志-节点2】user/message 事件到达
    if (type === 'user/message') {
      captureDiag(`reqboard-capture [NODE-2]: user/message event ARRIVED (windowKey=${windowKey.slice(0, 16)}, type=${type})`)
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
    // 必须留在采集点：核验发生在**同一回合内**，idle 跑批时已来不及。
    if (deps.recentUserMsgs !== undefined) {
      recordRecentUserMsg(deps.recentUserMsgs, windowKey, text, now())
    }

    // 仅采集，不判定：等 agent 空闲（agent/status === 'idle'）时统一驱动。
    const replaced = roundHuman.has(windowKey)
    roundHuman.set(windowKey, { windowKey, text, capturedAt: now() })
    // 【诊断日志-节点3】本回合直接人类消息采集状态（文件双写，防 stdout 死管道）
    captureDiag(`reqboard-capture [NODE-3]: roundHuman SET (windowKey=${windowKey.slice(0, 16)}, text.length=${text.length}, replaced=${replaced})`)
    logger?.info(
      `reqboard-capture: 采集到直接人类消息（待 idle 驱动，len=${text.length}${replaced ? ', 覆盖旧条目' : ''}）`,
    )
  }) as DiveSessionDriver

  /**
   * agent/status 驱动入口（对齐 dsh-goal-round-driver lib/index.js:213）：
   * 仅整 agent 空闲（idle）时跑批——对话真正结束后的那一拍才是 Dive 的采集点。
   */
  driver.onAgentStatus = (agent: unknown, status: unknown): void => {
    if (status !== 'idle') return
    const ref = agentRef(agent)
    if (ref === undefined) return
    const { windowKey, session } = ref
    if (isIgnoredSession(windowKey, session)) {
      debug(`reqboard-capture: ignored session (idle) ${windowKey.slice(0, 16)}`)
      return
    }
    const tick = (): void => {
      try {
        driveIdle(windowKey, session)
      } catch (err) {
        // 驱动失败不能炸宿主事件循环：记 warn，等下一次 idle 重试。
        logger?.info(`reqboard-capture: idle drive failed (${windowKey.slice(0, 16)}): ${String(err)}`)
      }
    }
    // 定序（T-4）：round 半先复位 competingQueued → 采集跑批（可能同步排入纪律提示）→ 请求驱动。
    if (deps.round !== undefined) deps.round.onIdle(agent, tick)
    else tick()
  }

  return driver
}
