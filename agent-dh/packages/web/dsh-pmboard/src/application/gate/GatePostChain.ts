/**
 * 闸门后置责任链（REQ-e3b6a0 t3 / FR-2 / design/architecture.md §3）。
 *
 * 做什么：把"人工闸门被作答之后要发生什么"从各用例里收出来，变成一条**有序、可短路、可降级、
 * 幂等**的链——H1 推进落库 → H2 压缩上下文 → H3 注入阶段纪律 → H4 唤醒续跑 → H5 留痕。
 *
 * 两相执行（本模块只做骨架，不给任一 handler 的实现）：
 *  - **Phase A（内联）**：`enqueue(ctx)` 只登记，不执行任何 handler、不碰会话；
 *  - **Phase B（边界）**：`runPending(windowKey, session)` 在 agent 空闲后跑完 H1..H5。
 * 之所以分两相：弹框作答发生在 agent 的回合内，而 H2 的 surface 替换要求 `idle()`，
 * 且 `session append` 拒绝"发布中重入"（D-17 实测）。
 *
 * 四条纪律：
 *  ① 有序：严格按 `HANDLER_ORDER` 顺序执行（不重排、不并行）；
 *  ② 可短路：`skip` / `degraded` **都不阻断**后续 handler（H2 跳过时 H3 仍要注入）；
 *  ③ 可降级：任一 handler 抛错被就地转成 `degraded` 并计票，**永不冒泡**、不回滚 H1 已落库的裁决；
 *  ④ 幂等：按 `(windowKey, gate, decidedAt)` 去重（ring 容量有界，超出丢最旧），
 *     重复信号被记为 `deduped` 而不重跑。
 *
 * 分层：application 只依赖 domain 与端口（tests/layer-boundary.test.ts）；
 * 消息一律走 `fmt`（tests/message-hygiene.test.ts 的棘轮不得上涨）。
 *
 * @module dsh-pmboard/application/gate/GatePostChain
 */
import { fmt } from '../../domain/text/fmt.js'
import { pendingKeyOf, type ConfirmContext } from '../../domain/gate/GateSpec.js'
import { createPendingGateStore, type PendingGateStore } from './PendingGate.js'

/** 五个 handler 的稳定名字（顺序即执行顺序）。 */
export type HandlerName = 'h1-advance' | 'h2-compact' | 'h3-inject' | 'h4-resume' | 'h5-audit'

/** 规范执行顺序（唯一事实源；链按它排序，调用方乱序传入也会被纠正）。 */
export const HANDLER_ORDER: readonly HandlerName[] = [
  'h1-advance', 'h2-compact', 'h3-inject', 'h4-resume', 'h5-audit',
]

/**
 * handler 的执行结果。**三种都是正常返回**（抛异常不是契约的一部分）：
 *  - continue：做完了；
 *  - skip：条件不满足（如"输入包不自足""非提示词阶段"），带可读原因进留痕；
 *  - degraded：想做但没做成（通道不可用 / 投递失败），带 code 进留痕与告警。
 */
export type HandlerOutcome =
  | { readonly kind: 'continue' }
  | { readonly kind: 'skip'; readonly code: string; readonly reason: string }
  | { readonly kind: 'degraded'; readonly code: string; readonly reason: string }

/**
 * 一次链运行内的临时交换区——handler 之间传递产物（如 H3 算出的提示词交给 H4 组唤醒消息）。
 * 刻意做成显式命名的小对象：不让 handler 互相 import，也不把中间态塞进台账。
 */
export interface ChainScratch {
  /** H3 产出的阶段纪律提示词全文（H4 按 D5 分流决定是否随唤醒消息发送）。 */
  promptText?: string
  /** H2 是否真的做了整段替换（true = 提示词已在输入包里，H4 只发摘要）。 */
  compacted?: boolean
  /** 已执行步骤（链逐步追加，H5 据此写链级审计）。 */
  steps?: ChainStepResult[]
}

export interface ChainInput {
  readonly ctx: ConfirmContext
  /** Phase B 才有会话句柄；Phase A 不调用 handler，故此处可缺省（降级链要求）。 */
  readonly session?: unknown
  /** 同一次运行的交换区（链总会提供；单独调 handler 时可缺省）。 */
  readonly scratch?: ChainScratch
}

export interface GateHandler {
  readonly name: HandlerName
  /** 契约：**不要抛**；失败请返回 degraded。链仍会兜住抛错（防御性）。 */
  run(input: ChainInput): Promise<HandlerOutcome>
}

export interface ChainStepResult {
  readonly name: HandlerName
  readonly outcome: HandlerOutcome
}

export interface ChainRunSummary {
  readonly windowKey: string
  readonly gate?: ConfirmContext['gate']
  /** 本轮是否真的执行了链。 */
  readonly ran: boolean
  /** 未执行的原因：disabled / no-pending / duplicate。 */
  readonly reason?: string
  readonly steps: readonly ChainStepResult[]
  /** 其中 degraded 的步数（skip 不计）。 */
  readonly degraded: number
}

