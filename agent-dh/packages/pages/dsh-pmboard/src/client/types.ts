/**
 * 项目看板 client 类型 —— 与 host /dashboard/api/reqboard 响应对齐。
 * 字段形状来自 shared/protocol.ts（host 落库记录的原样投影）。
 *
 * @module dsh-pmboard/client/types
 */
import type { StageArtifact, StageKind } from '../shared/protocol.ts'

// 产物/节点键等跨端共享类型复用 protocol 的单一定义（client 不另抄一份）。
export type { ArtifactKind, StageArtifact, StageKey, StageKind } from '../shared/protocol.ts'

// -- 需求 -----------------------------------------------------------------

export type RequirementStatus =
  | 'draft' | 'brainstorming' | 'design' | 'decomposing' | 'implementing'
  | 'accepting' | 'done' | 'archived' | 'canceled'

export type RequirementCategory = 'feature' | 'bug' | 'doc' | 'refactor' | 'spike' | 'chore'

export interface ActorRef { kind: 'human' | 'agent' | 'system'; sessionId?: string }

export interface CommentRecord { id: string; body: string; createdAt: number; createdBy?: ActorRef }

/**
 * 状态事件（时间线）：需求/任务每次进入某状态的记录。
 * inferred=true 表示升级前老记录由 createdAt + 评论反推的**回填**事件（非原始记录）。
 */
export interface StatusEvent {
  status: string
  at: number
  by: ActorRef
  reason?: string
  inferred?: boolean
}

/** 计划任务条目（plan mode：拆分前就定死的粒度） */
export interface PlanTask {
  key: string
  title: string
  description?: string
  phase?: TaskPhase
  side?: TaskSide
  dependsOn?: string[]
  acceptance?: string
}

/** 拆分计划：提交 → 人批准/退回；未批准不允许拆分 */
export interface PlanRecord {
  path: string
  summary: string
  tasks: PlanTask[]
  submittedAt: number
  submittedBy: ActorRef
  approvedAt?: number
  approvedBy?: ActorRef
  rejectedAt?: number
  rejectedReason?: string
}

/**
 * 验收覆盖记录（REQ-a8d582 FR-4）：与 shared/protocol.ts 同形，client 侧独立声明。
 * 挂在需求级：无材料通过时没有 verification 对象可挂。
 */
export interface AcceptanceOverride {
  at: number
  by: ActorRef
  detail: string
  failed: number
  pending: number
  noMaterials: boolean
}

/** 验收材料（agent 提交）+ 人工审核结论 */
export interface VerificationRecord {
  summary: string
  evidence: string[]
  submittedAt: number
  submittedBy: ActorRef
  /** 验收单（REQ-2e9473 t14/W6 逐项确认） */
  sheet?: VerificationSheet
  sheetHistory?: VerificationSheet[]
  reviewedAt?: number
  reviewedBy?: ActorRef
  decision?: 'pass' | 'rework'
  reviewNote?: string
}

/** 验收单单项（逐项裁决）。 */
export interface VerificationItem {
  id: string
  /** 来源（v5 判别联合）：需求级 / 具体任务 */
  source: { kind: 'requirement' } | { kind: 'task'; taskId: string }
  criterion: string
  evidence: string[]
  status: 'pending' | 'passed' | 'failed'
  opinion?: string
  decidedAt?: number
}

/** 验收单（版本化，可挂起/续验）。 */
export interface VerificationSheet {
  version: number
  items: VerificationItem[]
  generatedAt: number
  reworkOnly?: boolean
}

/** 归档文档条目 */
export interface ArchiveDoc {
  kind: 'requirement' | 'plan' | 'verification' | 'retro' | 'notes'
  path: string
}

/** 归档材料（agent 准备）+ 归档结论（人） */
/** 归档对项目说明书（金字塔 L1/L2）的更新点 */
export interface ManualUpdate {
  path: string
  section: string
  summary: string
}

export interface ArchiveRecord {
  dir: string
  docs: ArchiveDoc[]
  mergedInto: string[]
  indexEntry: string
  manualUpdates?: ManualUpdate[]
  manualNote?: string
  submittedAt: number
  submittedBy: ActorRef
  archivedAt?: number
  archivedBy?: ActorRef
}

