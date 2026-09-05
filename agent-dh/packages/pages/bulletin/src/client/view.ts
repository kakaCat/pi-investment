/**
 * 公告板视图（纯函数 innerHTML 构建，RFC 013 §6）。
 * 渲染只读：buildBoardHtml → 整板 innerHTML；buildPostsHtml / buildPaginationHtml →
 * 供「纯视图切换（状态 tab / kind pill / 翻页）局部替换 #dsh-bbd-posts 与 #dsh-bbd-pg」
 * （RFC D3 局部刷新铁律：数据拉取才整体重绘，切换只动卡根）。
 * 帖子卡手风琴：默认 content 3 行截断，点击卡片展开全文 + moderation_log（expanded 集合控制）。
 * 色板与持仓看板同源（--dsw-* tokens + 固定状态色），类名 dsh-bbd-* 不与既有看板冲突。
 *
 * @module dashboard-bulletin/client/view
 */
import type { BulletinCounts, BulletinData, KindKey, Post, StatusKey } from './types.js'

/* ------------------------------------------------------------------ utils */
const esc = (s: unknown): string =>
  String(s ?? '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m] ?? m))

const fmtClock = (ts?: string | null): string => {
  if (!ts) return '—'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return String(ts).slice(0, 16).replace('T', ' ')
  const p = (n: number): string => String(n).padStart(2, '0')
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes())
}

/* ------------------------------------------------------------ label 映射 */
const STATUS_TEXT: Record<string, string> = {
  open: '待认领', claimed: '已认领', paused: '暂停', blocked: '卡住',
  done: '已完成', dropped: '已删除', archived: '已归档',
}
const STATUS_CLS: Record<string, string> = {
  open: 'amber', claimed: 'blue', paused: 'gray', blocked: 'red', done: 'green', dropped: 'gray', archived: 'gray',
}
const KIND_TEXT: Record<string, string> = {
  finding: '发现', question: '疑问', review: '复盘', proposal: '倡议',
}
const KIND_CLS: Record<string, string> = {
  finding: 'finding', question: 'question', review: 'review', proposal: 'proposal',
}

const STATUS_TABS: { key: StatusKey; label: string }[] = [
  { key: 'active', label: '悬赏池' },
  { key: 'open', label: '待认领' },
  { key: 'claimed', label: '已认领' },
  { key: 'paused', label: '暂停' },
  { key: 'blocked', label: '卡住' },
  { key: 'done', label: '已完成' },
  { key: 'dropped', label: '已删除' },
  { key: 'all', label: '全部' },
]
const KIND_TABS: { key: KindKey; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'finding', label: '发现' },
  { key: 'question', label: '疑问' },
  { key: 'review', label: '复盘' },
  { key: 'proposal', label: '倡议' },
]

const sumCounts = (c: BulletinCounts): number =>
  (Number(c.open) || 0) + (Number(c.claimed) || 0) + (Number(c.paused) || 0) + (Number(c.blocked) || 0) +
  (Number(c.done) || 0) + (Number(c.dropped) || 0) + (Number(c.archived) || 0)

/** status tab 显示计数：active=open+claimed+paused+blocked；all=全部；单状态=自身 */
function tabCount(c: BulletinCounts, key: StatusKey): number {
  const n = (v: number | undefined): number => Number(v) || 0
  switch (key) {
    case 'active': return n(c.open) + n(c.claimed) + n(c.paused) + n(c.blocked)
    case 'all': return sumCounts(c)
    default: return n(c[key])
  }
}

export interface ViewState {
  status: StatusKey
  kind: KindKey
  /** 1-based */
  page: number
}

/* ------------------------------------------------------------------ posts */
function buildPostCard(p: Post, expanded: boolean): string {
  const kindTag = p.kind
    ? '<span class="dsh-bbd-kind ' + KIND_CLS[p.kind] + '">' + esc(KIND_TEXT[p.kind] ?? p.kind) + '</span>'
    : ''
  const bounty = p.status === 'open' ? '<span class="dsh-bbd-badge bounty">悬赏</span>' : ''
  const staleTag = p.stale ? '<span class="dsh-bbd-badge stale">滞留超时</span>' : ''
  const statusCls = STATUS_CLS[p.status] ?? 'gray'
  const statusText = STATUS_TEXT[p.status] ?? p.status
  const author = p.author ? esc(p.author) : '<span class="dim">—</span>'
  const assignee = p.assignee ? esc(p.assignee) : '<span class="dim">未认领</span>'
  const logHtml = (p.moderation_log?.length ?? 0) > 0
    ? '<div class="dsh-bbd-log"><div class="dsh-bbd-log-hd">变更记录</div>' +
      p.moderation_log.map((e) =>
        '<div class="dsh-bbd-log-row"><b>' + esc(e.action) + '</b> · ' + esc(e.actor) +
        ' · ' + fmtClock(e.timestamp) + (e.note ? ' — ' + esc(e.note) : '') + '</div>'
      ).join('') + '</div>'
    : ''
  const closedInfo = p.status === 'done' && p.closed_at
    ? '<span class="dim"> · 完成于 ' + fmtClock(p.closed_at) + '</span>' : ''
  const closedInfo2 = p.status === 'dropped' && p.drop_reason
    ? '<div class="dsh-bbd-drop">删除原因：' + esc(p.drop_reason) + '</div>' : ''
  const exp = expanded ? ' exp' : ''
  return (
    '<article class="dsh-bbd-post ' + statusCls + exp + '" data-bbd-id="' + esc(p.id) + '" title="点击展开/收起全文">' +
      '<div class="dsh-bbd-bar"></div>' +
      '<div class="dsh-bbd-body">' +
        '<div class="dsh-bbd-meta-top">' +
          '<span class="dsh-bbd-status ' + statusCls + '">' + esc(statusText) + '</span>' +
          kindTag + bounty + staleTag +
        '</div>' +
        '<h3 class="dsh-bbd-title">' + esc(p.title) + '</h3>' +
        '<div class="dsh-bbd-content">' + esc(p.content) + '</div>' +
        closedInfo2 +
        '<div class="dsh-bbd-meta">' +
          '作者 <b>' + author + '</b> · 认领人 <b>' + assignee + '</b> · 认领 ' + (Number(p.claim_count) || 0) + ' 次' +
          ' · 上报 ' + fmtClock(p.created_at) + ' · v' + (Number(p.revision) || 1) + closedInfo +
        '</div>' +
        logHtml +
      '</div>' +
    '</article>'
  )
}

