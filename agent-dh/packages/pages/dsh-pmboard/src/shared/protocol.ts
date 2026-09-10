/**
 * Reqboard 共享协议：两级状态机（需求 7 主态 + 任务 6 主态）、闸门规则、
 * 任务 DAG 校验、记录形状与落库校验。host 与 client 共用本文件（零依赖）。
 *
 * 设计来源：RFC 014（agent-dh/docs/rfcs/014-requirement-board.md）。
 * 协议闸哲学沿用 dsh-taskboard：人工闸门是代码级拒绝，不是提示词约定。
 *
 * @module dsh-pmboard/shared/protocol
 */

// ---------------------------------------------------------------------------
// Actors
// ---------------------------------------------------------------------------

/** 操作者：human=人在看板操作；agent=agent 会话；system=编排器 rollup 自动推进。 */
export type ActorKind = 'human' | 'agent' | 'system'

export interface ActorRef {
  kind: ActorKind
  /** agent 操作时的会话 id（审计用） */
  sessionId?: string
}

// ---------------------------------------------------------------------------
// Requirement 状态机（RFC 014 §3）
// ---------------------------------------------------------------------------

export type RequirementStatus =
  | 'draft'        // 立项
  | 'reviewing'    // 评审（方案共创：agent 写 proposal，人机交流，人确认）
  | 'decomposing'  // 拆分（LLM 拆 DAG，人确认落库）
  | 'implementing' // 进行中（hook 驱动串行调度）
  | 'accepting'    // 验收（二层：agent 验收证据闸 → 人工验收）
  | 'done'         // 完成（归档清单齐）
  | 'archived'     // 归档（文档合并进项目文档）
  | 'canceled'

export const MAIN_REQ_STATUSES: readonly RequirementStatus[] = [
  'draft', 'reviewing', 'decomposing', 'implementing', 'accepting', 'done', 'archived',
]

export const ALL_REQ_STATUSES: readonly RequirementStatus[] = [...MAIN_REQ_STATUSES, 'canceled']

/** 需求状态合法转移表。 */
export const REQ_TRANSITIONS: Readonly<Record<RequirementStatus, readonly RequirementStatus[]>> = {
  draft: ['reviewing', 'canceled'],
  reviewing: ['decomposing', 'draft', 'canceled'],
  decomposing: ['implementing', 'reviewing', 'canceled'],
  implementing: ['accepting', 'canceled'],
  accepting: ['done', 'implementing', 'canceled'],
  done: ['archived'],
  canceled: ['draft', 'archived'],
  archived: [],
}

/**
 * 人工闸门转移（代码级仅人）：方案确认 / 拆分确认 / 人工验收 / 归档。
 * 键格式 'from>to'。agent 与 system 对这些转移一律拒绝。
 */
export const HUMAN_ONLY_REQ_TRANSITIONS: ReadonlySet<string> = new Set([
  'reviewing>decomposing', // 方案确认
  'decomposing>implementing', // 拆分 DAG 确认
  'accepting>done', // 人工验收通过
  'done>archived', // 归档
  'canceled>archived', // 取消后归档
])

/**
 * system（rollup）允许自动推进的转移白名单：其余转移 system 一律不可发起。
 *  - draft>reviewing       需求被窗口接手开工（有直接人类消息）的接手推进；
 *  - implementing>accepting 全部实施任务 done 的 rollup。
 * 人工闸门（reviewing>decomposing / decomposing>implementing / accepting>done /
 * done>archived）永不在本白名单内 —— 自动推进不可能越过人工闸门。
 */
export const SYSTEM_REQ_TRANSITIONS: ReadonlySet<string> = new Set([
  'draft>reviewing', // 窗口接手开工 → 进入评审（方案共创）
  'implementing>accepting', // 全部实施任务 done 的 rollup
])

/**
 * 会话 id → 窗口码（人类可读的短标识）。规则与 DSH 窗口编码一致：
 * `session-<uuid>` → `w-<uuid 前 8 位>`（如 session-1cee2467-95f9-… → w-1cee2467）。
 * 非标准 id 原样前缀截断，保证看板永不显示空标识。
 */
