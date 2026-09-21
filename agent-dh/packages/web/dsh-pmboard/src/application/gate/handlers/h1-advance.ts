/**
 * H1 推进校验与上下文回填（REQ-e3b6a0 t7 / FR-2）——链的**第一步**。
 *
 * 为什么 Phase B 还要"校验推进"：真正落章与状态迁移发生在 Phase A（用例内），而装饰器登记时
 * 无权断言结果（作答与落库之间隔着用例的后续动作）。故本 handler 以**台账实时状态**为准：
 *
 *   需求 status === ctx.to → verdict=affirmative（推进确实发生了）
 *   否则                   → verdict=negative（非肯定项 / 未落库 / 并发改了状态）
 *
 * 它同时把 requirementId 回填进上下文，供 H2/H3/H5 使用。**永不抛**。
 *
 * @module dsh-pmboard/application/gate/handlers/h1-advance
 */
import { fmt } from '../../../domain/text/fmt.js'
import type { ReqboardRepository } from '../../ports.js'
import type { ChainInput, GateHandler, HandlerOutcome } from '../GatePostChain.js'
import { pickGateRequirement, reasonOf } from './shared.js'

export interface H1AdvanceDeps {
  repo: ReqboardRepository
}

export function createH1AdvanceHandler(deps: H1AdvanceDeps): GateHandler {
  return {
    name: 'h1-advance',
    async run({ ctx }: ChainInput): Promise<HandlerOutcome> {
      try {
        const requirement = pickGateRequirement(deps.repo, ctx)
        if (requirement === undefined) {
          ctx.verdict = 'negative'
          return { kind: 'skip', code: 'no_requirement', reason: '本窗口无可归属需求，无法校验推进结果' }
        }
        ctx.requirementId = requirement.id
        if (requirement.status === ctx.to) {
          ctx.verdict = 'affirmative'
          return { kind: 'continue' }
        }
        ctx.verdict = 'negative'
        return {
          kind: 'skip',
          code: 'not_advanced',
          reason: fmt('需求当前 {now}，未推进到 {to}（视为非肯定项或未落库）', { now: requirement.status, to: ctx.to }),
        }
      } catch (error) {
        ctx.verdict = 'negative'
        return { kind: 'degraded', code: 'h1_threw', reason: fmt('H1 校验异常：{err}', { err: reasonOf(error) }) }
      }
    },
  }
}