/** 帖子流卡根（id=dsh-bbd-posts）——局部替换的唯一目标（RFC D3） */
export function buildPostsHtml(posts: Post[], expanded: ReadonlySet<string>): string {
  if (!Array.isArray(posts) || posts.length === 0) {
    return '<section id="dsh-bbd-posts" class="dsh-bbd-posts"><div class="dsh-bbd-emptybox">当前筛选下暂无帖子</div></section>'
  }
  return '<section id="dsh-bbd-posts" class="dsh-bbd-posts">' + posts.map((p) => buildPostCard(p, expanded.has(p.id))).join('') + '</section>'
}

/** 分页条（id=dsh-bbd-pg）——与卡根一起被局部替换 */
export function buildPaginationHtml(data: BulletinData): string {
  const pageSize = data.page_size || 20
  const pages = Math.max(1, Math.ceil((Number(data.total) || 0) / pageSize))
  const cur = Math.min(Math.max(1, Number(data.page) || 1), pages)
  const nums: string[] = []
  for (let i = 1; i <= pages; i++) {
    nums.push('<button type="button" class="dsh-bbd-pgb' + (i === cur ? ' act' : '') + '" data-bbd-page="' + i + '"' +
      (i === cur ? ' disabled' : '') + '>' + i + '</button>')
  }
  return (
    '<div id="dsh-bbd-pg" class="dsh-bbd-pg">' +
      '<button type="button" class="dsh-bbd-pgnav" data-bbd-page="' + (cur - 1) + '"' + (cur <= 1 ? ' disabled' : '') + '>上一页</button>' +
      '<span class="dsh-bbd-pg-nums">' + nums.join('') + '</span>' +
      '<button type="button" class="dsh-bbd-pgnav" data-bbd-page="' + (cur + 1) + '"' + (cur >= pages ? ' disabled' : '') + '>下一页</button>' +
      '<span class="dsh-bbd-pg-cnt">共 ' + (Number(data.total) || 0) + ' 条 · 第 ' + cur + '/' + pages + ' 页</span>' +
    '</div>' +
    (data.rangeNote ? '<div class="dsh-bbd-rangenote">' + esc(data.rangeNote) + '</div>' : '')
  )
}

/* ------------------------------------------------------------------ board */
/** 整板 innerHTML（打开/轮询/手动刷新整体重绘用；含 header/过滤条/帖子流/分页） */
export function buildBoardHtml(data: BulletinData, vs: ViewState, expanded: ReadonlySet<string>): string {
  const banner = data.degraded
    ? '<div class="dsh-bbd-banner show">数据源（Agent OS）不可达，以下为降级空数据：' + esc(data.error ?? '') +
      ' —— 数据来自 board_post/board_read 工具同源 memory（tag office:board）。</div>'
    : '<div class="dsh-bbd-banner"></div>'

  const statusPills = STATUS_TABS.map((t) =>
    '<button type="button" class="dsh-bbd-pill' + (vs.status === t.key ? ' act' : '') + '" data-bbd-status="' + t.key + '">' +
      esc(t.label) + '<i class="c">' + tabCount(data.counts, t.key) + '</i></button>'
  ).join('')
  const kindPills = KIND_TABS.map((t) =>
    '<button type="button" class="dsh-bbd-pill kind' + (vs.kind === t.key ? ' act' : '') + '" data-bbd-kind="' + t.key + '">' +
      esc(t.label) + '</button>'
  ).join('')
  const staleChip = Number(data.staleActive) > 0
    ? '<span class="dsh-bbd-chip warn">滞留超 48h ' + (Number(data.staleActive) || 0) + '</span>'
    : '<span class="dsh-bbd-chip ok">滞留超 48h 0</span>'

  return (
    '<div class="dsh-bbd-board">' +
      '<div class="dsh-bbd-wrap">' +
        '<div class="dsh-bbd-head">' +
          '<h1 class="dsh-bbd-title">公告板<span class="sub">Agent OS · 只读监控（写入走 board_update 工具）</span></h1>' +
          '<div class="dsh-bbd-tools">' +
            staleChip +
            '<span class="dsh-bbd-updated">更新 <b>' + fmtClock(data.fetchedAt) + '</b> · 30s 轮询</span>' +
            '<button type="button" class="dsh-bbd-refresh" id="dsh-bbd-refresh">↻ 刷新</button>' +
          '</div>' +
        '</div>' +
        banner +
        '<div class="dsh-bbd-filters">' +
          '<div class="dsh-bbd-frow">' + statusPills + '</div>' +
          '<div class="dsh-bbd-frow kind">' + kindPills + '</div>' +
        '</div>' +
        buildPostsHtml(data.posts, expanded) +
        buildPaginationHtml(data) +
      '</div>' +
    '</div>'
  )
}
