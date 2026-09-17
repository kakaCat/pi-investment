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
// 领域规则的唯一实现处迁至 src/domain/**（REQ-47939a t2）
// ---------------------------------------------------------------------------
// 本文件继续作为 host 与 client 共用的事实契约枢纽，但状态机 / 可证伪验收 / 产物规约的
// **数据与判定**不再在这里定义，而是从 domain 单向再导出——客户端渲染"下一步可推进哪"
// 与宿主判定用同一份表，消除"前端口径与后端口径漂移"（architecture.md §2 注释）。
// 规则常量与类型从 domain 再导出后，既有 20 个引用方的 import 路径保持不变。
import type { ActorKind, ActorRef } from '../domain/actor.js'
import type { RequirementStatus, StageKey } from '../domain/requirement/RequirementStatus.js'
import type { TaskStatus } from '../domain/task/TaskStatus.js'
import type { RequirementCategory } from '../domain/requirement/Requirement.js'
import type { ArtifactKind, ArchiveDoc, ArchiveDocRule } from '../domain/artifact/ArtifactSpec.js'
import {
  REQ_TRANSITIONS,
  HUMAN_ONLY_REQ_TRANSITIONS,
  SYSTEM_REQ_TRANSITIONS,
  canReqTransition,
  assertReqTransition,
  agentNextActions,
} from '../domain/requirement/RequirementStatus.js'
import {
  TASK_TRANSITIONS,
  HUMAN_ONLY_TASK_TRANSITIONS,
  SYSTEM_TASK_TRANSITIONS,
  canTaskTransition,
  assertTaskTransition,
} from '../domain/task/TaskStatus.js'
import { checkAcceptance, checkPlanTaskReferences } from '../domain/task/Acceptability.js'
import type { VerificationItemSource } from '../domain/workflow/AcceptanceSheetSpec.js'
import {
  ALL_ARTIFACT_KINDS,
  STAGE_ARTIFACT_REQUIREMENTS,
  ARTIFACT_CONFIRM_GATES,
  ARCHIVE_DOC_RULES,
} from '../domain/artifact/ArtifactSpec.js'

// 类型再导出（保持既有 import 路径）
export type { ActorKind, ActorRef }
export type { RequirementStatus, StageKey }
export type { TaskStatus }
export type { RequirementCategory }
export type { ArtifactKind, ArchiveDoc, ArchiveDocRule }
export type { VerificationItemSource }
// 规则常量 / 判定函数再导出
export {
  REQ_TRANSITIONS,
  HUMAN_ONLY_REQ_TRANSITIONS,
  SYSTEM_REQ_TRANSITIONS,
  canReqTransition,
  assertReqTransition,
  agentNextActions,
}
export {
  TASK_TRANSITIONS,
  HUMAN_ONLY_TASK_TRANSITIONS,
  SYSTEM_TASK_TRANSITIONS,
  canTaskTransition,
  assertTaskTransition,
}
export { ALL_ARTIFACT_KINDS, STAGE_ARTIFACT_REQUIREMENTS, ARTIFACT_CONFIRM_GATES, ARCHIVE_DOC_RULES }

// ---------------------------------------------------------------------------
// Actors
// ---------------------------------------------------------------------------

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

// RequirementStatus 类型与状态机迁至 domain/requirement/RequirementStatus.ts（REQ-47939a t2）。

/**
 * 流水线主状态（REQ-9f4a44：**移除 done**）。
 *
 * 验收通过 ⇒ 直接归档，中间不再有"完成"节点——done 只是"验收通过"的落点，语义重复。
 * 注：`done` 仍保留在 RequirementStatus 类型与 ALL_REQ_STATUSES 中（legacy 兼容），
 * 但不在 MAIN 里，因此不参与流程图节点、分类档案与阶段提示词键。
 */
export const MAIN_REQ_STATUSES: readonly RequirementStatus[] = [
  'draft', 'brainstorming', 'planning', 'decomposing', 'implementing', 'accepting', 'archived',
]

