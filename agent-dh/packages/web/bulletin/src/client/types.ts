// 公告板 client 类型（与 host src/types/index.ts 同构子集；两端各自声明防循环依赖）
// 状态/kind 语义与 board_* 工具一致（lifecycle/board-tools.ts）：
// 未带 metadata.board_status 的记录缺省归 open；stale/age 派生同工具公式。

export const BULLETIN_STATUSES = ['open', 'claimed', 'paused', 'blocked', 'done', 'dropped', 'archived'] as const
export type BoardStatus = (typeof BULLETIN_STATUSES)[number]
export const ACTIVE_STATUSES: BoardStatus[] = ['open', 'claimed', 'paused', 'blocked']
export const BOARD_KINDS = ['finding', 'question', 'review', 'proposal'] as const
export type BoardKind = (typeof BOARD_KINDS)[number]

export interface ModerationLogEntry {
  timestamp: string
  action: string
  actor: string
  note?: string | null
}

export interface Post {
  id: string
  title: string
  content: string
  status: BoardStatus
  kind?: BoardKind
  author?: string | null
  assignee?: string | null
  revision: number
  claim_count: number
  age_hours: number
  stale: boolean
  created_at: string
  claimed_at?: string | null
  closed_at?: string | null
  drop_reason?: string | null
  moderation_log: ModerationLogEntry[]
}

export interface BulletinCounts {
  open: number
  claimed: number
  paused: number
  blocked: number
  done: number
  dropped: number
  archived: number
}

export interface BulletinData {
  posts: Post[]
  total: number
  page: number
  page_size: number
  counts: BulletinCounts
  staleActive: number
  degraded: boolean
  error?: string
  fetchedAt: string
  rangeNote?: string
}

/** 状态 tab key（与 host API status 参数同值） */
export type StatusKey = 'active' | 'open' | 'claimed' | 'paused' | 'blocked' | 'done' | 'dropped' | 'all'
/** kind pill key；'all' 不过滤 */
export type KindKey = 'all' | BoardKind
