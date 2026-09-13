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
// 状态事件（时间线）
// ---------------------------------------------------------------------------

/**
 * 一次状态进入事件（时间线的原子单位）。需求与任务共用形状。
 *
 * 为什么必须有它：此前记录上只有 createdAt/updatedAt 两个时间戳，「评审/拆分/实施/
 * 验收/归档发生在什么时候、每一段停留多久」在台账里根本不存在——看板问"需求没有
 * 对应的时间"时无法回答，也无法做停留时长/流程瓶颈分析。状态事件让时间成为一等
 * 数据：每次转移写入一条 {status, at, by, reason}。
 *
 * inferred=true 表示该条为**历史回填**（升级前的老记录没有事件表，由 createdAt +
 * 评论里的转移留痕逐条反推），不是当时真实记录的事件——UI 必须显式标注，避免把
 * 推导值当成原始数据（R-013：数据来源与时点必须可核验）。
 */
export interface StatusEvent {
  status: string
  at: number
  by: ActorRef
  reason?: string
  /** true=从历史评论/时间戳反推的回填事件（非原始记录）。 */
  inferred?: boolean
}

/** 就地追加一条状态事件（相邻同状态去重；返回被写入的事件）。 */
export function recordStatus(
  record: { statusHistory?: StatusEvent[] },
  status: string,
  at: number,
  by: ActorRef,
  reason?: string,
): StatusEvent {
  const history = (record.statusHistory ??= [])
  const last = history[history.length - 1]
  if (last !== undefined && last.status === status && last.at === at) return last
  const event: StatusEvent = { status, at, by, ...(reason !== undefined && reason.length > 0 ? { reason } : {}) }
  history.push(event)
  return event
}

/** 某状态首次进入的时间（未进入过 → undefined）。 */
export function milestoneAt(record: { statusHistory?: StatusEvent[] }, status: string): number | undefined {
  return record.statusHistory?.find(e => e.status === status)?.at
}

// ---------------------------------------------------------------------------
// Requirement 状态机（RFC 014 §3）
// ---------------------------------------------------------------------------

/**
 * 需求流水线 = superpowers 的三段式落成状态（2026-09-13 用户要求「需求从创建开始就有流程」）：
 *   立项 → 头脑风暴（brainstorming）→ 写计划（writing-plans）→ 拆分（落库 DAG）
 *        → 执行（executing-plans）→ 验收 → 完成 → 归档
 * 「计划待批」不是独立状态：它是 planning 的子状态（plan.approvedAt 未写入），看板用
 * 卡面 chip 表达——批准是拆分的前置闸门，不额外占一条泳道。
 */
export type RequirementStatus =
  | 'draft'         // 立项：想法落成需求卡
  | 'brainstorming' // 头脑风暴：探索意图/边界/方案（原 reviewing）
  | 'planning'      // 写计划：产出实施计划（文档 + 任务表），提交待人批准
  | 'decomposing'   // 拆分：计划获批后落库任务 DAG
  | 'implementing'  // 执行：按任务卡逐项执行（executing-plans）
  | 'accepting'     // 验收
  | 'done'          // 完成
  | 'archived'      // 归档
  | 'canceled'

export const MAIN_REQ_STATUSES: readonly RequirementStatus[] = [
  'draft', 'brainstorming', 'planning', 'decomposing', 'implementing', 'accepting', 'done', 'archived',
]

/** 旧状态名迁移（2026-09-13：reviewing → brainstorming）。 */
export const LEGACY_REQ_STATUS_ALIASES: Readonly<Record<string, RequirementStatus>> = {
  reviewing: 'brainstorming',
}

export const ALL_REQ_STATUSES: readonly RequirementStatus[] = [...MAIN_REQ_STATUSES, 'canceled']

/** 需求状态合法转移表。 */
export const REQ_TRANSITIONS: Readonly<Record<RequirementStatus, readonly RequirementStatus[]>> = {
  draft: ['brainstorming', 'canceled'],
  brainstorming: ['planning', 'draft', 'canceled'],
  planning: ['decomposing', 'brainstorming', 'canceled'],
  decomposing: ['implementing', 'planning', 'canceled'],
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
  // 2026-09-11 用户裁定：agent 必须能自己推进在途需求（此前「确认方案/确认拆分/
  // 验收通过」都是人工闸门 → 每个需求都要人点两三次，看板实质静止）。
  // 现在仅保留**终态与破坏性动作**为人工闸门，在途推理由窗口 agent 自行推进：
  'draft>canceled',
  'brainstorming>canceled',
  'decomposing>canceled',
  'implementing>canceled',
  'accepting>canceled', // 取消需求（破坏性）
  'accepting>done', // 验收通过（人工审核：agent 可提交验收，但"过"必须是人点的）
  'done>archived', // 归档
  'canceled>archived', // 取消后归档
])

