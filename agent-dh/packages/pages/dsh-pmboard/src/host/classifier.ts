/**
 * 会话分类器：三层架构（显式标记 → LLM 精准 → 启发式兜底）。
 * 
 * 用户明确：
 * 1. 有 #REQ-xxx / #t-xxx 标记 → 直接绑定，不走 LLM
 * 2. 无标记 → LLM 判断：能挂靠的挂靠，需新建的新建 + 需求分类
 * 3. LLM 失败 → 启发式兜底
 * 
 * @module dsh-pmboard/host/classifier
 */
import type { RequirementRecord, TaskRecord, TriageRecord, RequirementCategory } from '../shared/protocol.js'

// ---------------------------------------------------------------------------
// 第 0 层：显式标记检测（最高优先级，无需 LLM）
// ---------------------------------------------------------------------------

const EXPLICIT_REQ_REGEX = /#(REQ-[0-9a-f]{6})/gi
const EXPLICIT_TASK_REGEX = /#(t-[0-9a-f]{6})/gi

export interface ExplicitMatch {
  kind: 'req' | 'task'
  id: string
}

/** 从文本提取显式标记（#REQ-xxx / #t-xxx）。 */
export function extractExplicitId(text: string): ExplicitMatch | undefined {
  const reqMatch = EXPLICIT_REQ_REGEX.exec(text)
  if (reqMatch) return { kind: 'req', id: reqMatch[1] }
  const taskMatch = EXPLICIT_TASK_REGEX.exec(text)
  if (taskMatch) return { kind: 'task', id: taskMatch[1] }
  return undefined
}

// ---------------------------------------------------------------------------
// 第 1 层：启发式分类器（兜底，token 重叠）
// ---------------------------------------------------------------------------

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

export interface HeuristicResult {
  action: 'create_req' | 'bind_req' | 'bind_task'
  targetId?: string
  score: number
}

export function classifySessionHeuristic(
  text: string,
  requirements: readonly RequirementRecord[],
  tasks: readonly TaskRecord[],
): HeuristicResult {
  const openReqs = requirements.filter(r => r.status !== 'archived' && r.status !== 'canceled')
  const openTasks = tasks.filter(t => t.status !== 'done' && t.status !== 'canceled')

  let best: HeuristicResult = { action: 'create_req', score: 0 }

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

// ---------------------------------------------------------------------------
// 第 2 层：LLM 精准分类（语义理解 + 需求分类）
// ---------------------------------------------------------------------------

export interface LlmClassifyInput {
  firstMessage: string
  requirements: Array<{ id: string; title: string; description: string; status: string }>
  tasks: Array<{ id: string; title: string; context: string; phase: string; status: string }>
}

export interface LlmClassifyOutput {
  action: 'create_req' | 'bind_req' | 'bind_task'
  targetId?: string
  confidence: number // 0-100
  reason: string
  /** 新建需求时的分类（仅 action=create_req 时有效） */
  category?: RequirementCategory
  /** 建议的需求标题（仅 action=create_req 时有效） */
  suggestedTitle?: string
}

/**
 * LLM 精准分类（异步）。
 * v1 用规则模拟，v2 接入真实 DeepSeek API。
 * 
 * Prompt 设计（真实 LLM 时）：
 * "给定以下需求列表和任务列表，判断新会话内容应：
 *  A) 绑定到已有需求/任务（给出 id）
 *  B) 新建需求（给出分类：feature/bug/doc/refactor/spike/chore + 建议标题）
 *  输出 JSON：{ action, targetId?, confidence, reason, category?, suggestedTitle? }"
 */
export async function classifySessionLlm(
  input: LlmClassifyInput,
  _options?: { apiKey?: string; model?: string },
): Promise<LlmClassifyOutput> {
  const { firstMessage, requirements, tasks } = input

  // 模拟 LLM：显式标题包含 → 绑定
  for (const req of requirements) {
    if (firstMessage.includes(req.title) || req.title.includes(firstMessage.slice(0, 20))) {
      return { action: 'bind_req', targetId: req.id, confidence: 90, reason: `消息语义匹配需求"${req.title}"` }
    }
  }

  // 模拟：任务上下文匹配
  for (const task of tasks) {
    const keywords = task.context.split(/[,，\s]+/).filter(w => w.length >= 2)
    const matched = keywords.filter(k => firstMessage.includes(k)).length
    if (matched >= 2 || (matched >= 1 && firstMessage.includes(task.title))) {
      return { action: 'bind_task', targetId: task.id, confidence: 85, reason: `上下文语义匹配任务"${task.title}"` }
    }
  }

  // 模拟：新建需求 + 分类（基于关键词规则）
  let category: RequirementCategory = 'feature'
  if (/bug|修复|报错|异常|崩溃|error|fix/i.test(firstMessage)) category = 'bug'
  else if (/文档|doc|readme|说明|注释/i.test(firstMessage)) category = 'doc'
  else if (/重构|优化|整理|clean|refactor/i.test(firstMessage)) category = 'refactor'
  else if (/调研|调研|spike|调研|研究/i.test(firstMessage)) category = 'spike'

  const suggestedTitle = firstMessage.split(/[。！？\n]/)[0].slice(0, 50).trim()

  return {
    action: 'create_req',
    confidence: 75,
    reason: '与现有需求/任务语义关联度低，建议新建',
    category,
    suggestedTitle,
  }
}