export function windowCodeFromSessionId(sessionId: string): string {
  const raw = sessionId.startsWith('session-') ? sessionId.slice('session-'.length) : sessionId
  const head = raw.split('-')[0] ?? raw
  return `w-${head.slice(0, 8)}`
}

export function canReqTransition(from: RequirementStatus, to: RequirementStatus): boolean {
  return REQ_TRANSITIONS[from].includes(to)
}

/**
 * 需求转移闸门校验。抛出带 code 的 Error：invalid_transition / human_gate / system_gate。
 */
export function assertReqTransition(from: RequirementStatus, to: RequirementStatus, actor: ActorKind): void {
  if (!canReqTransition(from, to)) {
    throw Object.assign(new Error(`需求状态不允许从 ${from} 转移到 ${to}`), { code: 'invalid_transition' })
  }
  const key = `${from}>${to}`
  if (HUMAN_ONLY_REQ_TRANSITIONS.has(key) && actor !== 'human') {
    throw Object.assign(new Error(`转移 ${from} → ${to} 是人工闸门，仅人可操作`), { code: 'human_gate' })
  }
  if (actor === 'system' && !SYSTEM_REQ_TRANSITIONS.has(key)) {
    throw Object.assign(new Error(`system 不可发起转移 ${from} → ${to}`), { code: 'system_gate' })
  }
}

// ---------------------------------------------------------------------------
// Task 状态机（RFC 014 §4）
// ---------------------------------------------------------------------------

export type TaskStatus =
  | 'todo'        // 待办（自足任务卡落库）
  | 'in_progress' // 进行中（执行会话绑定）
  | 'integrating' // 联调（前后端汇合，可跳过）
  | 'testing'     // 测试（单测输出证据）
  | 'in_review'   // 验收（等人）
  | 'done'        // 完成（仅人）
  | 'canceled'

export const MAIN_TASK_STATUSES: readonly TaskStatus[] = [
  'todo', 'in_progress', 'integrating', 'testing', 'in_review', 'done',
]

export const ALL_TASK_STATUSES: readonly TaskStatus[] = [...MAIN_TASK_STATUSES, 'canceled']

export const TASK_TRANSITIONS: Readonly<Record<TaskStatus, readonly TaskStatus[]>> = {
  todo: ['in_progress', 'canceled'],
  // in_progress→testing 直通 = 跳过联调（skipIntegration 或人工跳过，均留痕）
  in_progress: ['integrating', 'testing', 'todo', 'canceled'],
  integrating: ['testing', 'in_progress', 'canceled'],
  testing: ['in_review', 'in_progress', 'canceled'],
  in_review: ['done', 'in_progress', 'canceled'],
  done: [],
  canceled: ['todo'],
}

/** 任务人工闸门：验收通过（done 仅人）。 */
export const HUMAN_ONLY_TASK_TRANSITIONS: ReadonlySet<string> = new Set(['in_review>done'])

/** system 允许的任务转移（执行结算用）：开始执行与退回。 */
export const SYSTEM_TASK_TRANSITIONS: ReadonlySet<string> = new Set([
  'todo>in_progress',
  'in_progress>todo',
])

export function canTaskTransition(from: TaskStatus, to: TaskStatus): boolean {
  return TASK_TRANSITIONS[from].includes(to)
}

export function assertTaskTransition(from: TaskStatus, to: TaskStatus, actor: ActorKind): void {
  if (!canTaskTransition(from, to)) {
    throw Object.assign(new Error(`任务状态不允许从 ${from} 转移到 ${to}`), { code: 'invalid_transition' })
  }
  const key = `${from}>${to}`
  if (HUMAN_ONLY_TASK_TRANSITIONS.has(key) && actor !== 'human') {
    throw Object.assign(new Error('任务验收（→ done）仅人可操作'), { code: 'human_gate' })
  }
  if (actor === 'system' && !SYSTEM_TASK_TRANSITIONS.has(key)) {
    throw Object.assign(new Error(`system 不可发起任务转移 ${from} → ${to}`), { code: 'system_gate' })
  }
}

// ---------------------------------------------------------------------------
// Task 分类字段
// ---------------------------------------------------------------------------

