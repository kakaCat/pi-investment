// 公告板数据聚合服务
// 职责：从 Agent OS memory 拉取 RFC 009 公告板帖子（tag office:board，与 board_* 工具同源），
// 按 board_read 口径归一 + 过滤 + 计数 + 分页，产出 BulletinData 信封。
// 降级（RFC D4）：Agent OS 不可达/超时 → 不抛错，返回 degraded:true 空数据（页面顶部降级 banner），
// 仅未预期异常由路由层兜底 500。

import type {
  BoardStatus,
  BulletinCounts,
  BulletinData,
  BulletinQuery,
  Post,
} from '../types/index.js'

export interface AggregationOptions {
  agentOsBaseURL: string
  requestTimeoutMs: number
}

export class BulletinAggregationService {
  constructor(private readonly options: AggregationOptions) {}

  async fetchBulletin(query: BulletinQuery = {}): Promise<BulletinData> {
    const { agentOsBaseURL, requestTimeoutMs } = this.options
    const nowIso = new Date().toISOString()
    const emptyCounts: BulletinCounts = { open: 0, claimed: 0, paused: 0, blocked: 0, done: 0, dropped: 0, archived: 0 }

    let rawMemories: any[]
    try {
      rawMemories = await this.fetchBoardMemories(agentOsBaseURL, requestTimeoutMs)
    } catch (err) {
      // 降级：Agent OS 不可达 —— 页面正常渲染 + degraded banner，绝不白屏（RFC D4）
      return {
        posts: [], total: 0, page: 1, page_size: query.page_size ?? 20,
        counts: emptyCounts, staleActive: 0, degraded: true,
        error: err instanceof Error ? err.message : String(err),
        fetchedAt: nowIso, rangeNote: '',
      }
    }

    const posts: Post[] = rawMemories.map((m: any) => this.normalize(m))
    // RFC D5：语义检索序不稳 → 页面端统一 created_at 降序重排，保证翻页稳定
    posts.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))

    // counts：对拉取全集（≤200）按状态归桶（页面 header 全局计数，与当前筛选无关）
    const counts: BulletinCounts = { ...emptyCounts }
    let staleActive = 0
    for (const p of posts) {
      const s = p.status
      counts[s] = (counts[s] ?? 0) + 1
      if (ACTIVE_STATUS_SET.has(s) && p.stale) staleActive += 1
    }

    // 过滤（镜像 board_read：status 集合 / kind / assignee）
    const statusSet = resolveStatusSet(query.status)
    let filtered = posts
    if (statusSet !== null) filtered = filtered.filter((p) => statusSet.has(p.status))
    if (query.kind) filtered = filtered.filter((p) => p.kind === query.kind)
    if (query.assignee) filtered = filtered.filter((p) => p.assignee === query.assignee)

    const total = filtered.length
    const page = Math.max(1, Math.trunc(Number(query.page) || 1))
    const pageSize = Math.min(50, Math.max(1, Math.trunc(Number(query.page_size) || 20)))
    const slice = filtered.slice((page - 1) * pageSize, page * pageSize)

    const degraded = false
    return {
      posts: slice, total, page, page_size: pageSize,
      counts, staleActive, degraded,
      fetchedAt: nowIso,
      rangeNote: rawMemories.length >= 200 ? '引擎搜索上限 200，仅展示最近 200 条' : '',
    }
  }

  /** 拉取 memory 全集：一次 include_closed=true，counts/活跃/终态同快照 */
  private async fetchBoardMemories(baseURL: string, timeoutMs: number): Promise<any[]> {
    const url = baseURL + '/api/v1/memory/search?q=board&tag=office:board&limit=200&include_closed=true'
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    let res: Response
    try {
      res = await fetch(url, { signal: controller.signal, headers: { accept: 'application/json' } })
    } catch (err: unknown) {
      clearTimeout(timer)
      const e = err as { name?: string; message?: string; cause?: { code?: string } }
      if (e?.name === 'AbortError') throw new Error('Agent OS 请求超时(>' + timeoutMs + 'ms): ' + url)
      const code = (e as { cause?: { code?: string } })?.cause?.code ?? (e as { code?: string })?.code
      if (code === 'ECONNREFUSED') throw new Error('Agent OS 连接被拒绝(ECONNREFUSED): ' + baseURL)
      throw new Error('Agent OS 请求失败: ' + (e?.message ?? String(err)))
    } finally {
      clearTimeout(timer)
    }
    if (!res.ok) throw new Error('Agent OS HTTP ' + res.status + ': ' + url)
    const text = await res.text()
    let json: any = null
    try { json = text ? JSON.parse(text) : null } catch { json = null }
    const memories = json?.memories ?? json?.data?.memories ?? []
    return Array.isArray(memories) ? memories : []
  }

  /** 归一为 Post（派生规则与 board_read 逐一对应，页面不读 metadata） */
  private normalize(m: any): Post {
    const md = (m?.metadata && typeof m.metadata === 'object' ? m.metadata : {}) as Record<string, any>
    const createdAt = new Date(m?.created_at ?? '')
    const now = new Date()
    const ageHours = Number.isNaN(createdAt.getTime())
      ? 0
      : Math.floor((now.getTime() - createdAt.getTime()) / (1000 * 60 * 60))
    const claimedAtRaw = md.claimed_at
    const claimedAt = claimedAtRaw ? new Date(String(claimedAtRaw)) : null
    let stale = false
    if (claimedAt && !Number.isNaN(claimedAt.getTime())) {
      stale = Math.floor((now.getTime() - claimedAt.getTime()) / (1000 * 60 * 60)) > 48
    } else {
      stale = ageHours > 72
    }
    const log = Array.isArray(md.moderation_log) ? md.moderation_log : []
    return {
      id: String(m?.id ?? ''),
      title: String(md.display_title ?? m?.title ?? '(无标题)'),
      content: String(m?.content ?? ''),
      status: (BULLETIN_STATUS_SET.has(md.board_status) ? md.board_status : 'open') as BoardStatus,
      kind: BOARD_KIND_SET.has(md.kind) ? (md.kind as Post['kind']) : undefined,
      author: md.author ?? null,
      assignee: md.assignee ?? null,
      revision: Number(md.revision) || 1,
      claim_count: Number(md.claim_count) || 0,
      age_hours: ageHours,
      stale,
      created_at: String(m?.created_at ?? ''),
      claimed_at: claimedAtRaw ? String(claimedAtRaw) : null,
      closed_at: md.closed_at ? String(md.closed_at) : null,
      drop_reason: md.drop_reason ?? null,
      moderation_log: log.map((e: any) => ({
        timestamp: String(e?.timestamp ?? ''),
        action: String(e?.action ?? ''),
        actor: String(e?.actor ?? ''),
        note: e?.note ?? null,
      })),
    }
  }
}

const BULLETIN_STATUS_SET: Set<BoardStatus> = new Set(['open', 'claimed', 'paused', 'blocked', 'done', 'dropped', 'archived'])
const ACTIVE_STATUS_SET: Set<BoardStatus> = new Set(['open', 'claimed', 'paused', 'blocked'])
const BOARD_KIND_SET = new Set<NonNullable<Post['kind']>>(['finding', 'question', 'review', 'proposal'])

/** status 参数 → 内部状态集合；unknown → 空集（结果为空但不报错） */
function resolveStatusSet(status?: string): Set<BoardStatus> | null {
  if (!status || status === 'all') return null
  if (status === 'active') return new Set(ACTIVE_STATUS_SET)
  const single = status as BoardStatus
  return BULLETIN_STATUS_SET.has(single) ? new Set([single]) : new Set()
}