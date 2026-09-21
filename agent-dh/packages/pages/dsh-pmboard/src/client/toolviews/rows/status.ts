/**
 * reqboard_status 定制卡（REQ-c48f99 t3 / FR-2、FR-3、FR-4）。
 * 折叠行：看板 · 未绑定 / N 个进行中需求；展开：需求清单、可推进动作。
 * @module dsh-pmboard/client/toolviews/rows
 */
import { numOf, firstLine, resultText, isSettled, type CardSummarize } from '../shared.ts'
import type { BizCard } from '../biz-row.ts'

interface OpenReq { id?: string; title?: string; status?: string }

export const statusSummarize: CardSummarize = (_args, result, block) => {
  if (result === undefined && !isSettled(block)) {
    return { icon: '📊', line: '看板状态（查询中…）' }
  }
  if (result === undefined) return null
  const err = isSettled(block) && block.isError === true
  if (err) return { icon: '❌', line: `看板状态查询失败：${firstLine(resultText(block)).slice(0, 60)}`, isError: true }
  const bound = result.bound === true
  const openCount = numOf(result, 'open_count') ?? 0
  const reqs = (Array.isArray(result.open_requirements) ? result.open_requirements : []) as OpenReq[]
  const line = bound
    ? `看板 · ${openCount} 个进行中需求${reqs[0]?.id !== undefined ? `（${reqs[0].id}${reqs[0].status !== undefined ? ' ' + reqs[0].status : ''}）` : ''}`
    : '看板 · 未绑定需求'
  const details: Array<[string, string]> = []
  if (reqs.length > 0) {
    details.push(['进行中需求', reqs.map(r => `${r.id ?? '?'} ${r.title ?? ''}（${r.status ?? '?'}）`).join('\n')])
  }
  const actions = Array.isArray(result.next_actions) ? result.next_actions : []
  if (actions.length > 0) details.push(['可推进', actions.map(String).join('、')])
  const unreceived = Array.isArray(result.unreceived_clauses) ? result.unreceived_clauses : []
  if (unreceived.length > 0) details.push(['未接收条款', unreceived.map(String).join('、')])
  return { icon: '📊', line, details }
}

export const statusCard: BizCard = { key: 'reqboard_status', title: '看板状态', icon: '📊', summarize: statusSummarize }
