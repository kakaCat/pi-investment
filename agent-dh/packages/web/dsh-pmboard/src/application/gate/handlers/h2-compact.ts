/**
 * H2 压缩上下文（REQ-e3b6a0 t5 / FR-3 / design/architecture.md §4）——把既有的
 * 节点边界隔离（`use-cases/IsolateNodeContext.ts`）**接进闸门后置链**。
 *
 * 本 handler 只做三件"链侧"的事，压缩算法本身一行不改：
 *  ① **条件判定**：肯定项 && 输入包自足（路由提示词可用 **且** 需求文档已落盘）&& `to` 是可注入阶段；
 *  ② **构造端口**：会话句柄 → `NodeIsolationPort`（组合根按会话构造），并转交留痕端口；
 *  ③ **结果映射**：replaced→continue；skipped→skip；rejected/fallback→degraded。四态都不抛。
 *
 * 三条纪律仍在 `isolateNodeContext` 内部执行、本层不得放松：
 *  先落盘再遗弃（`artifactSeq < replacementSeq`）/ 边界 tool 配对平衡 / 只在轮次边界（`idle()`）。
 *
 * 「输入包自足」是**本层新加的闸**：G0 立项门那一刻 `requirement.md` 还不存在，若压缩会把
 * "用户为什么提这个需求"一起丢掉——所以宁可不压（skip 并留痕），也不产出不自足的输入包。
 *
 * @module dsh-pmboard/application/gate/handlers/h2-compact
 */
import { fmt } from '../../../domain/text/fmt.js'
import { isPromptStage } from '../../../domain/prompt/index.js'
import type { ConfirmContext } from '../../../domain/gate/GateSpec.js'
import type { Clock, DocRepository, ReqboardRepository } from '../../ports.js'
import { requirementDocPath } from '../../internal/node-input-package.js'
import { pickGateRequirement, reasonOf, safeReadDoc } from './shared.js'
import {
  isolateNodeContext,
  type IsolateNodeContextDeps,
  type IsolateNodeContextRequest,
  type IsolateNodeContextResult,
  type IsolationTracePort,
  type NodeIsolationPort,
} from '../../use-cases/IsolateNodeContext.js'
import type { ChainInput, GateHandler, HandlerOutcome } from '../GatePostChain.js'

export interface H2CompactDeps {
  repo: ReqboardRepository
  docs: DocRepository
  clock: Clock
  /**
   * 压缩开关（D1：链默认开、**压缩默认关**——surface 替换是高风险动作，先验证「不压缩也能自动续跑」）。
   * false → 直接 skip(compaction_disabled)，不进 isolateNodeContext。
   */
  compactionEnabled?: boolean
  /** 会话句柄 → 隔离端口（组合根构造）；返回 undefined = 触达不到（走 fallback）。 */
  isolationFor?: (session: unknown, ctx: ConfirmContext) => NodeIsolationPort | undefined
  trace?: IsolationTracePort
  /** 用例执行器（默认 isolateNodeContext）；测试可换替身做异常/边界路径。 */
  run?: (deps: IsolateNodeContextDeps, request: IsolateNodeContextRequest) => Promise<IsolateNodeContextResult>
  /** 纪律①的落盘证据指针（默认取台账 revision：persistAtomic 成功后才 bump）。 */
  persistArtifacts?: (ctx: ConfirmContext) => number | Promise<number>
}


/** 组装 H2 handler。**永不抛**：任何意外都被就地降级为 degraded。 */
export function createH2CompactHandler(deps: H2CompactDeps): GateHandler {
  const run = deps.run ?? isolateNodeContext
  const persist = deps.persistArtifacts ?? ((): number => deps.repo.snapshot().revision)

  return {
    name: 'h2-compact',
    async run({ ctx, session, scratch }: ChainInput): Promise<HandlerOutcome> {
      try {
        if (deps.compactionEnabled === false) {
          return { kind: 'skip', code: 'compaction_disabled', reason: '压缩开关未开（D1：先验证不压缩也能续跑）' }
        }
        if (ctx.verdict !== 'affirmative') {
          return { kind: 'skip', code: 'negative_verdict', reason: '非肯定项：阶段未变，不压缩' }
        }
        if (!isPromptStage(ctx.to)) {
          return { kind: 'skip', code: 'not_prompt_stage', reason: fmt('阶段 {to} 不可注入，不压缩', { to: ctx.to }) }
        }
        const requirement = pickGateRequirement(deps.repo, ctx)
        const docPath = requirementDocPath(requirement)
        if (requirement === undefined || docPath.length === 0) {
          return { kind: 'skip', code: 'no_requirement', reason: '本窗口无可归属需求，输入包不可构造' }
        }
        const docText = await safeReadDoc(deps.docs, docPath)
        if (docText.trim().length === 0) {
          return { kind: 'skip', code: 'doc_not_ready', reason: fmt('需求文档未落盘（{path}），输入包不自足', { path: docPath }) }
        }
        const isolation = deps.isolationFor?.(session, ctx)
        const useCaseDeps: IsolateNodeContextDeps = {
          repo: deps.repo,
          docs: deps.docs,
          clock: deps.clock,
          ...(isolation === undefined ? {} : { isolation }),
          ...(deps.trace === undefined ? {} : { trace: deps.trace }),
        }
        const result = await run(useCaseDeps, {
          windowKey: ctx.windowKey,
          stage: ctx.to,
          ...(requirement.category === undefined ? {} : { category: requirement.category }),
          requirementId: requirement.id,
          persistArtifacts: () => persist(ctx),
        })
        if (result.replaced) {
          if (scratch !== undefined) scratch.compacted = true
          return { kind: 'continue' }
        }
        if (result.status === 'skipped') {
          return { kind: 'skip', code: result.code ?? 'skipped', reason: result.trace.reason }
        }
        if (result.status === 'fallback') {
          return { kind: 'degraded', code: result.code ?? 'fallback', reason: result.trace.reason }
        }
        return { kind: 'degraded', code: result.code ?? 'rejected', reason: result.trace.reason }
      } catch (error) {
        return { kind: 'degraded', code: 'h2_threw', reason: fmt('H2 压缩异常：{err}', { err: reasonOf(error) }) }
      }
    },
  }
}