// LEGACY_REQ_STATUS_ALIASES 已随迁移收口移出运行时契约（REQ-47939a t10）：
// 别名表 + 历史时间线回填 + 旧状态名归一现在都在 src/domain/legacy/LegacyStatus.ts，
// 只由迁移脚本/迁移用例复用；运行时读路径不再做别名兜底（数据已在 v5 迁移时归一）。

/** 全部可读状态（含 legacy `done`）——用于载入校验，保证老台账不被丢弃。 */
export const ALL_REQ_STATUSES: readonly RequirementStatus[] = [...MAIN_REQ_STATUSES, 'done', 'canceled']

// REQ_TRANSITIONS / HUMAN_ONLY_REQ_TRANSITIONS / SYSTEM_REQ_TRANSITIONS 迁至
// domain/requirement/RequirementStatus.ts（REQ-47939a t2），本文件顶部再导出。

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

// canReqTransition / assertReqTransition 迁至 domain/requirement/RequirementStatus.ts（t2）。

// 用户可见文案单点（REQ-47939a 返工）：弹框选项/徽章此前 host 与 client 各写一份会静默漂移，
// 现由 domain/text/labels.ts 单点定义、此处再导出给 client 复用。
export {
  ACCEPT_ITEM_OPTIONS, FINAL_PASS_LABEL, FINAL_DECLINE_LABEL,
  ITEM_STATUS_BADGE, DEFAULT_CONFIRM_OPTIONS,
} from '../domain/text/labels.js'
import { LIMITS } from '../domain/limits.js'

// ---------------------------------------------------------------------------
// Task 状态机（RFC 014 §4）
// ---------------------------------------------------------------------------

// TaskStatus 类型与状态机迁至 domain/task/TaskStatus.ts（REQ-47939a t2）。

export const MAIN_TASK_STATUSES: readonly TaskStatus[] = [
  'todo', 'in_progress', 'integrating', 'testing', 'in_review', 'done',
]

export const ALL_TASK_STATUSES: readonly TaskStatus[] = [...MAIN_TASK_STATUSES, 'canceled']

// TASK_TRANSITIONS / HUMAN_ONLY_TASK_TRANSITIONS / SYSTEM_TASK_TRANSITIONS /
// canTaskTransition / assertTaskTransition 迁至 domain/task/TaskStatus.ts（t2），顶部再导出。

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
// 流水线节点契约（REQ-31e11f：节点详情/产物闸门/分类流程/提示词键 共用）
// ---------------------------------------------------------------------------

/** 流水线节点键 = 需求主状态（除 canceled）。会话框进度条、节点详情、产物闸门共用。 */
// StageKey 类型迁至 domain/requirement/RequirementStatus.ts（t2），顶部再导出；ALL_STAGE_KEYS
// 是 MAIN_REQ_STATUSES 的过滤投影，仍留在本文件（消费方为 CATEGORY_FLOW_PROFILES / asStageKey）。
export const ALL_STAGE_KEYS: readonly StageKey[] = MAIN_REQ_STATUSES.filter((s): s is StageKey => s !== 'canceled')

export function asStageKey(raw: unknown): StageKey {
  if (typeof raw !== 'string' || !(ALL_STAGE_KEYS as readonly string[]).includes(raw)) {
    bad(`节点键必须是：${ALL_STAGE_KEYS.join(', ')}`)
  }
  return raw as StageKey
}

// ArtifactKind / ALL_ARTIFACT_KINDS 迁至 domain/artifact/ArtifactSpec.ts（t2），顶部再导出。

export function asArtifactKind(raw: unknown): ArtifactKind {
  if (typeof raw !== 'string' || !(ALL_ARTIFACT_KINDS as readonly string[]).includes(raw)) {
    bad(`产物种类必须是：${ALL_ARTIFACT_KINDS.join(', ')}`)
  }
  return raw as ArtifactKind
}

