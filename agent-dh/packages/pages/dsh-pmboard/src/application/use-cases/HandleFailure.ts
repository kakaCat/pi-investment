/**
 * 失败处置（REQ-4842fe t8 / FR-13、FR-14）：失败即暂停后，人三选一，选完即生效。
 *
 * 三处置（design/observability §3）：
 *  - 重跑该卡：开启 autoRun 并触发一次推进事件（不自动重试——重跑是人拍板的）；
 *  - 退回上游重新描述需求：implementing → design（人工门），重批准计划后就地更新旧卡；
 *  - 取消：需求 → canceled（人工门）。
 *
 * @module dsh-pmboard/application/use-cases/HandleFailure
 */
import type { UseCaseDeps } from '../ports.js'
import { fmt } from '../../domain/text/fmt.js'
import { assertReqTransition, recordStatus } from '../../shared/protocol.js'
import { advanceRequirement } from './AdvanceChain.js'

export type FailureChoice = 'rerun' | 'upstream' | 'cancel'

export const FAILURE_CHOICE_LABELS: Readonly<Record<FailureChoice, string>> = {
  rerun: '重跑该卡',
  upstream: '退回上游重新描述需求',
  cancel: '取消需求',
}

function choiceOfLabel(label: string): FailureChoice | undefined {
  const hit = (Object.keys(FAILURE_CHOICE_LABELS) as FailureChoice[]).find((k) => FAILURE_CHOICE_LABELS[k] === label)
  return hit
}

/**
 * 弹出三选处置（会话内弹框，FR-16）。弹框通道不可用返回 undefined（调用方保留看板入口）。
 */
export async function openFailurePopup(
  deps: UseCaseDeps,
  requirementId: string,
  exec?: unknown,
): Promise<FailureChoice | undefined> {
  if (!deps.questions.available()) return undefined
  const answers = await deps.questions.ask(
    [{
      id: 'failure-decision',
      header: '实施链已暂停',
      question: fmt('需求 {req} 的实施链因失败暂停，请选择处置方式（重跑 / 退回上游 / 取消）', { req: requirementId }),
      options: (Object.keys(FAILURE_CHOICE_LABELS) as FailureChoice[]).map((k) => ({ label: FAILURE_CHOICE_LABELS[k] })),
    }],
    { ...(exec !== undefined ? { agent: exec } : {}) },
  )
  const label = answers[0]?.selected?.[0]
  return label === undefined ? undefined : choiceOfLabel(label)
}

/**
 * 执行处置选择。三选各自生效；重跑通过"置 autoRun=true + 触发一次事件"实现
 * （链会在下一个事件继续，且已 no-op 的步不会重做）。
 */
export async function handleFailureChoice(
  deps: UseCaseDeps,
  requirementId: string,
  choice: FailureChoice,
): Promise<{ ok: boolean; note: string }> {
  const now = deps.clock.now()
  if (choice === 'rerun') {
    await deps.repo.mutate('failure-rerun', (ledger) => {
      const req = ledger.requirements.find((r) => r.id === requirementId)
      if (req === undefined) return undefined
      req.autoRun = true
      const adv = (req.advance ??= {})
      adv.pausedReason = undefined
      adv.noopStreak = 0
      req.comments.push({
        id: deps.ids.comment(),
        body: '[人工处置] 重跑该卡：autoRun 已开启，链从下一张可跑的子卡继续',
        createdAt: now,
        createdBy: { kind: 'human' },
      })
      return { requirements: [req] }
    })
    const out = await advanceRequirement(deps, requirementId)
    return { ok: true, note: fmt('已重跑：{steps} 步，停止于 {stop}', { steps: out.steps.length, stop: out.stopped }) }
  }
  if (choice === 'upstream') {
    await deps.repo.mutate('failure-upstream', (ledger) => {
      const req = ledger.requirements.find((r) => r.id === requirementId)
      if (req === undefined) return undefined
      assertReqTransition(req.status, 'design', 'human')
      const from = req.status
      req.status = 'design'
      req.autoRun = false
      req.version += 1
      req.updatedAt = now
      req.updatedBy = { kind: 'human' }
      recordStatus(req, 'design', now, { kind: 'human' }, '返工回上游：重新描述需求')
      req.comments.push({
        id: deps.ids.comment(),
        body: fmt('[人工处置] 退回上游：{from} → design，重新描述需求后重走设计/计划/拆分（既有父卡将就地更新）', { from }),
        createdAt: now,
        createdBy: { kind: 'human' },
      })
      return { requirements: [req] }
    })
    return { ok: true, note: '已退回设计态：重新描述需求并重新提交/批准计划' }
  }
  // cancel
  await deps.repo.mutate('failure-cancel', (ledger) => {
    const req = ledger.requirements.find((r) => r.id === requirementId)
    if (req === undefined) return undefined
    assertReqTransition(req.status, 'canceled', 'human')
    const from = req.status
    req.status = 'canceled'
    req.autoRun = false
    req.version += 1
    req.updatedAt = now
    req.updatedBy = { kind: 'human' }
    recordStatus(req, 'canceled', now, { kind: 'human' }, '失败处置：取消需求')
    req.comments.push({
      id: deps.ids.comment(),
      body: fmt('[人工处置] 取消需求：{from} → canceled', { from }),
      createdAt: now,
      createdBy: { kind: 'human' },
    })
    return { requirements: [req] }
  })
  return { ok: true, note: '需求已取消' }
}
