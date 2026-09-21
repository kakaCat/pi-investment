/**
 * reqboard_capture 定制卡（REQ-c48f99 t3 / FR-2、FR-3、FR-4）。
 * 折叠行：立项 · <需求名>（或弹框待答）；展开：分类/难度、立项依据。
 * @module dsh-pmboard/client/toolviews/rows
 */
import { strOf, firstLine, resultText, isSettled, type CardSummarize } from '../shared.ts'
import type { BizCard } from '../biz-row.ts'

export const captureSummarize: CardSummarize = (args, result, block) => {
  const err = isSettled(block) && block.isError === true
  if (err) return { icon: '❌', line: `立项失败：${firstLine(resultText(block)).slice(0, 60)}`, isError: true }
  const answers = result?.answers as Record<string, unknown> | undefined
  const title = strOf(answers ?? undefined, 'title')
    ?? strOf(result, 'title')
    ?? (Array.isArray(args?.title_options) ? String((args!.title_options as unknown[])[0] ?? '') : undefined)
  const reqId = strOf(result, 'requirement_id')
  if (title === undefined && reqId === undefined) {
    if (!isSettled(block)) return { icon: '🌱', line: '立项弹框 · 等待作答' }
    return null
  }
  const line = reqId !== undefined && reqId !== ''
    ? `立项 · ${title ?? reqId} → ${reqId}`
    : `立项弹框 · ${title ?? '待答'}`
  const details: Array<[string, string]> = []
  const category = strOf(answers ?? undefined, 'category')
  const difficulty = strOf(answers ?? undefined, 'difficulty')
  if (category !== undefined || difficulty !== undefined) {
    details.push(['分类/难度', `${category ?? '?'} / ${difficulty ?? '?'}`])
  }
  const reason = strOf(args, 'reason')
  if (reason !== undefined) details.push(['立项依据', reason.slice(0, 400)])
  return { icon: '🌱', line, details }
}

export const captureCard: BizCard = { key: 'reqboard_capture', title: '立项', icon: '🌱', summarize: captureSummarize }
