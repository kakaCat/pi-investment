/**
 * reqboard_submit 定制卡（REQ-c48f99 t3 / FR-2、FR-3、FR-4）。
 * 折叠行：提交<种类> · REQ-xxx（+结果态）；展开：摘要、证据清单。
 * @module dsh-pmboard/client/toolviews/rows
 */
import { strOf, numOf, firstLine, resultText, isSettled, cnLabel, SUBMIT_KIND, type CardSummarize } from '../shared.ts'
import type { BizCard } from '../biz-row.ts'

export const submitSummarize: CardSummarize = (args, result, block) => {
  const kind = strOf(args, 'kind')
  if (kind === undefined) return null
  const kindCn = cnLabel(SUBMIT_KIND, kind) ?? kind
  const reqId = strOf(args, 'requirement_id') ?? strOf(result, 'requirement_id')
  const err = isSettled(block) && block.isError === true
  if (err) {
    return { icon: '❌', line: `提交${kindCn} 失败：${firstLine(resultText(block)).slice(0, 60)}`, isError: true,
      details: [['种类', kindCn]] }
  }
  const status = strOf(result, 'status') ?? strOf(result, 'plan_status')
  return {
    icon: '📄',
    line: `提交${kindCn}${reqId !== undefined ? ` · ${reqId}` : ''}${status !== undefined ? ` → ${status}` : ''}`,
    details: [
      ['种类', kindCn],
      ...(strOf(args, 'summary') !== undefined ? [['摘要', strOf(args, 'summary')!.slice(0, 300)] as [string, string]] : []),
      ...(Array.isArray(args?.evidence) ? [['证据', (args!.evidence as unknown[]).map(String).join('\n').slice(0, 500)] as [string, string]] : []),
      ...(numOf(result, 'task_count') !== undefined ? [['任务数', String(numOf(result, 'task_count'))] as [string, string]] : []),
    ],
  }
}

export const submitCard: BizCard = { key: 'reqboard_submit', title: '提交产物', icon: '📄', summarize: submitSummarize }