/** 节点产物登记（t4 钩子写入；五道人工确认门的确认状态在此）。 */
export interface StageArtifact {
  stage: StageKey
  kind: ArtifactKind
  /** 产物文档路径（工作区相对路径） */
  path: string
  registeredAt: number
  registeredBy: ActorRef
  /** 五道人工确认门：人确认后写入（看板一键确认，或会话经 ask_user_question 落章） */
  confirmedAt?: number
  confirmedBy?: ActorRef
  /**
   * 确认来源（REQ-ff20ca t2）：board=看板一键确认 / session=会话经 ask_user_question 落章。
   * 缺省视为 board（存量记录向后兼容）。
   */
  confirmedVia?: 'board' | 'session'
  /** 会话确认的审计凭据：用户在 ask_user_question 中的答复原文（仅 via=session 时写入） */
  confirmedEvidence?: string
  /**
   * 自动发现标记（REQ-2e9473 t11/W4）：true = 由 syncReqArtifacts 扫描需求目录补登，
   * 非工具显式登记。看板文档记录区据此显示「自动发现」徽标。
   */
  autoDiscovered?: boolean
  /** 自动发现时的文件 mtime / 大小（审计与新鲜度展示用）。 */
  fileMtime?: number
  fileSize?: number
}

// STAGE_ARTIFACT_REQUIREMENTS / ARTIFACT_CONFIRM_GATES 迁至 domain/artifact/ArtifactSpec.ts（t2），
// 顶部再导出（CATEGORY_FLOW_PROFILES / confirmGateKindFor 仍在本文件消费它们）。

/** 分类流程档案：不同立项分类走不同流程形状（跳过阶段不产生物/不设门/不注入提示词）。 */
export interface CategoryFlowProfile {
  /** 启用节点（按流水线序） */
  stages: readonly StageKey[]
  /** 生效的人工确认门（'from>to'，ARTIFACT_CONFIRM_GATES 子集） */
  confirmGates: readonly string[]
  note: string
}

export const CATEGORY_FLOW_PROFILES: Readonly<Record<RequirementCategory, CategoryFlowProfile>> = {
  feature: { stages: ALL_STAGE_KEYS, confirmGates: Object.keys(ARTIFACT_CONFIRM_GATES), note: '全流水线，五门全开' },
  bug: {
    stages: ['draft', 'planning', 'decomposing', 'implementing', 'accepting', 'archived'],
    confirmGates: ['planning>decomposing', 'decomposing>implementing', 'accepting>archived'],
    note: '免需求分析门：业务文档+复现定位即上下文，并入修复方案产物',
  },
  refactor: {
    stages: ['draft', 'planning', 'decomposing', 'implementing', 'accepting', 'archived'],
    confirmGates: ['planning>decomposing', 'decomposing>implementing', 'accepting>archived'],
    note: '免需求分析：现状+目标态并入技术设计',
  },
  spike: {
    stages: ['draft', 'implementing', 'accepting', 'archived'],
    confirmGates: ['accepting>archived'],
    note: '研究即实施，产物=研究报告',
  },
  doc: {
    stages: ['draft', 'implementing', 'accepting', 'archived'],
    confirmGates: ['accepting>archived'],
    note: '写作即实施',
  },
  chore: {
    stages: ['draft', 'implementing', 'accepting', 'archived'],
    confirmGates: ['accepting>archived'],
    note: '最简流程',
  },
}

export function flowProfileFor(category: RequirementCategory | undefined): CategoryFlowProfile {
  return CATEGORY_FLOW_PROFILES[category] ?? CATEGORY_FLOW_PROFILES['feature']
}

export function stageEnabledFor(category: RequirementCategory | undefined, stage: StageKey): boolean {
  return flowProfileFor(category).stages.includes(stage)
}

/** 该分类下此转移的人工确认门要求（无门 → undefined）。 */
export function confirmGateKindFor(
  category: RequirementCategory | undefined,
  from: RequirementStatus,
  to: RequirementStatus,
): ArtifactKind | undefined {
  const key = `${from}>${to}`
  if (!flowProfileFor(category).confirmGates.includes(key)) return undefined
  return ARTIFACT_CONFIRM_GATES[key]
}

