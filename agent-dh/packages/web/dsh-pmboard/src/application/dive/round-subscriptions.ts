/**
 * Dive 服务的**回合事件接线**（REQ-260926215013-1568 T-5 · serves: FR-1, FR-2, FR-5, FR-6, FR-9, FR-11）。
 *
 * 从 ReqboardDiveManager 抽出：Service 构造依赖真 cordis ctx（单测不便），而"订阅哪七个事件、
 * 各交给 round 半哪个入口、订阅失败如何响亮"是纯接线逻辑——独立成模块后可被单测直接驱动。
 *
 * @module dsh-pmboard/application/dive/round-subscriptions
 */
import type { DiveRoundDriver } from './round-driver.js'

export interface EventBusLike {
  on?: (event: string, listener: (...args: unknown[]) => unknown) => (() => void) | void
}
export interface WireLogger {
  debug(message: string): void
  warn(message: string, err?: unknown): void
}

/** round 半接管的宿主事件（任一订阅失败 = 对应纪律静默停摆 → 必须响亮）。 */
export const DIVE_ROUND_EVENTS: readonly string[] = [
  'agent/pre-step',
  'agent/inbox/inserted',
  'agent/inbox/claimed',
  'agent/inbox/discarded',
  'agent/error',
  'agent/disposed',
  'reqboard/requirement-moved',
]

function agentOf(payload: unknown): unknown {
  return (payload as { agent?: unknown } | undefined)?.agent
}
function messageOf(payload: unknown): unknown {
  return (payload as { message?: unknown } | undefined)?.message
}

/** 把七个宿主事件接到 round 半；返回合并解绑函数。订阅失败按「响亮」留痕（不静默降级）。 */
export function wireDiveRoundSubscriptions(bus: EventBusLike, driver: DiveRoundDriver, logger: WireLogger): () => void {
  const offs: Array<() => void> = []
  const sub = (event: string, listener: (...args: unknown[]) => unknown): void => {
    let off: (() => void) | void
    try {
      off = bus.on?.(event, listener)
    } catch (err) {
      logger.warn('dive-manager 订阅 ' + event + ' 抛错——该路径静默停摆', err)
      return
    }
    if (typeof off === 'function') {
      offs.push(off)
      logger.debug('dive-manager 订阅 ' + event + ' ok')
    } else {
      logger.warn('dive-manager 订阅 ' + event + ' 未成立（宿主未提供 ctx.on / 未返回解绑函数）——该路径静默停摆')
    }
  }
  sub('agent/pre-step', (payload, next) => {
    const p = (payload ?? {}) as { agent?: unknown; messages?: unknown[]; signal?: unknown }
    return driver.onPreStep(p.agent, p.messages ?? [], p.signal as never, next as never)
  })
  sub('agent/inbox/inserted', (payload) => driver.onInboxInserted(agentOf(payload), messageOf(payload)))
  sub('agent/inbox/claimed', (payload) => driver.onInboxClaimed(agentOf(payload), messageOf(payload)))
  sub('agent/inbox/discarded', (payload) => driver.onInboxDiscarded(agentOf(payload), messageOf(payload)))
  sub('agent/error', (payload) => driver.onAgentError(agentOf(payload)))
  sub('agent/disposed', (payload) => driver.onAgentDisposed(agentOf(payload)))
  sub('reqboard/requirement-moved', (payload) => driver.onRequirementMoved(String((payload as { requirementId?: unknown } | undefined)?.requirementId ?? '')))
  return () => {
    for (const off of offs) {
      try { off() } catch { /* 解绑失败不抛 */ }
    }
  }
}