/** 流水线阶段。 */
export type TaskPhase = 'doc' | 'ui' | 'analysis' | 'implement' | 'test' | 'review' | 'merge'
export const ALL_TASK_PHASES: readonly TaskPhase[] = ['doc', 'ui', 'analysis', 'implement', 'test', 'review', 'merge']

/** 端侧：前端/后端/全栈/纯文档。frontend/backend 默认需要联调。 */
export type TaskSide = 'frontend' | 'backend' | 'fullstack' | 'doc'
export const ALL_TASK_SIDES: readonly TaskSide[] = ['frontend', 'backend', 'fullstack', 'doc']

/** 该 side 默认是否需要联调（建卡未显式标 skipIntegration 时生效）。 */
export function defaultNeedsIntegration(side: TaskSide): boolean {
  return side === 'frontend' || side === 'backend'
}

// ---------------------------------------------------------------------------
// Records
// ---------------------------------------------------------------------------

export interface CommentRecord {
  id: string
  body: string
  createdAt: number
  createdBy?: ActorRef
}

export interface ExecutionRecord {
  id: string
  sessionId?: string
  trigger: 'manual' | 'auto' // auto = 编排器派发
  startedAt: number
  endedAt?: number
  outcome: 'running' | 'succeeded' | 'failed' | 'cancelled'
  error?: string
  /** 证据路径（测试输出/review 报告等，相对需求目录） */
  evidence?: string[]
}

export type RequirementCategory = 'feature' | 'bug' | 'doc' | 'refactor' | 'spike' | 'chore'
export const ALL_REQ_CATEGORIES: readonly RequirementCategory[] = ['feature', 'bug', 'doc', 'refactor', 'spike', 'chore']

export function asReqCategory(raw: unknown): RequirementCategory {
  if (typeof raw !== 'string' || !(ALL_REQ_CATEGORIES as readonly string[]).includes(raw)) {
    bad(`需求分类必须是：${ALL_REQ_CATEGORIES.join(', ')}`)
  }
  return raw as RequirementCategory
}

export interface RequirementRecord {
  id: string // REQ-xxxxxx
  title: string
  description: string
  /** 需求分类（LLM 在新建时自动标注） */
  category?: RequirementCategory
  /** 文档链接（需求文档/UI/方案），相对工作区路径或 URL */
  docLinks?: { requirement?: string; ui?: string; proposal?: string }
  status: RequirementStatus
  blocked: boolean
  blockedReason?: string
  /** 手动中断：编排器跳过本需求的自动派发 */
  paused?: boolean
  /** 评审共创会话 */
  reviewSessionId?: string
  /** 立项来源窗口（自动立项时写入；人工建卡不填）——窗口↔需求 n:n 的需求侧锚点 */
  sourceSessionId?: string
  /** 归档后的目录路径 */
  archivePath?: string
  comments: CommentRecord[]
  version: number
  createdAt: number
  updatedAt: number
  createdBy: ActorRef
  updatedBy: ActorRef
}

export interface TaskScope {
  /** 涉及接口（如 POST /dashboard/api/board/solve） */
  apis: string[]
  /** 涉及数据表 */
  tables: string[]
  /** 涉及文件/目录 */
  files: string[]
}

export interface TaskRecord {
  id: string // t-xxxxxx
  requirementId: string
  title: string
  description: string
  phase: TaskPhase
  side: TaskSide
  /** DAG 依赖（同需求内任务 id） */
  dependsOn: string[]
  scope: TaskScope
  /** 验收标准（TBD 模板化，v1 自由文本） */
  acceptance: string
  /** 需求背景摘要（自足执行用） */
  context: string
  skipIntegration?: boolean
  status: TaskStatus
  blocked: boolean
  blockedReason?: string
  claimedBy?: string
  claimedAt?: number
  executions: ExecutionRecord[]
  comments: CommentRecord[]
  version: number
  createdAt: number
  updatedAt: number
  createdBy: ActorRef
  updatedBy: ActorRef
}

// ---------------------------------------------------------------------------
// Ledger
// ---------------------------------------------------------------------------

export const REQBOARD_SCHEMA_VERSION = 2

export interface ReqboardLedger {
  schemaVersion: number
  revision: number
  requirements: RequirementRecord[]
  tasks: TaskRecord[]
  triages: TriageRecord[]
}

