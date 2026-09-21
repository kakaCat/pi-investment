/**
 * bizToolviews —— 业务工具定制卡片注册入口（REQ-c48f99 t2 / FR-1）。
 *
 * 经 tool.call.toolview keyed 插槽注册（ui-tool ask-question-toolview 同款模式）；
 * 每张卡注册失败互不影响（逐卡 try/catch），整体失败不拖垮 pmboard client。
 * @module dsh-pmboard/client/toolviews
 */
import { makeBizRow, type BizCard, type BizRowProps } from './biz-row.ts'
import { taskMoveCard } from './rows/task-move.ts'
import { submitCard } from './rows/submit.ts'
import { askConfirmCard } from './rows/ask-confirm.ts'
import { statusCard } from './rows/status.ts'
import { captureCard } from './rows/capture.ts'
import { memoryWriteCard } from './rows/memory-write.ts'
import { decisionAuditCard } from './rows/decision-audit.ts'
import { tradeCard } from './rows/trade.ts'
import { watchCard } from './rows/watch-manage.ts'

interface SlotsLike {
  inject(slot: string, thunk: () => unknown): unknown
  register(options: Record<string, unknown>, occupant: unknown): unknown
}

/** 首批卡片清单（REQ-c48f99 首批 9 张）。 */
export const BIZ_CARDS: readonly BizCard[] = [
  taskMoveCard, submitCard, askConfirmCard, statusCard, captureCard,
  memoryWriteCard, decisionAuditCard, tradeCard, watchCard,
]

/** 把全部业务卡片注册进 tool.call.toolview 插槽。 */
export function registerBizToolviews(slots: SlotsLike): number {
  let registered = 0
  for (const card of BIZ_CARDS) {
    try {
      const Row = makeBizRow(card)
      slots.inject('tool.call.toolview', () =>
        slots.register(
          { name: 'tool.call.toolview', key: card.key, locale: 'conversation' },
          (props: BizRowProps) => Row(props),
        ),
      )
      registered += 1
    } catch (e) {
      console.error(`[dsh-pmboard] toolview 注册失败: ${card.key}`, e)
    }
  }
  return registered
}
