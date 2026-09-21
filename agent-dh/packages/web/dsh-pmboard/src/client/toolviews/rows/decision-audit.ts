/**
 * decision_audit 定制卡（REQ-c48f99 t3 / FR-2、FR-3、FR-4）。
 * 折叠行：决策留痕 · <类型> · <标的>；展开：推理、参数。
 * @module dsh-pmboard/client/toolviews/rows
 */
import { strOf, firstLine, resultText, isSettled, cnLabel, AUDIT_ACTION, type CardSummarize } from '../shared.ts'
import type { BizCard } from '../biz-row.ts'

export const decisionAuditSummarize: CardSummarize = (args, result, block) => {
  const action = strOf(args, 'action')
  if (action === undefined) return null
  const err = isSettled(block) && block.isError === true
  if (err) return { icon: '❌', line: `决策审计失败：${firstLine(resultText(block)).slice(0, 60)}`, isError: true }
  const actionCn = cnLabel(AUDIT_ACTION, action) ?? action
  const dtype = strOf(args, 'decision_type') ?? strOf(args, 'decision_subtype')
  const params = args?.parameters as Record<string, unknown> | undefined
  const entity = strOf(args, 'related_entity_id') ?? strOf(params, 'symbol')
  const line = `决策${actionCn}${dtype !== undefined ? ` · ${dtype}` : ''}${entity !== undefined ? ` · ${entity}` : ''}`
  const details: Array<[string, string]> = []
  const reasoning = strOf(args, 'reasoning')
  if (reasoning !== undefined) details.push(['推理', reasoning.slice(0, 400)])
  if (params !== undefined) {
    details.push(['参数', JSON.stringify(params).slice(0, 300)])
  }
  const decisionId = strOf(result, 'decision_id')
  if (decisionId !== undefined) details.push(['决策 ID', decisionId])
  return { icon: '📝', line, details }
}

export const decisionAuditCard: BizCard = { key: 'decision_audit', title: '决策审计', icon: '📝', summarize: decisionAuditSummarize }