// ---------------------------------------------------------------------------
// 节点详情契约（模板模式：骨架固定，body 可变；host 装配器与 client 渲染器共用）
// ---------------------------------------------------------------------------

/** 节点详情公共骨架。 */
export interface StageDetailBase {
  stage: StageKey
  /** false=本分类跳过该节点（UI 标灰"本分类跳过"，不算缺失） */
  enabled: boolean
  /** 该节点已登记的产物 */
  artifacts: StageArtifact[]
  /** 该节点有产物待人工确认（五门对准且未 confirmed） */
  pendingConfirmation: boolean
  /** 该阶段状态事件切片（谁/何时/为什么） */
  timeline: StatusEvent[]
}

/** 任务引用（拆分/实施节点共用；handoff 自足任务卡）。 */
export interface StageTaskRef {
  id: string
  title: string
  status: TaskStatus
  phase: TaskPhase
  side: TaskSide
  dependsOn: string[]
  /** 上游产出摘要（下游窗口不读上游会话） */
  dependsSummary?: string
  acceptance: string
  /** 自足任务卡文档（decompose 生成骨架，task_report 追加汇报） */
  cardDoc?: string
  executorHint?: ExecutorHint
}

export interface StageTaskExecution extends StageTaskRef {
  claimedBy?: string
  executions: ExecutionRecord[]
}

export interface DraftStageBody { title: string; category?: RequirementCategory; description: string; sourceWindow?: string; createdAt?: number }
export interface BrainstormStageBody { requirementDoc?: string; reviewSessionId?: string; comments: CommentRecord[] }
export interface PlanningStageBody { plan?: PlanRecord }
export interface DecomposeStageBody { decompositionDoc?: string; tasks: StageTaskRef[]; planTasks: PlanTask[] }
export interface ImplementStageBody {
  tasks: StageTaskExecution[]
  /** 窗口码 → 任务 id 列表（上下文分担可见化） */
  byWindow: Record<string, string[]>
}
export interface AcceptStageBody { verification?: VerificationRecord }
export interface DoneStageBody { completedAt?: number; verificationDecision?: 'pass' | 'rework' }
export interface ArchiveStageBody { archive?: ArchiveRecord }

export type StageDetail =
  | (StageDetailBase & { stage: 'draft'; body: DraftStageBody })
  | (StageDetailBase & { stage: 'brainstorming'; body: BrainstormStageBody })
  | (StageDetailBase & { stage: 'planning'; body: PlanningStageBody })
  | (StageDetailBase & { stage: 'decomposing'; body: DecomposeStageBody })
  | (StageDetailBase & { stage: 'implementing'; body: ImplementStageBody })
  | (StageDetailBase & { stage: 'accepting'; body: AcceptStageBody })
  | (StageDetailBase & { stage: 'done'; body: DoneStageBody })
  | (StageDetailBase & { stage: 'archived'; body: ArchiveStageBody })

/**
 * 全流程一览（REQ-31e11f 节点详情重设计：监控视角，一眼看全）。
 * 一次返回全部节点详情 + 当前节点，client 渲染竖向时间线（每节点一行摘要 + 就地展开）。
 */
export interface StageOverview {
  requirementId: string
  category?: RequirementCategory
  /** 需求当前状态（= 当前节点；canceled 时各节点按既有完成度推导状态） */
  currentStage: RequirementStatus
  /** 全部节点（含 enabled=false 的跳过节点），按 ALL_STAGE_KEYS 顺序 */
  stages: StageDetail[]
}

// 阶段提示词键与常量表迁至 domain/stage/StagePromptSpec.ts（REQ-47939a t9），此处再导出。
export type { StagePromptKey } from '../domain/stage/StagePromptSpec.js'
export { ALL_STAGE_PROMPT_KEYS } from '../domain/stage/StagePromptSpec.js'

