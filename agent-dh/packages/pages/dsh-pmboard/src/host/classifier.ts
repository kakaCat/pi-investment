/**
 * 会话分类器：三层架构（显式标记 → LLM 精准 → 启发式兜底）。
 *
 * 用户明确（2026-09-0x 定稿）：
 * 1. 窗口消息带 #REQ-xxx / #t-xxx 显式标记 → 直接绑定，不走 LLM
 * 2. 无标记 → 真实 LLM（hook 注入提示词）判断：
 *    - 全库（跨窗口）语义命中已有需求/任务 → bind
 *    - 否则（该窗口此刻没有可对应的需求）→ create：新建需求 + 分类 + 建议标题
 * 3. LLM 失败/不可用 → 规则模拟（无 callLlm 时保持 v1 行为）→ 启发式兜底
 *
 * 窗口↔需求是 n:n：bind 判定不局限于本窗口已立需求，而是对全部 open
 * 需求/任务做语义匹配（窗口 B 可续做窗口 A 立的需求，任务可在多窗口执行）。
 *
 * @module dsh-pmboard/host/classifier
 */
import type { RequirementRecord, TaskRecord, RequirementCategory } from '../shared/protocol.js'

// ---------------------------------------------------------------------------
// 消息清洗：剔除 harness 注入的系统块（system-reminder / runtime context /
// checkpoint 快照 / 提示词注入等），避免把系统噪声当成对话内容立项。
// ---------------------------------------------------------------------------

const NOISE_BLOCK_RE = /<system-reminder>[\s\S]*?<\/system-reminder>/g

