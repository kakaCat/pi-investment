/**
 * 会话分类器：首条消息 vs 全部 open 需求/任务做启发式打分。
 * v1 从简：分词 token 重叠 + 标签加权 + 工作区路径一致性（预留）。
 * 不上 LLM（hook 路径低延迟、可解释）。
 *
 * @module dashboard-requirement/host/classifier
 */
import type { RequirementRecord, TaskRecord, TriageRecord } from '../shared/protocol.js'

/** 分词：英文按单词（\w+），中文按单字（\u4e00-\u9fa5），转小写。 */
function tokenize(text: string): string[] {
  const tokens: string[] = []
  const regex = /\w+|[\u4e00-\u9fa5]/g
  let m: RegExpExecArray | null
  while ((m = regex.exec(text)) !== null) {
    tokens.push(m[0].toLowerCase())
  }
  return tokens
}

function overlapScore(a: string, b: string): number {
  const ta = new Set(tokenize(a))
  const tb = new Set(tokenize(b))
  if (ta.size === 0 || tb.size === 0) return 0
  let common = 0
  for (const w of ta) if (tb.has(w)) common++
  return Math.round((common / Math.min(ta.size, tb.size)) * 100)
}

export interface ClassifyResult {
  action: 'create_req' | 'bind_req' | 'bind_task'
  targetId?: string
  score: number
}

/**
 * 对一条会话首条消息做分类建议。
 * @param text - 首条消息文本
 * @param requirements - open 需求（非 archived/canceled）
 * @param tasks - open 任务（非 done/canceled）
 * @returns 最佳建议
 */
export function classifySession(
  text: string,
  requirements: readonly RequirementRecord[],
  tasks: readonly TaskRecord[],
): ClassifyResult {
  const openReqs = requirements.filter(r => r.status !== 'archived' && r.status !== 'canceled')
  const openTasks = tasks.filter(t => t.status !== 'done' && t.status !== 'canceled')

  let best: ClassifyResult = { action: 'create_req', score: 0 }

  for (const req of openReqs) {
    const corpus = [req.title, req.description, req.docLinks?.requirement ?? ''].join(' ')
    const score = overlapScore(text, corpus)
    if (score > best.score) best = { action: 'bind_req', targetId: req.id, score }
  }

  for (const task of openTasks) {
    const corpus = [task.title, task.description, task.context, task.acceptance].join(' ')
    const score = overlapScore(text, corpus)
    if (score > best.score) best = { action: 'bind_task', targetId: task.id, score }
  }

  return best
}