/** 执行方式提示：该任务该换上下文执行（handoff 意图落成数据）。 */
export type ExecutorHint = 'fresh-window' | 'subagent' | 'current'
export const ALL_EXECUTOR_HINTS: readonly ExecutorHint[] = ['fresh-window', 'subagent', 'current']

export function asExecutorHint(raw: unknown): ExecutorHint | undefined {
  if (raw === undefined || raw === null || raw === '') return undefined
  if (typeof raw !== 'string' || !(ALL_EXECUTOR_HINTS as readonly string[]).includes(raw)) {
    bad('executorHint 必须是：' + ALL_EXECUTOR_HINTS.join(', '))
  }
  return raw as ExecutorHint
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
  /**
   * 实施方案（REQ-2e9473 W5）：拆分卡 ≠ 实施卡——本字段回答"怎么做"：
   * 改哪些文件、步骤、验证方式。REQ-6f39b5 事故 F 的教训：薄卡（只有 title+acceptance）
   * 让 agent 凭印象自由发挥，8 处偏离技术设计。批准计划 = 同时批准做什么与怎么做。
   */
  implementation?: string
  /** 执行方式提示：该任务该换上下文执行（fresh-window/subagent/current） */
  executorHint?: ExecutorHint
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
  /** 批准来源（REQ-ff20ca t2）：board=看板 / session=会话经 ask_user_question；缺省视为 board */
  approvedVia?: 'board' | 'session'
  /** 会话批准的审计凭据：用户答复原文（仅 via=session 时写入） */
  approvedEvidence?: string
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
/**
 * 验收单单项（REQ-2e9473 t13/W6）：一个可独立裁决的验收点。
 * 来源 = 任务验收标准（source=taskId）或需求级标准（source='requirement'）。
 */
export interface VerificationItem {
  /** 稳定 id（v1-1, v1-2…；跨版本复用时保留） */
  id: string
  /**
   * 来源（v5 判别联合，migration.md C7）：任务项带 taskId，需求级项 kind='requirement'。
   * 旧账本的字符串 source（任务 id / 'requirement'）不落在 ledger——实测含 sheet 的需求为 0，
   * 故本类型不做字符串兼容读。
   */
  source: VerificationItemSource
  /** 验收标准原文（怎么算过） */
  criterion: string
  /** 该项对应的证据（产物路径/命令输出摘要/截图） */
  evidence: string[]
  /** 裁决状态（挂起/续验持久化核心）：pending=待验 / passed=通过 / failed=不通过 */
  status: 'pending' | 'passed' | 'failed'
  /** 用户裁决意见（不通过时必填） */
  opinion?: string
  decidedAt?: number
  decidedBy?: ActorRef
}

/**
 * 验收单（版本化，REQ-2e9473 t13/W6）：逐项打勾的载体，可挂起/续验。
 * v2+ 只含上一版未过项（已过项保留结论，不重验）。
 */
export interface VerificationSheet {
  version: number
  items: VerificationItem[]
  generatedAt: number
  generatedBy: ActorRef
  /** 本轮是否只含上一版未过项（返工续验标记） */
  reworkOnly?: boolean
}

export interface VerificationRecord {
  /** 一句话结论：这次交付了什么、验了什么 */
  summary: string
  /** 证据清单（命令 + 输出摘要 / 测试报告路径 / 截图路径） */
  evidence: string[]
  submittedAt: number
  submittedBy: ActorRef
  /** 当前验收单（逐项裁决；REQ-2e9473 t13） */
  sheet?: VerificationSheet
  /** 历史验收单（v1/v2…；版本化留痕，供复盘与归档） */
  sheetHistory?: VerificationSheet[]
  reviewedAt?: number
  reviewedBy?: ActorRef
  /** pass=验收通过；rework=退回返工（附意见） */
  decision?: 'pass' | 'rework'
  reviewNote?: string
}

/** 下游待同步标记（REQ-2e9473 t19/W8）。 */
export interface DocSyncPending {
  /** 变更源（'requirement' | 'plan'） */
  source: string
  /** 待同步的下游产物种类（'plan' | 'decomposition'） */
  downstream: string[]
  /** 变更原因（人读） */
  reason: string
  at: number
}

// ArchiveDoc 类型迁至 domain/artifact/ArtifactSpec.ts（t2），顶部再导出。

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
/**
 * 归档对**项目说明书**（金字塔 L1）的更新点。
 *
 * 用户要求「归档后应该是金字塔模型，是项目的一个说明书，agent 可以通过这个更了解项目」：
 * 归档不只是留证据，而是让项目认知**自下而上生长**——L3 证据（需求档案）→ L2 领域篇
 * （architecture/guides/adr/rfcs）→ L1 说明书（docs/architecture/project-manual.md）。
 * 改变了项目级认知的需求，必须在归档材料里申报它更新了说明书的哪一节。
 */
export interface ManualUpdate {
  /** 被更新的说明书/领域篇路径（L1 或 L2） */
  path: string
  /** 章节标题 */
  section: string
  /** 一句话：这一节现在多了什么认知 */
  summary: string
}

export interface ArchiveRecord {
  /** 需求目录（工作区相对路径，如 docs/requirements/REQ-xxxxxx） */
  dir: string
  /** 目录内保留的文档清单 */
  docs: ArchiveDoc[]
  /** 合并进的项目文档路径（架构/指南/ADR/研究/已知问题） */
  mergedInto: string[]
  /** 索引条目：一句话结论（进归档索引，供检索） */
  indexEntry: string
  /** 对项目说明书（金字塔 L1/L2）的更新点；无项目级认知变化时留空并写 manualNote */
  manualUpdates?: ManualUpdate[]
  /** 无手册更新时的理由（如"纯维护，不改变项目认知"） */
  manualNote?: string
  submittedAt: number
  submittedBy: ActorRef
  archivedAt?: number
  archivedBy?: ActorRef
}

/** 计划是否已被批准（拆分的代码级前置条件）。 */
export function planApproved(req: { plan?: PlanRecord }): boolean {
  return req.plan !== undefined && req.plan.approvedAt !== undefined
}

// VACUOUS_ACCEPTANCE / VERIFIABLE_ANCHOR 与可证伪判定迁至
// domain/task/Acceptability.ts（REQ-47939a t2）：checkAcceptance(key, acceptance)。

/** 计划任务表校验规整（key 唯一；phase/side 合法；标题非空；依赖只能指向**前面已定义**的计划内 key——落库按数组顺序解析，前向引用会在 decompose 时炸（REQ-2e9473 事故 G）；acceptance 可证伪；implementation 必填）。 */
export function normalizePlanTasks(raw: unknown): PlanTask[] {
  if (!Array.isArray(raw) || raw.length === 0) bad('计划必须包含至少 1 个任务（tasks 非空数组）')
  if (raw.length > 50) bad('计划任务过多（≤50）')
  // 两遍校验：第一遍结构（key 唯一/标题/字段规整），第二遍依赖与内容——
  // 保持"key 重复/依赖悬空"优先于"验收标准/实施方案缺失"的报错顺序（向后兼容）。
  const keys = new Set<string>()
  const out: PlanTask[] = []
  raw.forEach((item, i) => {
    const o = (typeof item === 'object' && item !== null ? item : {}) as Record<string, unknown>
    const key = (typeof o.key === 'string' && o.key.trim().length > 0 ? o.key.trim() : 'k' + (i + 1)).slice(0, 40)
    if (keys.has(key)) bad('计划任务 key 重复：' + key)
    keys.add(key)
    const description = o.description === undefined || o.description === null ? '' : String(o.description).trim().slice(0, 4000)
    const acceptance = o.acceptance === undefined || o.acceptance === null ? '' : String(o.acceptance).trim().slice(0, 2000)
    const implementation = o.implementation === undefined || o.implementation === null ? '' : String(o.implementation).trim().slice(0, 4000)
    const executorHint = asExecutorHint(o.executorHint ?? o.executor_hint)
    out.push({
      key,
      title: normalizeTitle(o.title),
      ...(description.length > 0 ? { description } : {}),
      phase: o.phase === undefined ? 'implement' : asTaskPhase(o.phase),
      side: o.side === undefined ? 'fullstack' : asTaskSide(o.side),
      dependsOn: asDependsOn(o.dependsOn ?? o.depends_on),
      ...(acceptance.length > 0 ? { acceptance } : {}),
      ...(implementation.length > 0 ? { implementation } : {}),
      ...(executorHint !== undefined ? { executorHint } : {}),
    })
  })
  // 第二遍依赖引用校验（自依赖/悬空/前向引用）——规则在 domain/task/Acceptability.ts（t2）。
  const refCheck = checkPlanTaskReferences(out.map(t => ({ key: t.key, dependsOn: t.dependsOn ?? [] })))
  if (!refCheck.ok) bad(refCheck.reason)
  for (const t of out) {
    const acc = checkAcceptance(t.key, t.acceptance ?? '')
    if (!acc.ok) bad(acc.reason)
    if ((t.implementation ?? '').length === 0) {
      bad('计划任务 ' + t.key + ' 缺实施方案（implementation）——拆分卡 ≠ 实施卡：写清改哪些文件、步骤、验证方式，批准计划即批准怎么做')
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

// RequirementCategory 类型迁至 domain/requirement/Requirement.ts（t2），顶部再导出。
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
  docLinks?: { requirement?: string; ui?: string; proposal?: string; extras?: Array<{ label: string; path: string }> }
  status: RequirementStatus
  blocked: boolean
  blockedReason?: string
  /** 手动中断：编排器跳过本需求的自动派发 */
  paused?: boolean
  /** 评审共创会话 */
  reviewSessionId?: string
  /** 立项来源窗口（自动立项时写入；人工建卡不填）——窗口↔需求 n:n 的需求侧锚点 */
  sourceSessionId?: string
  // C6（REQ-47939a t10）：预留字段 projectId / parentId 已删除——全仓引用 0、从未落过盘，
  // 只有类型声明会让读代码的人以为功能存在（design/migration.md §2 C6）。历史数据里若残留
  // 这两个键，由迁移脚本删除（scripts/migrate-ledger.ts C6）。
  /** 节点产物登记（t4 钩子写入；五道人工确认门的确认状态在此） */
  artifacts?: StageArtifact[]
  /** 归档后的目录路径 */
  archivePath?: string
  /**
   * 状态事件时间线（创建 + 每次转移一条）。新转移一律实时写入真实事件；
   * **老记录由 v4→v5 迁移一次性补齐**（inferred=true，算法见 domain/legacy/LegacyStatus.ts）——
   * t10 起运行时读路径不再做回填（此前每次 load 都补，见 design/migration.md C4）。
   * 仍标可选：未迁移的 v4 台账必须继续可载入（§5 兼容读策略）。
   */
  statusHistory?: StatusEvent[]
  /** 实施计划（plan mode）：拆分前提交、由人批准；未批准不允许拆分 */
  plan?: PlanRecord
  /**
   * 文档演进留痕（REQ-2e9473 t19/W8）：上游文档变更 → 下游文档"待同步"标记。
   * 上游 requirement 变更 → plan/decomposition 待同步；plan 变更 → decomposition 待同步。
   * 下游重交（plan_submit/decompose）后销标；未销标时推进/验收给出警告。
   */
  docSyncPending?: DocSyncPending[]
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

/** task_report 的结构化摘要（done 凭证门读取）。 */
export interface TaskReportSummary {
  at: number
  reportIndex: number
  filesChanged: string[]
  completed: string[]
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
  /** 实施方案（REQ-2e9473 W5，decompose 从 PlanTask 透传）：怎么做——改哪些文件、步骤、验证方式 */
  implementation?: string
  /** 需求背景摘要（自足执行用） */
  context: string
  /** 上游产出摘要（handoff：下游窗口不读上游会话） */
  dependsSummary?: string
  /**
   * 最近一次 task_report 的结构化摘要（REQ-2e9473 t06 done 凭证门的证据源）：
   * 汇报即留痕——转 done 前必须存在且 filesChanged/completed 至少其一非空。
   */
  lastReport?: TaskReportSummary
  /** 执行方式提示（decompose 从 PlanTask 透传） */
  executorHint?: ExecutorHint
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

// C1（REQ-47939a t10）：账本契约版本 4 → 5。改的是**契约版本常量**，不是读路径兼容分支——
// 迁移后文件里写的就是 5，常量必须与之一致，否则 load 会把 5 报告成 4、并在下一次写盘时把
// 版本回退（迁移成果被静默抹掉）。⚠️ 运行时**不自动迁移**（见 design/migration.md §5）：
// v4 台账仍可载入（字段缺失处按可选处理），迁移由人工跑 scripts/migrate-ledger.ts 完成。
export const REQBOARD_SCHEMA_VERSION = 5

export interface ReqboardLedger {
  schemaVersion: number
  revision: number
  requirements: RequirementRecord[]
  tasks: TaskRecord[]
  triages: TriageRecord[]
  /**
   * 迁移留痕（C2，REQ-47939a t10）：这份台账何时被谁升到过哪个版本。
   * 迁移脚本写入；运行时只读不写。
   */
  migrations?: { from: number; to: number; at: number; by: string }[]
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
  if (t.length > LIMITS.titleMax) bad('title 超长（≤' + LIMITS.titleMax + ' 字符）')
  return t
}

export function normalizeText(raw: unknown, field: string, max = LIMITS.textMax): string {
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

// 历史回填（parseTransitionTarget / backfill* / migrateRequirementStatusNames）已迁至
// src/domain/legacy/LegacyStatus.ts（REQ-47939a t10）——只由迁移脚本/用例复用；
// 运行时读路径不再做时间线回填与状态名兜底（v5 台账已固化）。

// ---------------------------------------------------------------------------
// 归档文档规范（不同问题如何记录文档 —— 校验的唯一依据）
// ---------------------------------------------------------------------------

// ArchiveDocRule 接口与 ARCHIVE_DOC_RULES 迁至 domain/artifact/ArtifactSpec.ts（t2），
// 顶部再导出（assertArchiveMaterials 仍在本文件消费它）。

/** 需求目录约定（校验用）：docs/requirements/REQ-xxxxxx 或 agent-dh/docs/requirements/REQ-xxxxxx。 */
export const REQUIREMENT_DIR_PATTERN = /(?:^|\/)docs\/requirements\/REQ-[0-9a-f]{6}$/

/** 归档材料校验（缺项抛 code=invalid_input，消息指明缺什么）。 */
export function assertArchiveMaterials(
  category: RequirementCategory | undefined,
  archive: Pick<ArchiveRecord, 'dir' | 'docs' | 'mergedInto' | 'indexEntry' | 'manualUpdates' | 'manualNote'>,
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
  // 金字塔生长：改变项目级认知的类型必须申报"说明书更新点"，否则项目认知永远长不上去
  const manual = archive.manualUpdates ?? []
  if (rule.requireManual && manual.length === 0) {
    bad('归档材料缺少项目说明书更新点（manualUpdates）——' + (category ?? 'feature')
      + ' 类需求改变了项目级认知，必须说明更新了 docs/architecture/project-manual.md（L1）'
      + '或对应领域篇（L2）的哪一节；确实没有认知变化时改用不需要申报的类型，或先在手册里补一节')
  }
  for (const u of manual) {
    if (u.path.trim().length === 0 || u.section.trim().length === 0 || u.summary.trim().length === 0) {
      bad('说明书更新点必须写全 path / section / summary（哪一份文档、哪一节、多了什么认知）')
    }
  }
}
