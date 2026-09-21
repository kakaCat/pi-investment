/**
 * memory_write 定制卡（REQ-c48f99 t3 / FR-2、FR-3、FR-4）。
 * 折叠行：记忆 · <命名空间> · <内容首 40 字>；展开：全文、重要度、标签。
 * @module dsh-pmboard/client/toolviews/rows
 */
import { strOf, numOf, firstLine, resultText, isSettled, type CardSummarize } from '../shared.ts'
import type { BizCard } from '../biz-row.ts'

export const memoryWriteSummarize: CardSummarize = (args, result, block) => {
  const content = strOf(args, 'content')
  if (content === undefined) return null
  const err = isSettled(block) && block.isError === true
  if (err) return { icon: '❌', line: `写记忆失败：${firstLine(resultText(block)).slice(0, 60)}`, isError: true }
  const ns = strOf(args, 'namespace') ?? 'default'
  const tags = Array.isArray(args?.tags) ? (args!.tags as unknown[]).map(String) : []
  const head = content.replace(/\s+/g, ' ').slice(0, 40)
  const line = `记忆 · ${ns} · ${head}${content.length > 40 ? '…' : ''}`
  const details: Array<[string, string]> = [['内容', content.slice(0, 800)]]
  const imp = numOf(args, 'importance')
  if (imp !== undefined) details.push(['重要度', String(imp)])
  if (tags.length > 0) details.push(['标签', tags.map(t => '#' + t).join(' ')])
  const memId = strOf(result, 'memory_id')
  if (memId !== undefined) details.push(['记忆 ID', memId])
  return { icon: '🧠', line, details }
}

export const memoryWriteCard: BizCard = { key: 'memory_write', title: '写记忆', icon: '🧠', summarize: memoryWriteSummarize }