export interface RequirementRecord {
  id: string
  title: string
  description: string
  category?: RequirementCategory
  docLinks?: { requirement?: string; ui?: string; proposal?: string; extras?: Array<{ label: string; path: string }> }
  status: RequirementStatus
  blocked: boolean
  blockedReason?: string
  paused?: boolean
  /**
   * 自动链开关（REQ-4842fe FR-12）：true=自动链运行中；false=暂停（失败/熔断/人工关闭）；
   * **缺省 = 未开启**（存量需求读出即旧行为，看板据此标 [手动]）。
   */
  autoRun?: boolean
  /** 推进事件运行状态（停滞计数 / 暂停原因 / 事件历史；缺省 = 未跑过自动链） */
  advance?: {
    lockAt?: number
    history?: unknown[]
    noopStreak?: number
    failureStreak?: number
    pausedReason?: string
  }
  reviewSessionId?: string
  /** 立项来源窗口（agent 会话 id，如 session-<uuid>；人工建卡不填）——窗口↔需求关联锚点 */
  sourceSessionId?: string
  archivePath?: string
  /** 已登记产物（五道人工确认门的判定输入；缺省=未登记，见 shared/protocol.ts） */
  artifacts?: StageArtifact[]
  /** 拆分计划（plan mode） */
  plan?: PlanRecord
  /** 验收材料（提交+人工审核结论） */
  verification?: VerificationRecord
  /** 覆盖式通过留痕（REQ-a8d582 FR-4）：缺省 = 无覆盖 */
  acceptanceOverride?: AcceptanceOverride
  /** 归档材料（准备+归档结论） */
  archive?: ArchiveRecord
  /** 状态事件时间线（创建 + 每次转移） */
  statusHistory?: StatusEvent[]
  comments: CommentRecord[]
  version: number
  createdAt: number
  updatedAt: number
  createdBy: ActorRef
  updatedBy: ActorRef
}

// -- 任务 -----------------------------------------------------------------

export type TaskStatus =
  | 'todo' | 'in_progress' | 'integrating' | 'testing' | 'in_review' | 'done' | 'canceled'

export type TaskPhase = 'doc' | 'ui' | 'analysis' | 'implement' | 'test' | 'review' | 'merge'
export type TaskSide = 'frontend' | 'backend' | 'fullstack' | 'doc'

export interface ExecutionRecord {
  id: string
  sessionId?: string
  trigger: 'manual' | 'auto'
  startedAt: number
  endedAt?: number
  outcome: 'running' | 'succeeded' | 'failed' | 'cancelled'
  error?: string
  evidence?: string[]
}

export interface TaskRecord {
  id: string
  requirementId: string
  title: string
  description: string
  phase: TaskPhase
  side: TaskSide
  dependsOn: string[]
  scope: { apis: string[]; tables: string[]; files: string[] }
  acceptance: string
  context: string
  skipIntegration?: boolean
  /** 有值 = 子卡（指向父卡 id）；父卡不存子卡列表，由 parentId 反查（单一事实源） */
  parentId?: string
  /** 子卡阶段（子卡必填；父卡/存量卡不得有） */
  stageKind?: StageKind
  /** 失败重跑次数（缺省 0） */
  attempt?: number
  status: TaskStatus
  blocked: boolean
  blockedReason?: string
  claimedBy?: string
  claimedAt?: number
  executions: ExecutionRecord[]
  /** 状态事件时间线（甘特图按状态分段着色） */
  statusHistory?: StatusEvent[]
  comments: CommentRecord[]
  version: number
  createdAt: number
  updatedAt: number
  createdBy: ActorRef
  updatedBy: ActorRef
}

// -- 待归类（triage）-------------------------------------------------------

export type TriageStatus = 'pending' | 'confirmed' | 'rejected'

export interface TriageRecord {
  id: string
  sessionId: string
  firstMessageText: string
  suggestedAction: 'create_req' | 'bind_req' | 'bind_task'
  suggestedTargetId?: string
  /** Agent/LLM 建议的需求标题（create_req；可编辑建议卡预填） */
  suggestedTitle?: string
  /** Agent/LLM 建议的需求分类（create_req；可编辑建议卡预填） */
  suggestedCategory?: RequirementCategory
  /** 匹配分数 0-100（agent 显式提议=100，启发式匹配=低值） */
  score: number
  status: TriageStatus
  createdAt: number
  resolvedAt?: number
  resolvedBy?: ActorRef
  resultRequirementId?: string
  comments: CommentRecord[]
}

// -- 看板数据 -------------------------------------------------------------

export interface BoardState {
  revision: number
  requirements: RequirementRecord[]
  tasks: TaskRecord[]
  /** 需求 id → ready 任务 id 列表（host 派生） */
  ready: Record<string, string[]>
  /** REQ-a33899：需求 id → 累计 token（无快照的需求不出现该键；缺失 ≠ 0） */
  tokenTotals?: Record<string, number>
}

export interface TriageList {
  pending: TriageRecord[]
  resolved: TriageRecord[]
}

/** 需求卡片在泳道列上的紧凑投影（视图层用，避免全量渲染） */
export interface ReqCard {
  req: RequirementRecord
  tasks: TaskRecord[]
  doneCount: number
  totalCount: number
  readyIds: string[]
  blocked: boolean
  /** REQ-a33899：累计 token；undefined = 无快照（不渲染徽章，也不显示 0） */
  tokenTotal?: number
}
