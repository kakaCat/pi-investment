/**
 * reqboard_task_move 定制卡（REQ-c48f99 t2 / FR-2、FR-3）。
 * 折叠行：`t-xxx → 完工`（icon 随 to 变；error 红）；展开体：from→to、理由、需求状态。
 * @module dsh-pmboard/client/toolviews/rows/task-move
 */
import {
  cnLabel, strOf, firstLine, resultText, isSettled,
  TASK_MOVE_TO, type CardSummarize,
} from '../shared.ts'
import type { BizCard } from '../biz-row.ts'

/** 游离纯函数（单测直接测它）。 */
export const taskMoveSummarize: CardSummarize = (args, result, block) => {
  const taskId = strOf(args, 'task_id') ?? strOf(result, 'task_id')
  const to = strOf(args, 'to') ?? strOf(result, 'to')
  if (taskId === undefined && to === undefined) return null

  const from = strOf(result, 'from')
  const err = isSettled(block) && block.isError === true
  const toCn = cnLabel(TASK_MOVE_TO, to)
  const id = taskId ?? '?'

  if (err) {
    const why = resultHeadlineOr(block)
    return {
      icon: '❌',
      line: `${id} 推进失败${why !== '' ? `：${why.slice(0, 60)}` : ''}`,
      isError: true,
      details: buildDetails(id, from, to, toCn, args, result),
    }
  }
  const icon = to === 'done' ? '✅' : to === 'canceled' ? '🚫' : to === 'todo' ? '↩️' : '🔀'
  const trans = from !== undefined
    ? `（${cnLabel(TASK_MOVE_TO, from) ?? from} → ${toCn ?? to ?? ''}）`
    : ''
  return {
    icon,
    line: `${id} → ${toCn ?? to ?? '?'}${trans}`,
    details: buildDetails(id, from, to, toCn, args, result),
  }
}

function resultHeadlineOr(block: Parameters<CardSummarize>[2]): string {
  const text = resultText(block).trim()
  if (text === '') return ''
  return firstLine(text)
}

function buildDetails(
  id: string,
  from: string | undefined,
  to: string | undefined,
  toCn: string | undefined,
  args: Record<string, unknown> | undefined,
  result: Record<string, unknown> | undefined,
): Array<[string, string]> {
  const rows: Array<[string, string]> = [['任务', id]]
  if (from !== undefined || to !== undefined) {
    rows.push(['状态迁移', `${cnLabel(TASK_MOVE_TO, from) ?? from ?? '?'} → ${toCn ?? to ?? '?'}`])
  }
  const reason = strOf(args, 'reason')
  if (reason !== undefined) rows.push(['理由', reason])
  const reqStatus = strOf(result, 'requirement_status')
  if (reqStatus !== undefined) rows.push(['需求状态', reqStatus])
  return rows
}

export const taskMoveCard: BizCard = {
  key: 'reqboard_task_move',
  title: '任务推进',
  icon: '🔀',
  summarize: taskMoveSummarize,
}
