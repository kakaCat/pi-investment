/**
 * H5 链级审计留痕（REQ-e3b6a0 t7 / FR-6）——把"这次确认之后每一步跑了什么"写进需求时间线。
 *
 * 为什么需要它：注入留痕（INV-6）记的是"注入了什么"，隔离留痕记的是"遗弃了哪一段"，
 * 但**没有任何一处**回答"这次确认之后整条链的结果如何"（哪步 continue、哪步 skip、哪步降级）。
 * 本 handler 在链尾把 `scratch.steps` 落成一条台账评论，人回看时一眼能查到。
 *
 * @module dsh-pmboard/application/gate/handlers/h5-audit
 */
import { fmt } from '../../../domain/text/fmt.js'
import type { ReqboardRepository } from '../../ports.js'
import type { ChainInput, ChainStepResult, GateHandler, HandlerOutcome } from '../GatePostChain.js'
import { reasonOf } from './shared.js'

export interface H5AuditDeps {
  repo: ReqboardRepository
  now: () => number
  newCommentId: () => string
}

/** 一步的可读描述：名字=结果（降级/跳过带 code）。 */
function describeStep(step: ChainStepResult): string {
  if (step.outcome.kind === 'continue') return fmt('{name}=ok', { name: step.name })
  return fmt('{name}={kind}（{code}）', { name: step.name, kind: step.outcome.kind, code: step.outcome.code })
}

export function createH5AuditHandler(deps: H5AuditDeps): GateHandler {
  return {
    name: 'h5-audit',
    async run({ ctx, scratch }: ChainInput): Promise<HandlerOutcome> {
      try {
        if (ctx.requirementId === undefined || ctx.requirementId.length === 0) {
          return { kind: 'skip', code: 'no_requirement', reason: '无归属需求，链级审计无处落账' }
        }
        const steps = scratch?.steps ?? []
        const stepsText = steps.length === 0 ? '（无步骤记录）' : steps.map(describeStep).join('；')
        const body = fmt('[闸门后置链] {gate}：{steps}', { gate: ctx.gate, steps: stepsText })
        const at = deps.now()
        await deps.repo.mutate('requirement-updated', (ledger) => {
          const req = ledger.requirements.find(r => r.id === ctx.requirementId)
          if (req === undefined) return undefined
          req.comments.push({
            id: deps.newCommentId(),
            body,
            createdAt: at,
            createdBy: { kind: 'agent', sessionId: ctx.windowKey },
          })
          req.version += 1
          req.updatedAt = at
          req.updatedBy = { kind: 'agent', sessionId: ctx.windowKey }
          return { requirements: [req] }
        })
        return { kind: 'continue' }
      } catch (error) {
        return { kind: 'degraded', code: 'h5_threw', reason: fmt('H5 审计异常：{err}', { err: reasonOf(error) }) }
      }
    },
  }
}
