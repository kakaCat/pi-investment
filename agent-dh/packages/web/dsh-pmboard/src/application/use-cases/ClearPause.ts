/**
 * ClearPause 用例（REQ-260925212722-96e7）
 *
 * 清除 Dive 模式的 armed 状态，允许手动操作。
 *
 * @module dsh-pmboard/application/use-cases/ClearPause
 */
import type { UseCaseDeps } from '../ports.js'
import { normalizeText } from '../../shared/protocol.js'
import { openRequirementsFor } from '../internal/window.js'

export interface ClearPauseArgs {
  requirement_id?: string
}

export interface ClearPauseResult {
  success: boolean
  requirement_id: string
  previous_activation?: string
  message: string
}

/**
 * 清除 Dive 模式暂停，解除 armed 锁定
 */
export async function clearPause(
  deps: UseCaseDeps,
  windowKey: string,
  args: ClearPauseArgs
): Promise<ClearPauseResult> {
  const reject = (msg: string, code: string): never => {
    throw Object.assign(new Error(msg), { code })
  }

  // 1. 获取目标需求
  const explicitId = normalizeText(args.requirement_id, 'requirement_id', 64)
  const snapshot = deps.repo.snapshot()
  const bound = openRequirementsFor(snapshot, windowKey)
  
  if (bound.length === 0) {
    reject('reqboard_clear_pause 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
  }
  
  const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
  if (target === undefined) {
    reject(
      'reqboard_clear_pause 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求',
      'REQBOARD_NOT_BOUND_TO_WINDOW'
    )
  }

  // 2. 执行清除
  const result = await deps.repo.mutate('dive-cleared', (ledger) => {
    const req = ledger.requirements.find(r => r.id === target.id)
    if (req === undefined) return undefined

    const previousActivation = req.dive?.activation

    // 清除 Dive 状态
    if (!req.dive) {
      req.dive = {
        activation: 'disarmed',
        phase: 'idle',
        roundsInStage: 0
      }
    } else {
      req.dive.activation = 'disarmed'
      req.dive.phase = 'idle'
      req.dive.pausedReason = undefined
    }

    // 记录解锁日志
    const now = deps.clock.now()
    const commentId = deps.ids.comment()
    req.comments.push({
      id: commentId,
      text: `Dive 模式已解除锁定（reqboard_clear_pause）。之前状态：${previousActivation || 'none'}`,
      createdAt: now,
      createdBy: { kind: 'agent', sessionId: windowKey }
    })

    req.version += 1
    req.updatedAt = now
    req.updatedBy = { kind: 'agent', sessionId: windowKey }

    return { previousActivation }
  })

  if (result === undefined) {
    reject('reqboard_clear_pause 未执行：需求未找到或数据冲突', 'REQBOARD_MUTATION_FAILED')
  }

  return {
    success: true,
    requirement_id: target.id,
    previous_activation: result.previousActivation,
    message: `需求 ${target.id} 的 Dive 模式已解除锁定，现在可以手动操作了。`
  }
}
