// 公告板数据契约（host 半类型；client 半在 src/client/types.ts 镜像同构子集）
// GET /dashboard/api/bulletin/posts?status=active|open|claimed|paused|blocked|done|dropped|all
//      &kind=finding|question|review|proposal&assignee=w-xxx&page=1&page_size=20
// 响应：{ success: true, data: BulletinData } | { success: false, error }
// 状态/kind 语义与 board_read/board_post/board_update 工具（lifecycle/board-tools.ts）一致：
// 未带 metadata.board_status 的记录缺省归 open（与工具同口径）；stale/age 派生同工具公式。

/** 帖子状态（RFC 009 STATE_MACHINE 全集；archive 仅 all 可见） */
export const BULLETIN_STATUSES = ['open', 'claimed', 'paused', 'blocked', 'done', 'dropped', 'archived'] as const
export type BoardStatus = (typeof BULLETIN_STATUSES)[number]
/** 活跃集合（= board_read 的 active 口径：悬赏池/处理中） */
export const ACTIVE_STATUSES: BoardStatus[] = ['open', 'claimed', 'paused', 'blocked']

/** 帖子类型（RFC 009 kind 枚举） */
export const BOARD_KINDS = ['finding', 'question', 'review', 'proposal'] as const
export type BoardKind = (typeof BOARD_KINDS)[number]

/** 归一化帖子（页面端仅认本派生形状，不直接读 metadata） */
export interface Post {
  id: string
  /** display_title || title */
  title: string
  content: string
  status: BoardStatus
  kind?: BoardKind
  author?: string | null
  assignee?: string | null
  revision: number
  claim_count: number
  /** 距创建小时数（与 board_read 同公式；Agent OS 时间戳带时区偏移可能为负，view 侧钳制展示） */
  age_hours: number
  /** 认领后超 48h 未动 / 未认领创建超 72h → true（与 board_read 同口径） */
  stale: boolean
  created_at: string
  claimed_at?: string | null
  closed_at?: string | null
  drop_reason?: string | null
  moderation_log: { timestamp: string; action: string; actor: string; note?: string | null }[]
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

export interface BulletinQuery {
  /** 不传=active（悬赏池）；active|单状态|all */
  status?: string
  kind?: string
  assignee?: string
  page?: number
  page_size?: number
}

export interface BulletinData {
  posts: Post[]
  /** 当前筛选未分页总数 */
  total: number
  page: number
  page_size: number
  counts: BulletinCounts
  /** 活跃集合内 stale 数（header「滞留超 48h」胶囊） */
  staleActive: number
  /** Agent OS 不可达/超时 → degraded:true + error，页面显示降级 banner（RFC D4） */
  degraded: boolean
  error?: string
  fetchedAt: string
  /** 拉取达到引擎上限（200）时提示 */
  rangeNote?: string
}