export function emptyLedger(): ReqboardLedger {
  return { schemaVersion: REQBOARD_SCHEMA_VERSION, revision: 0, requirements: [], tasks: [], triages: [] }
}

// ---------------------------------------------------------------------------
// ID 生成（随机 6 位 hex，可读前缀）
// ---------------------------------------------------------------------------

export function newRequirementId(rand: () => number = Math.random): string {
  return `REQ-${Math.floor(rand() * 0xffffff).toString(16).padStart(6, '0')}`
}

export function newTaskId(rand: () => number = Math.random): string {
  return `t-${Math.floor(rand() * 0xffffff).toString(16).padStart(6, '0')}`
}

export function newExecutionId(rand: () => number = Math.random): string {
  return `e-${Math.floor(rand() * 0xffffff).toString(16).padStart(6, '0')}`
}

export function newCommentId(rand: () => number = Math.random): string {
  return `c-${Math.floor(rand() * 0xffffff).toString(16).padStart(6, '0')}`
}

// ---------------------------------------------------------------------------
// 入参校验（routes/tools 共用；非法输入抛 code=invalid_input）
// ---------------------------------------------------------------------------

function bad(message: string): never {
  throw Object.assign(new Error(message), { code: 'invalid_input' })
}

export function normalizeTitle(raw: unknown): string {
  if (typeof raw !== 'string') bad('title 必须是字符串')
  const t = raw.trim()
  if (t.length === 0) bad('title 不能为空')
  if (t.length > 120) bad('title 超长（≤120 字符）')
  return t
}

export function normalizeText(raw: unknown, field: string, max = 4000): string {
  if (raw === undefined || raw === null) return ''
  if (typeof raw !== 'string') bad(`${field} 必须是字符串`)
  const t = raw.trim()
  if (t.length > max) bad(`${field} 超长（≤${max} 字符）`)
  return t
}

export function asReqStatus(raw: unknown): RequirementStatus {
  if (typeof raw !== 'string' || !(ALL_REQ_STATUSES as readonly string[]).includes(raw)) {
    bad(`需求状态必须是：${ALL_REQ_STATUSES.join(', ')}`)
  }
  return raw as RequirementStatus
}

export function asTaskStatus(raw: unknown): TaskStatus {
  if (typeof raw !== 'string' || !(ALL_TASK_STATUSES as readonly string[]).includes(raw)) {
    bad(`任务状态必须是：${ALL_TASK_STATUSES.join(', ')}`)
  }
  return raw as TaskStatus
}

export function asTaskPhase(raw: unknown): TaskPhase {
  if (typeof raw !== 'string' || !(ALL_TASK_PHASES as readonly string[]).includes(raw)) {
    bad(`任务 phase 必须是：${ALL_TASK_PHASES.join(', ')}`)
  }
  return raw as TaskPhase
}

export function asTaskSide(raw: unknown): TaskSide {
  if (typeof raw !== 'string' || !(ALL_TASK_SIDES as readonly string[]).includes(raw)) {
    bad(`任务 side 必须是：${ALL_TASK_SIDES.join(', ')}`)
  }
  return raw as TaskSide
}

export function asActor(raw: unknown): ActorKind {
  if (raw !== 'human' && raw !== 'agent' && raw !== 'system') bad('actor 必须是 human/agent/system')
  return raw
}

export function asScope(raw: unknown): TaskScope {
  const arr = (v: unknown, field: string): string[] => {
    if (v === undefined || v === null) return []
    if (!Array.isArray(v) || v.some(x => typeof x !== 'string')) bad(`scope.${field} 必须是字符串数组`)
    return (v as string[]).map(s => s.trim()).filter(Boolean).slice(0, 50)
  }
  const obj = (typeof raw === 'object' && raw !== null ? raw : {}) as Record<string, unknown>
  return { apis: arr(obj.apis, 'apis'), tables: arr(obj.tables, 'tables'), files: arr(obj.files, 'files') }
}

export function asDependsOn(raw: unknown): string[] {
  if (raw === undefined || raw === null) return []
  if (!Array.isArray(raw) || raw.some(x => typeof x !== 'string')) bad('dependsOn 必须是任务 id 字符串数组')
  return [...new Set(raw as string[])].slice(0, 50)
}