/** 段落级噪声判据（注入块首行特征）。 */
function isNoiseParagraph(p: string): boolean {
  const s = p.trim()
  if (s.length === 0) return true
  if (/^<system-reminder>/i.test(s)) return true
  if (/^<\/?system-reminder>/.test(s)) return true
  if (/^Current runtime context/i.test(s)) return true
  if (/^Current DSH file policy/i.test(s)) return true
  if (/^Approval prompts? (are|is) disabled/i.test(s)) return true
  if (/^This is an automatically generated checkpoint/i.test(s)) return true
  if (/^\[compacted-summary\]/i.test(s)) return true
  if (/^\[genome:/i.test(s)) return true
  if (/^Treat the captured context/i.test(s)) return true
  if (/^The available skill catalog/i.test(s)) return true
  if (/^Available skills?:/i.test(s)) return true
  if (/^Tool results?[:：]/i.test(s)) return true
  return false
}

/**
 * 清洗用户消息文本：剥掉系统注入块与前置噪声段落，返回真实对话内容。
 * 若整段都是噪声返回空串（调用方应跳过分类，不建 triage 不立项）。
 */
export function cleanUserMessageText(raw: unknown): string {
  if (typeof raw !== 'string') return ''
  let text = raw.replace(NOISE_BLOCK_RE, '')
  // 逐段过滤：保留非噪声、非 markdown 结构标题的段落
  const kept: string[] = []
  for (const para of text.split(/\n{2,}/)) {
    const trimmed = para.trim()
    if (trimmed.length === 0) continue
    if (isNoiseParagraph(trimmed)) continue
    kept.push(trimmed)
  }
  let out = kept.join('\n\n').trim()
  // 进一步剥掉残余的 runtime-context 尾部（同一段内跟在正文后的注入句）
  const ctxIdx = out.search(/Current runtime context/i)
  if (ctxIdx > 20) out = out.slice(0, ctxIdx).trim() // 只当它出现在正文中后部才截断
  return out
}

/** 首行截断为建议标题（规则兜底用）。 */
export function titleFromCleanedText(text: string, max = 60): string {
  const firstLine = text.split(/\n/)[0]?.trim() ?? ''
  return firstLine.slice(0, max)
}

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
// 第 2 层：LLM 精准分类（真实 LLM + 规则模拟降级）
// ---------------------------------------------------------------------------

export interface LlmClassifyInput {
  /** 待分类的用户消息文本（已清洗；不是清洗则 hook 层负责） */
  firstMessage: string
  requirements: Array<{ id: string; title: string; description: string; status: string }>
  tasks: Array<{ id: string; title: string; context: string; phase: string; status: string }>
  /** 本窗口已立项的需求 id（延续优先提示；bind 判定仍跨全库） */
  windowRequirementIds?: string[]
  /** 发起分类的窗口（审计与提示词上下文） */
  sessionId?: string
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

export type LlmRole = 'system' | 'user'
export interface LlmTurn {
  role: LlmRole
  content: string
}
/** host 侧注入的 LLM 文本调用器（消息数组 → 纯文本回答；异常即失败）。 */
export type LlmTextCaller = (turns: LlmTurn[]) => Promise<string>

const CATEGORY_VALUES: readonly string[] = ['feature', 'bug', 'doc', 'refactor', 'spike', 'chore']

// ---------------------------------------------------------------------------
// hook 提示词（用户在回路前，LLM 看到的本窗口与全库上下文）
// ---------------------------------------------------------------------------

/** 立项助手系统提示词：让"这个窗口"知道自己要绑定已有或创建项目/需求。 */
export function buildClassifySystemPrompt(): string {
  return [
    '你是看板立项助手。你的任务：判断一条来自 GUI 对话窗口的用户消息应如何归入项目看板。',
    '判定规则（按优先级）：',
    '1. 绑定已有（bind_req / bind_task）：消息与**任意**未完结需求/任务语义延续——包括其他窗口创建的（窗口↔需求是多对多：',
    '   一个需求的任务可以由多个窗口执行）。若命中给出精确 targetId。',
    '2. 新建需求（create_req）：窗口此刻没有任何可对应的需求/任务（全库语义都不匹配），且消息表达了一段',
    '   具体、可执行的工作（功能/缺陷/文档/重构/调研/杂务）。给出 category + 简洁中文标题 + 一句话理由。',
    '3. 不立项（confidence 给 <30 且 action=create_req）：寒暄、纯确认、纯提问、与工作无关、空内容——不得立项。',
    '输出**严格 JSON 单对象**（不要 Markdown 围栏、不要多余文字）：',
    '{ "action": "create_req|bind_req|bind_task", "targetId": "REQ-xxxxxx 或 t-xxxxxx（bind 时必填）", "confidence": 0-100 整数, "reason": "一句话中文理由", "category": "feature|bug|doc|refactor|spike|chore（create 时填）", "suggestedTitle": "建议标题，中文，≤40字（create 时填）" }',
    '类别语义：feature=新功能 bug=缺陷修复 doc=文档 refactor=重构/优化 spike=调研/验证 chore=杂务/维护。',
  ].join('\n')
}

/** 组装用户提示词：现有需求/任务清单（全库）+ 本窗口已立项提示 + 待分类消息。 */
export function buildClassifyUserPrompt(input: LlmClassifyInput): string {
  const { firstMessage, requirements, tasks, windowRequirementIds, sessionId } = input
  const openReqs = requirements.filter(r => r.status !== 'archived' && r.status !== 'canceled')
  const openTasks = tasks.filter(t => t.status !== 'done' && t.status !== 'canceled')

  const reqLines = openReqs.map(r => `- ${r.id} | ${r.status} | ${r.title} | ${(r.description ?? '').slice(0, 80)}`)
  const taskLines = openTasks.map(t => `- ${t.id} | ${t.title} | ${(t.context ?? '').slice(0, 60)}`)

  const windowHint = (windowRequirementIds?.length ?? 0) > 0
    ? `本窗口已立项的需求（延续它优先）：${windowRequirementIds!.join(', ')}`
    : '本窗口尚未立项任何需求。'

  return [
    `窗口标识：${sessionId ?? '(未知)'}`,
    windowHint,
    '--- 全库未完结需求 ---',
    reqLines.length > 0 ? reqLines.join('\n') : '（无）',
    '--- 全库未完结任务 ---',
    taskLines.length > 0 ? taskLines.join('\n') : '（无）',
    '--- 待分类的用户消息 ---',
    firstMessage,
    '--- 输出 JSON ---',
  ].join('\n')
}

// ---------------------------------------------------------------------------
// LLM 输出解析与校验
// ---------------------------------------------------------------------------

/** 从 LLM 回复文本提取 JSON 对象（容忍 Markdown 围栏与前后杂质）。 */
export function extractJsonObject(text: string): Record<string, unknown> {
  let t = text.trim()
  t = t.replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/, '')
  const start = t.indexOf('{')
  const end = t.lastIndexOf('}')
  if (start === -1 || end === -1 || end <= start) throw new Error(`LLM 输出无 JSON 对象：${text.slice(0, 120)}`)
  return JSON.parse(t.slice(start, end + 1)) as Record<string, unknown>
}

/** 校验并规整 LLM 分类输出；不合法即抛错（调用方降级）。 */
export function normalizeClassifyOutput(
  raw: Record<string, unknown>,
  input: LlmClassifyInput,
): LlmClassifyOutput {
  const action = String(raw.action ?? '')
  if (action !== 'create_req' && action !== 'bind_req' && action !== 'bind_task') {
    throw new Error(`LLM 输出 action 非法：${action}`)
  }
  const confidenceNum = Number(raw.confidence)
  const confidence = Number.isFinite(confidenceNum) ? Math.max(0, Math.min(100, Math.round(confidenceNum))) : 0
  const reason = typeof raw.reason === 'string' ? raw.reason.slice(0, 200) : ''

  if (action === 'create_req') {
    const cat = String(raw.category ?? '')
    const category = (CATEGORY_VALUES.includes(cat) ? cat : 'feature') as RequirementCategory
    const suggestedTitle = typeof raw.suggestedTitle === 'string' && raw.suggestedTitle.trim().length > 0
      ? raw.suggestedTitle.trim().slice(0, 80)
      : titleFromCleanedText(input.firstMessage)
    if (confidence < 30) {
      // 低置信度：视为不立项（仍以 create_req 返回，hook 侧按阈值拦截）
      return { action, confidence, reason: reason || '（低置信度，不建议立项）', category, suggestedTitle }
    }
    return { action, confidence, reason, category, suggestedTitle }
  }

  // bind 分支：校验 targetId 存在于候选
  const targetId = typeof raw.targetId === 'string' ? raw.targetId.trim() : ''
  const reqIds = new Set(input.requirements.map(r => r.id))
  const taskIds = new Set(input.tasks.map(t => t.id))
  if (action === 'bind_req' && !reqIds.has(targetId)) {
    throw new Error(`LLM bind_req targetId 不在候选需求中：${targetId}`)
  }
  if (action === 'bind_task' && !taskIds.has(targetId)) {
    throw new Error(`LLM bind_task targetId 不在候选任务中：${targetId}`)
  }
  return { action, targetId, confidence, reason }
}

// ---------------------------------------------------------------------------
// 第 2 层入口：有 callLlm → 真实 LLM；无 → 规则模拟（兼容旧调用方与测试）
// ---------------------------------------------------------------------------

/** 规则模拟 LLM（无 LLM 时的兜底分类；仅标题包含/关键词命中才绑定）。 */
export function classifySessionLlmRule(input: LlmClassifyInput): LlmClassifyOutput {
  const { firstMessage, requirements, tasks } = input

  for (const req of requirements) {
    if (firstMessage.includes(req.title) || (req.title.length > 0 && req.title.includes(firstMessage.slice(0, 20)))) {
      return { action: 'bind_req', targetId: req.id, confidence: 90, reason: `消息语义匹配需求"${req.title}"` }
    }
  }

  for (const task of tasks) {
    const keywords = task.context.split(/[,，\s]+/).filter(w => w.length >= 2)
    const matched = keywords.filter(k => firstMessage.includes(k)).length
    if (matched >= 2 || (matched >= 1 && firstMessage.includes(task.title))) {
      return { action: 'bind_task', targetId: task.id, confidence: 85, reason: `上下文语义匹配任务"${task.title}"` }
    }
  }

  let category: RequirementCategory = 'feature'
  if (/bug|修复|报错|异常|崩溃|error|fix/i.test(firstMessage)) category = 'bug'
  else if (/文档|doc|readme|说明|注释/i.test(firstMessage)) category = 'doc'
  else if (/重构|优化|整理|clean|refactor/i.test(firstMessage)) category = 'refactor'
  else if (/调研|研究|spike|验证/i.test(firstMessage)) category = 'spike'
  else if (/维护|升级|依赖|chore|杂务/i.test(firstMessage)) category = 'chore'

  const suggestedTitle = titleFromCleanedText(firstMessage)

  return {
    action: 'create_req',
    confidence: 75,
    reason: '与现有需求/任务语义关联度低，建议新建',
    category,
    suggestedTitle,
  }
}

export interface ClassifyLlmOptions {
  /** 真实 LLM 文本调用器；缺省则退回规则模拟 */
  callLlm?: LlmTextCaller
}

export async function classifySessionLlm(
  input: LlmClassifyInput,
  options?: ClassifyLlmOptions,
): Promise<LlmClassifyOutput> {
  if (typeof options?.callLlm !== 'function') {
    return classifySessionLlmRule(input)
  }
  const system = buildClassifySystemPrompt()
  const user = buildClassifyUserPrompt(input)
  const rawText = await options.callLlm([
    { role: 'system', content: system },
    { role: 'user', content: user },
  ])
  const parsed = extractJsonObject(rawText)
  return normalizeClassifyOutput(parsed, input)
}
