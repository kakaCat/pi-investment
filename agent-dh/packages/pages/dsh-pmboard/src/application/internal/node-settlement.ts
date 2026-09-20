/**
 * 节点结算点 → 隔离执行分发（REQ-422af1 t10 / D-17 / design/architecture.md §5）。
 *
 * 定位：**接线件**。真正的隔离执行模型在 use-cases/IsolateNodeContext.ts（t9），本模块只负责
 * 三件事——开关、异步边界、失败隔离：
 *
 *  ① **开关默认关**（NODE_ISOLATION）：enabled=false 时 onSettle 直接返回——不调度、不建端口、
 *     不触会话，隔离代码路径**执行 0 次**（stats 四项计数全 0 即其可执行证明）。
 *  ② **必须移出 session/event 派发**（D-17，t9 实测）：监听器内同步 append 会被框架拒绝
 *     （"session append cannot reenter while another append is being published"，
 *     dsh-session lib/index.js:1183）。故 onSettle 只把任务交给**异步边界**
 *     （默认 setImmediate；严格晚于当前派发与 append 发布），并保证返回前任务未执行。
 *  ③ **失败只告警不中断**：结算点在上游是 session/event 监听器，任何异常冒泡都会打断流水线。
 *     本模块把用例异常、用例非 replaced 结果、留痕失败统统降级为 warn，绝不抛。
 *
 * 分层：application 层禁 import node:/@deepseek-ai/*（tests/layer-boundary.test.ts）；
 * setImmediate 是宿主全局而非 node: 导入，且可经 deps.schedule 注入替身（测试用）。
 * 会话句柄 → 隔离端口由组合根构造（deps.isolationFor），本模块只做转发。
 *
 * @module dsh-pmboard/application/internal/node-settlement
 */
import type { Clock, DocRepository, ReqboardRepository } from '../ports.js'
import { fmt } from '../../domain/text/fmt.js'
import type { Category, Difficulty, PromptStage } from '../../domain/prompt/index.js'
import {
  isolateNodeContext,
  type IsolateNodeContextDeps,
  type IsolateNodeContextRequest,
  type IsolateNodeContextResult,
  type IsolationTracePort,
  type NodeIsolationPort,
} from '../use-cases/IsolateNodeContext.js'

/** 一次节点结算（绑定窗口推进到某个可注入节点、且该回合已结束）。 */
export interface NodeSettlement {
  windowKey: string
  stage: PromptStage
  /** 缺省 → 路由按 DEFAULT_CATEGORY 解析。 */
  category?: Category
  /** 缺省 → 路由按 DEFAULT_DIFFICULTY 解析（light）。 */
  difficulty?: Difficulty
  /** 归属需求 id（台账投影用）。 */
  requirementId?: string
}

/** 执行计数——开关关闭时四项必须全为 0（验收断言点）。 */
export interface NodeSettlementStats {
  /** 交给异步边界的次数（开关关 = 0） */
  scheduled: number
  /** 真正进入隔离用例的次数（开关关 = 0） */
  executed: number
  /** 用例返回 replaced（真的做了整段替换）的次数 */
  replaced: number
  /** 用例异常（未预期）次数；正常恒为 0 */
  failed: number
}

/**
 * 闸门后置链触发端口（REQ-e3b6a0 t3）——结算点只关心"跑没跑"，不关心链内部。
 *
 * 为什么单独给开关：D1 决策是"链先开、压缩后开"，故链的开关（enabled）与
 * NODE_ISOLATION（deps.enabled）**相互独立**——链开着时隔离代码路径仍可关闭。
 */
export interface GateChainTrigger {
  /** 链自身开关。缺省视为开（注入即表示调用方要它跑）。 */
  readonly enabled?: boolean
  /** Phase B：跑该窗口的待处理闸门。返回 ran 供调用方决定是否跳过遗留隔离路径。 */
  runPending(windowKey: string, session?: unknown): Promise<{ ran: boolean }>
}

export interface NodeSettlementDeps {
  /** 开关（NODE_ISOLATION，默认关）。false = 隔离代码路径执行 0 次。 */
  enabled: boolean
  /**
   * 闸门后置链（REQ-e3b6a0 t3）：结算点是 Phase B 的唯一时机，故链从这里触发。
   * 缺省 = 不接链（行为与引入前完全一致）。
   */
  chain?: GateChainTrigger
  /** 会话句柄 → 隔离端口（组合根构造 NodeIsolationAdapter）；返回 undefined = 触达不到（D-12 ②）。 */
  isolationFor?: (session: unknown, settle: NodeSettlement) => NodeIsolationPort | undefined
  /** 隔离留痕端口（t9 定义）。 */
  trace?: IsolationTracePort
  /** 纪律①先落盘再遗弃：返回"结算点前置状态已落盘"的序号；未注入 = 取台账 revision。 */
  persistArtifacts?: (settle: NodeSettlement) => number | Promise<number>
  repo: ReqboardRepository
  docs: DocRepository
  clock: Clock
  /** 异步边界调度（默认 setImmediate）；注入替身可做调用顺序断言。 */
  schedule?: (task: () => void) => void
  /** 只告警不中断：所有非成功路径与异常都经这里（组合根接 logger.warn）。 */
  warn?: (message: string) => void
  /** 用例执行器（默认 isolateNodeContext）；测试可换替身做异常路径。 */
  run?: (deps: IsolateNodeContextDeps, request: IsolateNodeContextRequest) => Promise<IsolateNodeContextResult>
}