/** 链的执行计数（验收断言点：开关关时 executed 恒为 0）。 */
export interface GateChainStats {
  /** 被受理的登记次数（开关关时不计入） */
  enqueued: number
  /** 真正跑了链的次数 */
  executed: number
  /** 幂等命中次数 */
  deduped: number
  /** 因开关关闭而被忽略的次数（enqueue 与 runPending 都可能计入） */
  disabled: number
  /** handler 抛错（被就地降级）次数 */
  handlerThrew: number
}

/** 组合根与调用方消费的端口形状（ports.ts 的 GatePostChainPort 与之同形）。 */
export interface GateChainPort {
  /** Phase A：只登记。开关关 → 直接忽略。永不抛。 */
  enqueue(ctx: ConfirmContext): void
  /** Phase B：跑某窗口的待处理闸门。幂等、永不抛。 */
  runPending(windowKey: string, session?: unknown): Promise<ChainRunSummary>
}

export interface GatePostChainDeps {
  /** 注册的 handler（按 name 去重后按 HANDLER_ORDER 排序执行）。 */
  handlers: readonly GateHandler[]
  /** 链开关（默认关：与 NODE_ISOLATION 同源，由组合根决定）。 */
  enabled: boolean
  /** 登记表（缺省内部新建；测试可注入以断言）。 */
  pending?: PendingGateStore
  /** 每步的留痕钩子（t6 接注入留痕/隔离留痕）；抛错不得中断链。 */
  onStep?: (step: ChainStepResult, ctx: ConfirmContext) => void
  /** 只告警不中断（组合根接 logger.warn）。 */
  warn?: (message: string) => void
  /** 幂等去重表容量（默认 500，与注入留痕同口径）。 */
  dedupeCap?: number
}

const DEFAULT_DEDUPE_CAP = 500

/**
 * 组装链。调用方只需 `enqueue`（Phase A）与 `runPending`（Phase B）。
 * 本函数**不调度**：Phase B 的时机由既有 node-settlement 的异步边界负责（不另造调度器）。
 */
export function createGatePostChain(deps: GatePostChainDeps): GateChainPort & { stats(): GateChainStats } {
  const pending = deps.pending ?? createPendingGateStore()
  const warn = deps.warn ?? ((): void => {})
  const cap = deps.dedupeCap ?? DEFAULT_DEDUPE_CAP
  // 插入序 = 时间序：超容量丢最旧（ring 语义，避免无界增长）
  const seen = new Map<string, true>()
  const counters: GateChainStats = { enqueued: 0, executed: 0, deduped: 0, disabled: 0, handlerThrew: 0 }

  const ordered = [...deps.handlers]
    .filter((h, i, all) => all.findIndex(x => x.name === h.name) === i)
    .sort((a, b) => HANDLER_ORDER.indexOf(a.name) - HANDLER_ORDER.indexOf(b.name))

  const remember = (key: string): void => {
    seen.set(key, true)
    if (seen.size > cap) {
      const oldest = seen.keys().next().value
      if (oldest !== undefined) seen.delete(oldest)
    }
  }

  const safeWarn = (message: string): void => {
    try { warn(message) } catch { /* 告警通道自身失败也不得冒泡 */ }
  }

  return {
    enqueue(ctx) {
      if (!deps.enabled) {
        counters.disabled += 1
        return
      }
      counters.enqueued += 1
      pending.set(ctx)
    },

    async runPending(windowKey, session) {
      if (!deps.enabled) {
        counters.disabled += 1
        return { windowKey, ran: false, reason: 'disabled', steps: [], degraded: 0 }
      }
      const ctx = pending.take(windowKey)
      if (ctx === undefined) {
        return { windowKey, ran: false, reason: 'no-pending', steps: [], degraded: 0 }
      }
      const key = pendingKeyOf(ctx)
      if (seen.has(key)) {
        counters.deduped += 1
        return { windowKey, gate: ctx.gate, ran: false, reason: 'duplicate', steps: [], degraded: 0 }
      }
      remember(key)
      counters.executed += 1

      const steps: ChainStepResult[] = []
      const scratch: ChainScratch = {}
      let degraded = 0
      for (const handler of ordered) {
        let outcome: HandlerOutcome
        try {
          outcome = await handler.run({ ctx, scratch, ...(session === undefined ? {} : { session }) })
        } catch (error) {
          counters.handlerThrew += 1
          outcome = {
            kind: 'degraded',
            code: 'handler_threw',
            reason: fmt('handler {name} 抛错：{err}', {
              name: handler.name,
              err: error instanceof Error ? error.message : String(error),
            }),
          }
        }
        if (outcome.kind === 'degraded') {
          degraded += 1
          safeWarn(fmt('闸门链降级：{name}（{code}）{reason}', {
            name: handler.name, code: outcome.code, reason: outcome.reason,
          }))
        }
        const step: ChainStepResult = { name: handler.name, outcome }
        steps.push(step)
        ;(scratch.steps ??= []).push(step)
        try { deps.onStep?.(step, ctx) } catch { /* 留痕失败不得中断链 */ }
      }
      return { windowKey, gate: ctx.gate, ran: true, steps, degraded }
    },

    stats() { return { ...counters } },
  }
}
