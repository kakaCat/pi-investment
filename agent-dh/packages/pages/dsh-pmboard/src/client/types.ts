/**
 * 项目看板 client 类型 —— 与 host /dashboard/api/reqboard 响应对齐。
 * 字段形状来自 shared/protocol.ts（host 落库记录的原样投影）。
 *
 * @module dsh-pmboard/client/types
 */

// -- 需求 -----------------------------------------------------------------

export type RequirementStatus =
  | 'draft' | 'reviewing' | 'decomposing' | 'implementing'
  | 'accepting' | 'done' | 'archived' | 'canceled'

export type RequirementCategory = 'feature' | 'bug' | 'doc' | 'refactor' | 'spike' | 'chore'

export interface ActorRef { kind: 'human' | 'agent' | 'system'; sessionId?: string }

export interface CommentRecord { id: string; body: string; createdAt: number; createdBy?: ActorRef }

export interface RequirementRecord {
  id: string
  title: string
  description: string
  category?: RequirementCategory
  docLinks?: { requirement?: string; ui?: string; proposal?: string }
  status: RequirementStatus
  blocked: boolean
  blockedReason?: string
  paused?: boolean
  reviewSessionId?: string
  archivePath?: string
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

// -- 待归类（triage）-------------------------------------------------------

export type TriageStatus = 'pending' | 'confirmed' | 'rejected'

export interface TriageRecord {
  id: string
  sessionId: string
  firstMessageText: string
  suggestedAction: 'create_req' | 'bind_req' | 'bind_task'
  suggestedTargetId?: string
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
}