export interface NodeSettlementDispatcher {
  /** 结算点发来的信号：开关关 → no-op；开关开 → 交给异步边界执行。**永不同步执行、永不抛**。 */
  onSettle(settle: NodeSettlement, session?: unknown): void
  stats(): NodeSettlementStats
}

/** 默认异步边界：setImmediate（宏任务，严格晚于当前同步派发与 session append 的发布）。 */
function defaultSchedule(task: () => void): void {
  setImmediate(task)
}

/**
 * 组装结算 → 隔离分发器。调用方（组合根）只需把 onSettle 接到 CaptureHook 的
 * onNodeSettled；其余（开关、时机、失败处理、留痕）都在这里。
 */
export function createNodeSettlementDispatcher(deps: NodeSettlementDeps): NodeSettlementDispatcher {
  const counts: NodeSettlementStats = { scheduled: 0, executed: 0, replaced: 0, failed: 0 }
  const schedule = deps.schedule ?? defaultSchedule
  const warn = deps.warn ?? ((): void => {})
  const run = deps.run ?? isolateNodeContext
  const persist = deps.persistArtifacts ?? ((): Promise<number> => {
    // 结算点的前置状态（节点推进/产物登记）已由台账写入落盘；revision 是持久化的单调序号
    // （JsonLedgerRepository 在 persistAtomic 成功后才 bump），故作为"先落盘"的证据指针。
    return Promise.resolve(deps.repo.snapshot().revision)
  })

  /** 链是否生效：注入了 chain 且其开关未显式关闭。 */
  const chainActive = (): boolean => deps.chain !== undefined && deps.chain.enabled !== false

  const notify = (message: string): void => {
    try {
      warn(message)
    } catch {
      // 告警通道自身失败也不得冒泡（结算点在 session/event 派发链上）。
    }
  }

  const execute = async (settle: NodeSettlement, session: unknown): Promise<void> => {
    counts.executed += 1
    // ── 闸门后置链（Phase B，REQ-e3b6a0 t3）────────────────────────────────
    // 链自带全量降级（永不抛），此处 catch 只是最后一道网。
    // 链跑过（ran=true，说明该窗口确有待处理闸门且已由 H2 压缩）→ 不再走下面的遗留隔离路径，
    // 否则同一轮会对同一窗口压缩两次。
    if (chainActive()) {
      try {
        const summary = await deps.chain!.runPending(settle.windowKey, session)
        if (summary.ran) return
      } catch (error) {
        counts.failed += 1
        notify(fmt('闸门后置链执行异常（已忽略，不影响流水线）：{err}', {
          err: error instanceof Error ? error.message : String(error),
        }))
      }
    }
    // ── 遗留隔离路径（NODE_ISOLATION；触发源 = 绑定窗口收到用户消息）──────
    if (!deps.enabled) return
    try {
      const isolation = deps.isolationFor?.(session, settle)
      const useCaseDeps: IsolateNodeContextDeps = {
        repo: deps.repo,
        docs: deps.docs,
        clock: deps.clock,
        ...(isolation === undefined ? {} : { isolation }),
        ...(deps.trace === undefined ? {} : { trace: deps.trace }),
      }
      const request: IsolateNodeContextRequest = {
        windowKey: settle.windowKey,
        stage: settle.stage,
        ...(settle.difficulty === undefined ? {} : { difficulty: settle.difficulty }),
        ...(settle.category === undefined ? {} : { category: settle.category }),
        ...(settle.requirementId === undefined ? {} : { requirementId: settle.requirementId }),
        persistArtifacts: () => persist(settle),
      }
      const result = await run(useCaseDeps, request)
      if (result.replaced) {
        counts.replaced += 1
        return
      }
      notify(fmt('节点隔离未替换（{status}/{code}）：{reason}', {
        status: result.status,
        code: result.code ?? '-',
        reason: result.trace.reason,
      }))
    } catch (error) {
      counts.failed += 1
      notify(fmt('节点隔离执行异常（已忽略，不影响流水线）：{err}', {
        err: error instanceof Error ? error.message : String(error),
      }))
    }
  }

  return {
    onSettle(settle: NodeSettlement, session?: unknown): void {
      // 两个开关都不生效（默认）：一次都不执行——不调度、不建端口、不触会话。
      if (!deps.enabled && !chainActive()) return
      counts.scheduled += 1
      // D-17：交给异步边界，绝不在 session/event 派发内同步执行。
      schedule(() => {
        // execute 自带全量 try/catch（且 notify 亦不抛），此处 catch 只是最后一道网。
        void execute(settle, session).catch(() => undefined)
      })
    },
    stats(): NodeSettlementStats {
      return { ...counts }
    },
  }
}