// ---------------------------------------------------------------------------
// DAG 校验（同需求内：依赖存在 / 无自依赖 / 无环）
// ---------------------------------------------------------------------------

/**
 * 校验任务依赖 DAG。tasks 为该需求全部任务（含待落的草稿任务）。
 * 非法时抛 code=invalid_dag。
 */
export function assertDagAcyclic(tasks: ReadonlyArray<Pick<TaskRecord, 'id' | 'dependsOn' | 'requirementId'>>, requirementId: string): void {
  const inReq = tasks.filter(t => t.requirementId === requirementId)
  const ids = new Set(inReq.map(t => t.id))
  const deps = new Map<string, string[]>()
  for (const t of inReq) {
    if (t.dependsOn.includes(t.id)) {
      throw Object.assign(new Error(`任务 ${t.id} 不能依赖自身`), { code: 'invalid_dag' })
    }
    for (const dep of t.dependsOn) {
      if (!ids.has(dep)) {
        throw Object.assign(new Error(`任务 ${t.id} 依赖了不存在的任务 ${dep}（限同需求内）`), { code: 'invalid_dag' })
      }
    }
    deps.set(t.id, [...t.dependsOn])
  }
  // DFS 三色标记找环
  const color = new Map<string, 0 | 1 | 2>() // 0=未访问 1=在栈 2=完成
  const visit = (id: string, path: string[]): void => {
    const c = color.get(id) ?? 0
    if (c === 2) return
    if (c === 1) {
      throw Object.assign(new Error(`任务依赖成环：${[...path, id].join(' → ')}`), { code: 'invalid_dag' })
    }
    color.set(id, 1)
    for (const dep of deps.get(id) ?? []) visit(dep, [...path, id])
    color.set(id, 2)
  }
  for (const id of ids.keys()) visit(id, [])
}

/**
 * 计算 ready 任务：todo 且全部依赖均 done（串行调度器的选择器）。
 */
export function readyTasks(tasks: readonly TaskRecord[], requirementId: string): TaskRecord[] {
  const inReq = tasks.filter(t => t.requirementId === requirementId)
  const doneIds = new Set(inReq.filter(t => t.status === 'done').map(t => t.id))
  return inReq.filter(t => t.status === 'todo' && t.dependsOn.every(dep => doneIds.has(dep)))
}
// ---------------------------------------------------------------------------
// Triage（遗留：旧流程「会话捕获待归类建议卡，人工在看板确认」；新流程 2026-09 起
// 改为创建即立项——两问弹框作答即确认，直接 reqboard_create 建 REQ，不再产生
// pending triage。存量 triage 记录保留供回溯，路由仍兼容其 confirm/reject/rebind。）
// ---------------------------------------------------------------------------

export type TriageStatus = 'pending' | 'confirmed' | 'rejected'

export interface TriageRecord {
  id: string // tri-xxxxxx
  sessionId: string
  /** 会话首条用户消息文本（分类依据） */
  firstMessageText: string
  /** 建议动作 */
  suggestedAction: 'create_req' | 'bind_req' | 'bind_task'
  /** 建议绑定目标 id（REQ-xxx / t-xxx） */
  suggestedTargetId?: string
  /** LLM 建议的需求标题（create_req 时；GUI 可编辑卡预填） */
  suggestedTitle?: string
  /** LLM 建议的需求分类（create_req 时） */
  suggestedCategory?: RequirementCategory
  /** 匹配分数 0-100 */
  score: number
  status: TriageStatus
  createdAt: number
  resolvedAt?: number
  resolvedBy?: ActorRef
  /** 确认后产生的结果需求 id（最近一条；历史见 resultRequirementIds） */
  resultRequirementId?: string
  /** 该窗口全部已立项需求（自动立项史，窗口→需求 n:n 的窗口侧锚点） */
  resultRequirementIds?: string[]
  comments: CommentRecord[]
}

export function newTriageId(rand: () => number = Math.random): string {
  return `tri-${Math.floor(rand() * 0xffffff).toString(16).padStart(6, '0')}`
}

