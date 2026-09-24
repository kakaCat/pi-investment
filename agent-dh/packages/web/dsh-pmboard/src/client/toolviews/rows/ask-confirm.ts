/**
 * reqboard_ask_confirm 定制卡（REQ-c48f99 t3 / FR-2、FR-3、FR-4）。
 * 折叠行：请求确认<kind> · 已确认并推进 X→Y / 未确认（用户选择）；展开：问题、选择与意见。
 * @module dsh-pmboard/client/toolviews/rows
 */
import { strOf, firstLine, resultText, isSettled, type CardSummarize } from '../shared.ts'
import type { BizCard } from '../biz-row.ts'
import { artifactKindLabel } from '../../../shared/artifact-labels.ts'

export const askConfirmSummarize: CardSummarize = (args, result, block) => {
  const kind = strOf(args, 'kind') ?? strOf(args, 'target')
  if (kind === undefined && strOf(args, 'question') === undefined) return null
  const kindCn = kind !== undefined ? artifactKindLabel(kind) : '产物'
  const err = isSettled(block) && block.isError === true
  if (err) {
    return { icon: '❌', line: `请求确认${kindCn} 失败：${firstLine(resultText(block)).slice(0, 60)}`, isError: true, details: [['种类', kindCn]] }
  }
  const confirmed = result?.confirmed
  const advanced = result?.advanced === true
  const from = strOf(result, 'from')
  const to = strOf(result, 'to')
  let line: string
  if (confirmed === true) {
    line = `请求确认${kindCn} · 已确认${advanced && from !== undefined && to !== undefined ? `并推进 ${from}→${to}` : ''}`
  } else if (confirmed === false) {
    const choice = strOf(result, 'user_choice')
    line = `请求确认${kindCn} · 未确认${choice !== undefined ? `（${choice.slice(0, 30)}` + `）` : ''}`
  } else {
    line = `请求确认${kindCn} · 等待作答`
  }
  const details: Array<[string, string]> = [['种类', kindCn]]
  const q = strOf(args, 'question')
  if (q !== undefined) details.push(['问题', q.slice(0, 400)])
  const fb = strOf(result, 'user_feedback')
  if (fb !== undefined) details.push(['用户意见', fb])
  return { icon: '🔔', line, details }
}

export const askConfirmCard: BizCard = { key: 'reqboard_ask_confirm', title: '确认弹框', icon: '🔔', summarize: askConfirmSummarize }