/**
 * system（rollup）允许自动推进的转移白名单：其余转移 system 一律不可发起。
 *  - draft>brainstorming       需求被窗口接手开工（有直接人类消息）的接手推进；
 *  - implementing>accepting 全部实施任务 done 的 rollup。
 * 人工闸门（brainstorming>decomposing / decomposing>implementing / accepting>done /
 * done>archived）永不在本白名单内 —— 自动推进不可能越过人工闸门。
 */
export const SYSTEM_REQ_TRANSITIONS: ReadonlySet<string> = new Set([
  'draft>brainstorming', // 窗口接手开工 → 进入头脑风暴（方案共创）
  'planning>decomposing', // 计划已批准并落库任务 → 自动进入拆分态
  'decomposing>implementing', // 任务开始执行 → 自动进入执行
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

/**
 * 任务人工闸门（代码级仅人）。
 * 2026-09-13 用户裁定（与需求闸门同一口径）：agent 必须能自己把任务跑完——
 * 此前 in_review>done 仅人可操作，而任务完成又驱动需求 rollup，导致任务卡停在
 * 「验收」、需求进不了验收，看板再次静止。现仅保留**取消/复活**这类破坏性动作
 * 为人工闸门，正常流水线（含任务完成）由执行窗口自行推进。
 */
export const HUMAN_ONLY_TASK_TRANSITIONS: ReadonlySet<string> = new Set([
  'todo>canceled',
  'in_progress>canceled',
  'integrating>canceled',
  'testing>canceled',
  'in_review>canceled',
  'canceled>todo', // 复活已取消任务：仅人
])

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
// 实施计划（plan mode —— 拆分前必须先有计划，计划由人批准）
// ---------------------------------------------------------------------------

/**
 * 计划中的一个任务条目：**拆分前就定死的粒度**。
 *
 * 为什么计划里就带任务表（而不是只写一段散文）：拆分的粒度、依赖、验收标准如果等到
 * 落库时才由 agent 临时决定，人就失去了唯一的把关点——他能看到的只有「已拆分」这个
 * 状态。把任务表写进计划，人批准计划 = 批准拆分方案本身；之后的 decompose 只是把批准
 * 过的东西**落库**，不再二次创作。
 */
export interface PlanTask {
  key: string
  title: string
  description?: string
  phase?: TaskPhase
  side?: TaskSide
  /** 依赖（同计划内的 key） */
  dependsOn?: string[]
  /** 验收标准：怎么算做完（可验证，不允许"功能正常"这类空话） */
  acceptance?: string
}

/**
 * 需求上的实施计划（plan mode 的载体）。生命周期：
 *   agent 提交（submittedAt）→ 人批准（approvedAt）或退回（rejectedAt + reason）
 * 未批准的计划不构成拆分的许可——分解工具会代码级拒绝（HARD GATE）。
 */
export interface PlanRecord {
  /** 计划文档路径（工作区相对路径，如 docs/requirements/REQ-xxxxxx/plan.md） */
  path: string
  /** 计划摘要（目标 + 做法，人读这一段就懂） */
  summary: string
  /** 计划里的任务表（拆分即落库这批） */
  tasks: PlanTask[]
  submittedAt: number
  submittedBy: ActorRef
  approvedAt?: number
  approvedBy?: ActorRef
  rejectedAt?: number
  rejectedReason?: string
}

/**
 * 验收材料（agent 提交）+ 人工审核结论。
 *
 * 用户要求「验收 有人工审核」：agent 把"做完的证据"交上来（怎么验的、看到什么结果，
 * 全是可复核的命令/输出/路径，不接受"功能正常"），人**看着证据**决定过还是退回返工。
 * 代码级：验收通过（accepting>done）是人工闸门；提交验收必须有材料。
 */
export interface VerificationRecord {
  /** 一句话结论：这次交付了什么、验了什么 */
  summary: string
  /** 证据清单（命令 + 输出摘要 / 测试报告路径 / 截图路径） */
  evidence: string[]
  submittedAt: number
  submittedBy: ActorRef
  reviewedAt?: number
  reviewedBy?: ActorRef
  /** pass=验收通过；rework=退回返工（附意见） */
  decision?: 'pass' | 'rework'
  reviewNote?: string
}

/** 归档材料里的一条文档。 */
export interface ArchiveDoc {
  /** requirement=需求说明 / plan=实施计划 / verification=验收材料 / retro=复盘 / notes=其他 */
  kind: 'requirement' | 'plan' | 'verification' | 'retro' | 'notes'
  path: string
}

/**
 * 归档材料（agent 准备）+ 归档结论（人拍板）。
 *
 * 用户要求「归档 要有项目文档设计，文档如何合并，不同问题如何记录文档」：
 * 归档不是把目录挪走，而是**把这次需求的产出并进项目文档**——需求目录里留全套原始
 * 材料（需求/计划/验收/复盘），同时把"别人以后要读的那部分"合并进
 * docs/architecture|guides|adr|research|known-issues 等既定文档，并写一条索引条目。
 * 不同需求类型（category）的必填文档与合并去向由 ARCHIVE_DOC_RULES 规定，
 * 规范文档：agent-dh/docs/architecture/requirement-archive.md。
 */
export interface ArchiveRecord {
  /** 需求目录（工作区相对路径，如 docs/requirements/REQ-xxxxxx） */
  dir: string
  /** 目录内保留的文档清单 */
  docs: ArchiveDoc[]
  /** 合并进的项目文档路径（架构/指南/ADR/研究/已知问题） */
  mergedInto: string[]
  /** 索引条目：一句话结论（进归档索引，供检索） */
  indexEntry: string
  submittedAt: number
  submittedBy: ActorRef
  archivedAt?: number
  archivedBy?: ActorRef
}

/** 计划是否已被批准（拆分的代码级前置条件）。 */
export function planApproved(req: { plan?: PlanRecord }): boolean {
  return req.plan !== undefined && req.plan.approvedAt !== undefined
}

/** 计划任务表校验规整（key 唯一；phase/side 合法；标题非空；依赖只能指向计划内 key）。 */
export function normalizePlanTasks(raw: unknown): PlanTask[] {
  if (!Array.isArray(raw) || raw.length === 0) bad('计划必须包含至少 1 个任务（tasks 非空数组）')
  if (raw.length > 50) bad('计划任务过多（≤50）')
  const keys = new Set<string>()
  const out: PlanTask[] = []
  raw.forEach((item, i) => {
    const o = (typeof item === 'object' && item !== null ? item : {}) as Record<string, unknown>
    const key = (typeof o.key === 'string' && o.key.trim().length > 0 ? o.key.trim() : 'k' + (i + 1)).slice(0, 40)
    if (keys.has(key)) bad('计划任务 key 重复：' + key)
    keys.add(key)
    const description = o.description === undefined || o.description === null ? '' : String(o.description).trim().slice(0, 4000)
    const acceptance = o.acceptance === undefined || o.acceptance === null ? '' : String(o.acceptance).trim().slice(0, 2000)
    out.push({
      key,
      title: normalizeTitle(o.title),
      ...(description.length > 0 ? { description } : {}),
      phase: o.phase === undefined ? 'implement' : asTaskPhase(o.phase),
      side: o.side === undefined ? 'fullstack' : asTaskSide(o.side),
      dependsOn: asDependsOn(o.dependsOn ?? o.depends_on),
      ...(acceptance.length > 0 ? { acceptance } : {}),
    })
  })
  for (const t of out) {
    for (const dep of t.dependsOn ?? []) {
      if (!keys.has(dep)) bad('计划任务 ' + t.key + ' 依赖了计划中不存在的 key：' + dep)
      if (dep === t.key) bad('计划任务 ' + t.key + ' 不能依赖自身')
    }
  }
  return out
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
  /**
   * 状态事件时间线（创建 + 每次转移一条）。老记录首次加载时由 backfill* 反推补齐
   * （inferred=true），新转移一律实时写入真实事件。
   */
  statusHistory?: StatusEvent[]
  /** 实施计划（plan mode）：拆分前提交、由人批准；未批准不允许拆分 */
  plan?: PlanRecord
  /** 验收材料（agent 提交）+ 人工审核结论 */
  verification?: VerificationRecord
  /** 归档材料（agent 准备）+ 归档结论（人） */
  archive?: ArchiveRecord
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
  /** 状态事件时间线（创建 + 每次转移一条；甘特图据此按状态分段着色） */
  statusHistory?: StatusEvent[]
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

export const REQBOARD_SCHEMA_VERSION = 3

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

// ---------------------------------------------------------------------------
// 历史回填（升级迁移：老记录没有事件表 → 从 createdAt + 评论留痕反推）
// ---------------------------------------------------------------------------

/**
 * 从评论正文解析转移目标状态。覆盖历史上的三种留痕格式：
 *   `[自动推进] draft → brainstorming：…`（rollup）
 *   `[窗口推进] brainstorming → decomposing：…`（reqboard_move 工具）
 *   `[状态] decomposing ← 转移说明：…`（需求路由 move，箭头指向新状态）
 *   `[状态] → in_progress：…`（任务路由 move）
 * 解析不出或状态非法 → undefined（宁缺毋滥，绝不猜）。
 */
export function parseTransitionTarget(body: string, allowed: readonly string[]): string | undefined {
  const candidates: Array<{ re: RegExp; group: number }> = [
    { re: /\[(?:自动推进|窗口推进|人工推进)\]\s*\w+\s*→\s*(\w+)/, group: 1 },
    { re: /\[状态\]\s*(\w+)\s*←/, group: 1 },
    { re: /\[状态\]\s*→\s*(\w+)/, group: 1 },
  ]
  for (const { re, group } of candidates) {
    const m = re.exec(body)
    const hit = m?.[group]
    if (hit !== undefined && allowed.includes(hit)) return hit
  }
  return undefined
}

function backfill(
  record: { status: string; createdAt: number; updatedAt: number; createdBy: ActorRef; updatedBy: ActorRef; comments: CommentRecord[] },
  initialStatus: string,
  allowed: readonly string[],
  statusHistory: StatusEvent[] | undefined,
): StatusEvent[] | undefined {
  if (statusHistory !== undefined && statusHistory.length > 0) return undefined
  const events: StatusEvent[] = [
    { status: initialStatus, at: record.createdAt, by: record.createdBy, reason: '创建', inferred: true },
  ]
  for (const c of [...record.comments].sort((a, b) => a.createdAt - b.createdAt)) {
    const raw = parseTransitionTarget(c.body, allowed)
    if (raw === undefined) continue
    // 历史评论里可能写的是旧状态名（reviewing）——按别名表映射回新名，别丢历史
    const target = LEGACY_REQ_STATUS_ALIASES[raw] ?? raw
    const prev = events[events.length - 1]
    if (prev !== undefined && prev.status === target) continue
    events.push({
      status: target,
      at: c.createdAt,
      by: c.createdBy ?? { kind: 'system' },
      reason: (c.body.split('\n')[0] ?? '').slice(0, 120),
      inferred: true,
    })
  }
  const tail = events[events.length - 1]
  if (tail === undefined || tail.status !== record.status) {
    // 评论里没有该状态的留痕（老格式/直接改库）→ 用 updatedAt 兜底并标注不可考
    events.push({
      status: record.status,
      at: Math.max(record.updatedAt, record.createdAt),
      by: record.updatedBy,
      reason: '按 updatedAt 回填（当时无事件留痕）',
      inferred: true,
    })
  }
  return events
}

/** 需求时间线回填（已有事件 → 返回 undefined 不动）。旧状态名（reviewing）一并接受。 */
export function backfillRequirementHistory(req: RequirementRecord): StatusEvent[] | undefined {
  return backfill(
    req,
    'draft',
    [...ALL_REQ_STATUSES, ...Object.keys(LEGACY_REQ_STATUS_ALIASES)],
    req.statusHistory,
  )
}

/**
 * 旧状态名迁移（2026-09-13）：reviewing → brainstorming（含时间线事件）。
 * 迁移只改名字，不改语义；返回 true 表示发生过迁移（调用方据此决定是否落盘）。
 */
export function migrateRequirementStatusNames(req: RequirementRecord): boolean {
  let changed = false
  const alias = LEGACY_REQ_STATUS_ALIASES[req.status as string]
  if (alias !== undefined) {
    req.status = alias
    changed = true
  }
  for (const e of req.statusHistory ?? []) {
    const mapped = LEGACY_REQ_STATUS_ALIASES[e.status]
    if (mapped !== undefined) {
      e.status = mapped
      changed = true
    }
  }
  return changed
}

/** 任务时间线回填（已有事件 → 返回 undefined 不动）。 */
export function backfillTaskHistory(task: TaskRecord): StatusEvent[] | undefined {
  return backfill(task, 'todo', ALL_TASK_STATUSES as readonly string[], task.statusHistory)
}

// ---------------------------------------------------------------------------
// 归档文档规范（不同问题如何记录文档 —— 校验的唯一依据）
// ---------------------------------------------------------------------------

/**
 * 需求类型 → 归档时的文档要求。规范文档：agent-dh/docs/architecture/requirement-archive.md。
 * 校验是**代码级**的：缺必填文档或合并去向 → 归档材料提交被拒。
 */
export interface ArchiveDocRule {
  /** 需求目录内必填的文档 kind */
  requiredDocs: readonly ArchiveDoc['kind'][]
  /** 必须合并进的项目文档前缀（合并去向必须落在这些目录里） */
  mergeTargets: readonly string[]
  /** 人读的一句话规则说明 */
  note: string
}

export const ARCHIVE_DOC_RULES: Readonly<Record<RequirementCategory, ArchiveDocRule>> = {
  feature: {
    requiredDocs: ['requirement', 'plan', 'verification'],
    mergeTargets: ['agent-dh/docs/architecture/', 'agent-dh/docs/guides/', 'docs/architecture/', 'docs/guides/'],
    note: '功能：能力/接口变了 → 必须更新架构或使用指南（否则新人只能读代码）',
  },
  bug: {
    requiredDocs: ['requirement', 'verification', 'retro'],
    mergeTargets: ['agent-dh/docs/known-issues/', 'docs/known-issues/'],
    note: '缺陷：必须留根因与防回归（known-issues 一条 + 复盘），否则同类问题会再来一次',
  },
  doc: {
    requiredDocs: ['requirement', 'verification'],
    mergeTargets: ['agent-dh/docs/', 'docs/'],
    note: '文档类需求：产出本身就是文档，直接合并进 docs/ 相应子目录',
  },
  refactor: {
    requiredDocs: ['requirement', 'plan', 'verification', 'retro'],
    mergeTargets: ['agent-dh/docs/architecture/', 'agent-dh/docs/work-logs/', 'docs/architecture/', 'docs/work-logs/'],
    note: '重构：结构与边界变了 → 架构说明必须同步，否则文档与代码互相说谎',
  },
  spike: {
    requiredDocs: ['requirement', 'retro'],
    mergeTargets: ['agent-dh/docs/research/', 'docs/research/', 'docs/strategy-research/'],
    note: '调研：产物是结论（含被证伪的假设），必须进 research，明确"没有代码要留"',
  },
  chore: {
    requiredDocs: ['requirement', 'verification'],
    mergeTargets: ['agent-dh/docs/work-logs/', 'docs/work-logs/'],
    note: '杂项/维护：留一条工作记录即可，别把运维细节塞进架构文档',
  },
}

/** 需求目录约定（校验用）：docs/requirements/REQ-xxxxxx 或 agent-dh/docs/requirements/REQ-xxxxxx。 */
export const REQUIREMENT_DIR_PATTERN = /(?:^|\/)docs\/requirements\/REQ-[0-9a-f]{6}$/

/** 归档材料校验（缺项抛 code=invalid_input，消息指明缺什么）。 */
export function assertArchiveMaterials(
  category: RequirementCategory | undefined,
  archive: Pick<ArchiveRecord, 'dir' | 'docs' | 'mergedInto' | 'indexEntry'>,
): void {
  const rule = ARCHIVE_DOC_RULES[category ?? 'feature']
  if (archive.dir.trim().length === 0) bad('归档材料缺少需求目录（dir）')
  if (!REQUIREMENT_DIR_PATTERN.test(archive.dir.trim())) {
    bad('需求目录不符合约定：应为 docs/requirements/REQ-xxxxxx（或 agent-dh/docs/requirements/REQ-xxxxxx），'
      + '当前是 ' + archive.dir.trim())
  }
  if (archive.indexEntry.trim().length === 0) {
    bad('归档材料缺少索引条目（indexEntry）：一句话说清这次需求解决了什么')
  }
  const kinds = new Set(archive.docs.map(d => d.kind))
  const missing = rule.requiredDocs.filter(k => !kinds.has(k))
  if (missing.length > 0) {
    bad('归档材料缺少必填文档：' + missing.join(', ') + '（' + (category ?? 'feature') + ' 类要求）' + rule.note)
  }
  if (archive.docs.some(d => d.path.trim().length === 0)) bad('归档文档清单存在空路径')
  if (archive.mergedInto.length === 0) {
    bad('归档材料缺少合并去向（mergedInto）——' + rule.note)
  }
  for (const target of archive.mergedInto) {
    if (!rule.mergeTargets.some(prefix => target.startsWith(prefix))) {
      bad('合并去向 ' + target + ' 不在本类型允许的位置（应为 ' + rule.mergeTargets.join(' / ') + ' 之下）：' + rule.note)
    }
  }
}
