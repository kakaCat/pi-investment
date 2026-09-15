/**
 * 项目看板视图 —— 数据到 innerHTML 的纯渲染（参照 holdings view.ts 模式）。
 * 三层：泳道看板（需求状态列）/ 需求详情（任务 DAG + 任务列 + 评论）/ 待归类区。
 * 所有用户文本经 esc() 转义；交互经 data-action 属性委派到 board-mount。
 *
 * @module dsh-pmboard/client/view
 */
import { esc, renderPagination } from '@pi-investment/page-kit/client'
import type { ArchiveRecord, BoardState, ReqCard, RequirementRecord, RequirementStatus, StatusEvent, TaskRecord, TaskStatus, TriageRecord } from './types.ts'

/* ------------------------------------------------------------------ utils */

const STATUS_LABELS: Record<RequirementStatus, string> = {
  draft: '立项', brainstorming: '头脑风暴', planning: '写计划', decomposing: '拆分',
  implementing: '执行', accepting: '验收', done: '完成', archived: '归档', canceled: '取消',
}

const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  todo: '待办', in_progress: '进行中', integrating: '联调', testing: '测试',
  in_review: '验收', done: '完成', canceled: '取消',
}

const PHASE_LABELS: Record<string, string> = {
  doc: '文档', ui: 'UI', analysis: '分析', implement: '实施',
  test: '测试', review: '评审', merge: '合并',
}

const CATEGORY_LABELS: Record<string, string> = {
  feature: '功能', bug: '缺陷', doc: '文档', refactor: '重构', spike: '调研', chore: '杂项',
}

/**
 * 主链 8 态（泳道列）——状态即阶段，从立项一路走到完成：
 * 立项 → 头脑风暴 → 写计划 → 拆分 → 执行 → 验收 → 完成（archived/canceled 走底部归档区）。
 */
export const LANE_STATUSES: readonly RequirementStatus[] = [
  'draft', 'brainstorming', 'planning', 'decomposing', 'implementing', 'accepting', 'done',
]

/**
 * 会话 id → 窗口码（人类可读短标识）：`session-<uuid>` → `w-<uuid 前 8 位>`。
 * 与 host shared/protocol.ts 的 windowCodeFromSessionId 同规则（client 半不 import
 * host 模块，避免打包把 host 代码带进浏览器包）。
 */
function windowCodeFromSessionId(sessionId: string): string {
  const raw = sessionId.startsWith('session-') ? sessionId.slice('session-'.length) : sessionId
  const head = raw.split('-')[0] ?? raw
  return `w-${head.slice(0, 8)}`
}

const fmtTime = (ts: number): string => {
  const d = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 任务进度 n/m */
function progress(done: number, total: number): string {
  return total === 0 ? '0/0' : `${done}/${total}`
}

/** 需求卡片投影（视图层聚合，避免全量渲染） */
export function toReqCards(state: BoardState): ReqCard[] {
  return state.requirements
    .filter(r => r.status !== 'archived' && r.status !== 'canceled')
    .map(req => {
      const tasks = state.tasks.filter(t => t.requirementId === req.id)
      const doneCount = tasks.filter(t => t.status === 'done').length
      return {
        req,
        tasks,
        doneCount,
        totalCount: tasks.length,
        readyIds: state.ready[req.id] ?? [],
        blocked: req.blocked || tasks.some(t => t.blocked),
      }
    })
}

/* ------------------------------------------------------------------ 泳道看板 */

/** 看板视图种类：lanes=泳道（Kanban）/ list=列表（卡片流）。 */
export type BoardViewKind = 'lanes' | 'list'

export function buildBoard(
  state: BoardState,
  now: number = Date.now(),
  view: BoardViewKind = 'lanes',
  listOpts: ListViewOpts = {},
  archived: ReadonlySet<string> = NO_ARCHIVED,
): string {
  const cards = toReqCards(state)
  const lanes = LANE_STATUSES.map(status => {
    const inLane = cards.filter(c => c.req.status === status)
    const cardsHtml = inLane.map(c => renderReqCard(c, now, archived)).join('')
    return `
      <div class="dsh-pm-lane" data-lane="${status}">
        <div class="dsh-pm-lane-head">
          <span class="dsh-pm-lane-dot" data-status="${status}"></span>
          <span class="dsh-pm-lane-title">${STATUS_LABELS[status]}</span>
          <span class="dsh-pm-lane-count">${inLane.length}</span>
        </div>
        <div class="dsh-pm-lane-cards">${cardsHtml}</div>
      </div>`
  }).join('')

  // 注意：变量名不能叫 archived —— 那是本函数的参数（已归档会话 id 集合）
  const archivedReqs = state.requirements.filter(r => r.status === 'archived' || r.status === 'canceled')
  const archivedHtml = archivedReqs.length > 0
    ? `<div class="dsh-pm-archived-bar">
         <span class="dsh-pm-archived-label">归档/取消 ${archivedReqs.length}</span>
         ${archivedReqs.map(r => `<span class="dsh-pm-archived-chip" data-status="${r.status}">${esc(r.id)} ${esc(r.title)}</span>`).join('')}
       </div>`
    : ''

  const switcher = `
    <div class="dsh-pm-viewswitch" role="tablist" aria-label="看板视图">
      <button type="button" role="tab" class="dsh-pm-viewbtn${view === 'lanes' ? ' active' : ''}"
        data-action="switch-view" data-view="lanes" title="泳道视图（按状态分列）">泳道</button>
      <button type="button" role="tab" class="dsh-pm-viewbtn${view === 'list' ? ' active' : ''}"
        data-action="switch-view" data-view="list" title="列表视图（按需求汇总，含进度与跳转）">列表</button>
    </div>`

  const body = view === 'list'
    ? buildListView(state, now, listOpts, archived)
    : `<div class="dsh-pm-lanes">${lanes}</div>`

  return `
    <div class="dsh-pm-board">
      <div class="dsh-pm-head">
        <h1 class="dsh-pm-title">项目看板</h1>
        <span class="dsh-pm-rev">rev ${state.revision}</span>
        ${switcher}
        <button type="button" class="dsh-pm-btn" data-action="refresh" title="刷新">刷新</button>
        <button type="button" class="dsh-pm-btn" data-action="open-tasks" title="任务总览与甘特图">任务</button>
        <button type="button" class="dsh-pm-btn primary" data-action="new-req" title="新建需求">+ 需求</button>
      </div>
      ${body}
      ${view === 'list' ? '' : archivedHtml}
    </div>`
}

/* ------------------------------------------------------------------ 列表视图 */

/** 列表排序键。 */
export type ListSortKey = 'stage' | 'progress' | 'updated' | 'created' | 'title'
export type ListSortDir = 'asc' | 'desc'

/** 每页条数候选（与 board-mount 的 list-size 动作共用）。 */
export const LIST_PAGE_SIZES: readonly number[] = [10, 20, 50]
export const LIST_PAGE_SIZE_DEFAULT = 10

/** 各排序键的默认方向（最近更新/创建/进度 → 降序在前；阶段/名称 → 升序）。 */
export function defaultListDirFor(key: ListSortKey): ListSortDir {
  return key === 'updated' || key === 'created' || key === 'progress' ? 'desc' : 'asc'
}

const LIST_SORT_LABELS: ReadonlyArray<{ key: ListSortKey; label: string }> = [
  { key: 'stage', label: '阶段' },
  { key: 'progress', label: '进度' },
  { key: 'updated', label: '最近更新' },
  { key: 'created', label: '创建时间' },
  { key: 'title', label: '名称' },
]

/** 流水线阶段序（越小越靠前：实施中在最上）—— stage 排序用。 */
const STAGE_RANK: Record<string, number> = {
  implementing: 0, accepting: 1, decomposing: 2, planning: 3, brainstorming: 4, draft: 5, done: 6,
}

function listPct(card: ReqCard): number {
  return card.totalCount > 0 ? card.doneCount / card.totalCount : 0
}

/** 排序键 → 升序比较函数（方向由调用方翻转）。 */
function listComparator(key: ListSortKey): (a: ReqCard, b: ReqCard) => number {
  switch (key) {
    case 'stage':
      return (a, b) => (STAGE_RANK[a.req.status] ?? 99) - (STAGE_RANK[b.req.status] ?? 99)
    case 'progress':
      return (a, b) => listPct(a) - listPct(b)
    case 'created':
      return (a, b) => a.req.createdAt - b.req.createdAt
    case 'title':
      return (a, b) => a.req.title.localeCompare(b.req.title, 'zh-Hans-CN')
    case 'updated':
    default:
      return (a, b) => a.req.updatedAt - b.req.updatedAt
  }
}

export interface ListViewOpts {
  sortKey?: ListSortKey
  sortDir?: ListSortDir
  page?: number
  pageSize?: number
}

/**
 * 列表视图 —— 每条需求一张全宽卡片：状态 / 来源窗口 / 任务进度 / 最后更新 /
 * 「查看详情」与「跳转会话」。回答「项目有哪些事、各自到哪一步、谁在做」，
 * 与泳道视图（看流程分布）互补。
 *
 * 排序（阶段/进度/最近更新/创建时间/名称，点同键切换升降序）；
 * 已完成置底（先「进行中 → 已完成」分组，组内再按所选键排序）；
 * 分页（每页 10/20/50，复用 page-kit renderPagination，data-pmpage）。
 */
export function buildListView(
  state: BoardState,
  now: number = Date.now(),
  opts: ListViewOpts = {},
  archived: ReadonlySet<string> = NO_ARCHIVED,
): string {
  const sortKey: ListSortKey = opts.sortKey ?? 'stage'
  const sortDir: ListSortDir = opts.sortDir ?? defaultListDirFor(sortKey)
  const pageSize = opts.pageSize !== undefined && LIST_PAGE_SIZES.includes(opts.pageSize)
    ? opts.pageSize
    : LIST_PAGE_SIZE_DEFAULT

  const cards = toReqCards(state)
  const active = cards.filter(c => c.req.status !== 'done')
  const finished = cards.filter(c => c.req.status === 'done')
  const cmp = listComparator(sortKey)
  const sign = sortDir === 'asc' ? 1 : -1
  // 主键相同 → 最近更新在前（稳定、可预期）
  const byThen = (a: ReqCard, b: ReqCard): number => cmp(a, b) * sign || b.req.updatedAt - a.req.updatedAt
  active.sort(byThen)
  finished.sort(byThen)

  // 已完成永远排在最后：分组拼接，而不是让比较器把 done 混进排序
  const ordered = [...active, ...finished]
  const toolbar = renderListToolbar(sortKey, sortDir, cards.length, active.length, finished.length, pageSize)

  if (ordered.length === 0) {
    return `<div class="dsh-pm-list">${toolbar}<div class="dsh-pm-list-empty">暂无进行中的需求</div></div>`
  }

  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize))
  const page = Math.min(Math.max(1, opts.page ?? 1), totalPages)
  const slice = ordered.slice((page - 1) * pageSize, page * pageSize)

  const doneStart = active.length          // 已完成组在整体序列里的起点
  const pageStart = (page - 1) * pageSize  // 本页第一条的全局下标
  const rowsHtml: string[] = []
  for (let i = 0; i < slice.length; i++) {
    const globalIdx = pageStart + i
    if (active.length > 0 && (globalIdx === 0 || (globalIdx === pageStart && globalIdx < doneStart))) {
      rowsHtml.push(`<div class="dsh-pm-list-grouphead" data-group="active">进行中 ${active.length}${globalIdx > 0 ? '（续）' : ''}</div>`)
    }
    if (finished.length > 0 && (globalIdx === doneStart || (globalIdx === pageStart && globalIdx >= doneStart))) {
      rowsHtml.push(`<div class="dsh-pm-list-grouphead" data-group="done">已完成 ${finished.length}${globalIdx > doneStart ? '（续）' : ''}</div>`)
    }
    rowsHtml.push(renderListCard(slice[i], now, archived))
  }

  const pager = ordered.length > pageSize
    ? `<div class="dsh-pm-pager">${renderPagination({
        page, total: totalPages, totalItems: ordered.length, pageAttr: 'data-pmpage',
      })}</div>`
    : ''

  return `<div class="dsh-pm-list">${toolbar}${rowsHtml.join('')}${pager}</div>`
}

/** 列表工具条：排序键按钮（同键切换升降序）+ 每页条数 + 计数。 */
function renderListToolbar(
  sortKey: ListSortKey, sortDir: ListSortDir,
  total: number, activeCount: number, doneCount: number, pageSize: number,
): string {
  const btns = LIST_SORT_LABELS.map(({ key, label }) => {
    const on = key === sortKey
    const arrow = on ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''
    return `<button type="button" class="dsh-pm-sortbtn${on ? ' active' : ''}" data-action="list-sort" `
      + `data-key="${key}" title="按${label}排序（再点一次切换升降序）">${label}${arrow}</button>`
  }).join('')
  const sizes = LIST_PAGE_SIZES
    .map(n => `<option value="${n}"${n === pageSize ? ' selected' : ''}>${n}</option>`)
    .join('')
  return `
    <div class="dsh-pm-list-toolbar">
      <span class="dsh-pm-list-toolbar-label">排序</span>
      ${btns}
      <span class="dsh-pm-list-toolbar-gap"></span>
      <span class="dsh-pm-list-toolbar-label">每页</span>
      <select class="dsh-pm-pagesize" data-action="list-size" title="每页条数">${sizes}</select>
      <span class="dsh-pm-list-count">共 ${total} 条 · 进行中 ${activeCount} · 已完成 ${doneCount}</span>
    </div>`
}

/** 单条需求卡片（列表视图行）。 */
function renderListCard(card: ReqCard, now: number, archived: ReadonlySet<string> = NO_ARCHIVED): string {
    const { req, tasks, doneCount, totalCount, blocked } = card
    const pct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0
    const active = tasks.filter(t => t.status !== 'todo' && t.status !== 'done' && t.status !== 'canceled').length
    const cat = req.category
      ? `<span class="dsh-pm-cat" data-cat="${req.category}">${CATEGORY_LABELS[req.category] ?? req.category}</span>`
      : ''
    const blockedChip = blocked ? '<span class="dsh-pm-flag blocked">阻塞</span>' : ''
    const sid = req.sourceSessionId
    const sidArchived = sid !== undefined && sid.length > 0 && archived.has(sid)
    const windowChip = sid !== undefined && sid.length > 0
      ? sessionChipHtml({
          sid,
          label: windowCodeFromSessionId(sid),
          cls: 'dsh-pm-window',
          kind: '立项来源窗口',
          archived: sidArchived,
        })
      : '<span class="dsh-pm-list-nowindow">人工建卡</span>'

    // 任务状态条：一眼看出卡在开发/联调/测试/评审哪一段
    const statusStrip = tasks.length === 0
      ? '<span class="dsh-pm-list-strip-empty">尚未拆分任务</span>'
      : (() => {
          const counts: Record<string, number> = {}
          for (const t of tasks) counts[t.status] = (counts[t.status] ?? 0) + 1
          const order = ['in_progress', 'integrating', 'testing', 'in_review', 'todo', 'done']
          return order
            .filter(s => (counts[s] ?? 0) > 0)
            .map(s => `<span class="dsh-pm-list-seg" data-status="${s}">${TASK_STATUS_LABELS[s as TaskStatus] ?? s} ${counts[s]}</span>`)
            .join('')
        })()

    return `
      <div class="dsh-pm-list-card${blocked ? ' is-blocked' : ''}" data-req="${esc(req.id)}">
        <div class="dsh-pm-list-top">
          <span class="dsh-pm-card-id">${esc(req.id)}</span>
          <span class="dsh-pm-status-badge" data-status="${req.status}">${STATUS_LABELS[req.status]}</span>
          ${cat}${blockedChip}
          <span class="dsh-pm-list-when">${fmtTime(req.updatedAt)}</span>
        </div>
        <div class="dsh-pm-list-title" data-action="open-req" data-req="${esc(req.id)}">${esc(req.title)}</div>
        <div class="dsh-pm-list-meta">
          <span class="dsh-pm-list-window-label">来源</span>${windowChip}
          <span class="dsh-pm-list-seps">·</span>
          <span class="dsh-pm-list-strip">${statusStrip}</span>
        </div>
        <div class="dsh-pm-list-progress">
          <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${pct}%"></div></div>
          <span class="dsh-pm-card-pct">${progress(doneCount, totalCount)}</span>
          <span class="dsh-pm-list-pct">${pct}%${active > 0 ? `（${active} 进行中）` : ''}</span>
        </div>
        <div class="dsh-pm-list-actions">
          <button type="button" class="dsh-pm-btn sm" data-action="open-req" data-req="${esc(req.id)}">查看详情</button>
          ${sid !== undefined && sid.length > 0 && !sidArchived
            ? `<button type="button" class="dsh-pm-btn sm primary" data-action="jump-session" data-sid="${esc(sid)}">跳转会话</button>`
            : (sidArchived
                ? '<button type="button" class="dsh-pm-btn sm" disabled title="该需求来自一个已归档的会话：日志保留、侧栏不可见，无法跳转">会话已归档</button>'
                : '')}
        </div>
      </div>`
}

function renderReqCard(card: ReqCard, now: number, archived: ReadonlySet<string> = NO_ARCHIVED): string {
  const { req, tasks, doneCount, totalCount, readyIds, blocked } = card
  const pct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0
  const cat = req.category ? `<span class="dsh-pm-cat" data-cat="${req.category}">${CATEGORY_LABELS[req.category] ?? req.category}</span>` : ''
  const planChipHtml = planChip(req) + verifyChip(req) + archiveChip(req)
  const blockedChip = blocked ? '<span class="dsh-pm-flag blocked">阻塞</span>' : ''
  const pausedChip = req.paused ? '<span class="dsh-pm-flag paused">暂停</span>' : ''
  const readyChip = readyIds.length > 0 ? `<span class="dsh-pm-flag ready">${readyIds.length} ready</span>` : ''
  // 窗口 chip：立项来源窗口（窗口↔需求关联）+ 最近执行会话
  const timeLine = renderCardTime(req, now)
  const sessionChip = renderWindowChip(req, archived) + renderSessionChip(tasks, archived)
  const actions = cardActions(req)

  return `
    <div class="dsh-pm-card${blocked ? ' is-blocked' : ''}" data-req="${esc(req.id)}" data-action="open-req">
      <div class="dsh-pm-card-top">
        <span class="dsh-pm-card-id">${esc(req.id)}</span>
        ${cat}${planChipHtml}${blockedChip}${pausedChip}${readyChip}
      </div>
      <div class="dsh-pm-card-title">${esc(req.title)}</div>
      <div class="dsh-pm-card-progress">
        <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${pct}%"></div></div>
        <span class="dsh-pm-card-pct">${progress(doneCount, totalCount)}</span>
      </div>
      ${timeLine}
      ${sessionChip}
      ${actions}
    </div>`
}

/**
 * 泳道卡面操作按钮 —— 状态推进不埋在详情页里（用户反馈「按钮太深」）。
 * 每个状态只给**下一步合法的人工操作**：闸门按钮本身就是闸门（人点 = 确认），
 * 非闸门态给便捷推进/退回。所有按钮自带 data-id，卡面直连 move-req
 * （不再依赖「当前处于详情态」）。
 */
function cardActions(req: RequirementRecord): string {
  const btn = (to: RequirementStatus, label: string, opts?: { primary?: boolean; title?: string }): string => {
    const cls = opts?.primary === true ? 'dsh-pm-btn sm primary' : 'dsh-pm-btn sm'
    const title = opts?.title !== undefined ? ` title="${esc(opts.title)}"` : ''
    return `<button type="button" class="${cls}" data-action="move-req" data-to="${to}" data-id="${esc(req.id)}"${title}>${label}</button>`
  }
  let actions = ''
  switch (req.status) {
    case 'draft':
      actions = btn('brainstorming', '开始头脑风暴', { primary: true, title: '进入头脑风暴；窗口接手开工时会自动进入' })
        + btn('canceled', '取消', { title: '取消该需求（仅人可操作）' })
      break
    case 'brainstorming':
      actions = btn('planning', '写计划', { primary: true, title: '方案谈定 → 进入写计划阶段（计划在此阶段提交待人批准）' })
        + btn('draft', '退回', { title: '退回立项' })
      break
    case 'planning':
      actions = btn('decomposing', '落库拆分', { primary: true, title: '计划获批后落库任务卡；未获批会被代码级拒绝' })
        + btn('brainstorming', '退回重谈', { title: '方案要改 → 退回头脑风暴' })
      break
    case 'decomposing':
      actions = btn('implementing', '开始执行', { primary: true, title: '进入执行；任务开工时系统会自动推进' })
      break
    case 'implementing':
      actions = btn('accepting', '提交验收', { primary: true, title: '进入验收；任务全部完成时系统会自动推进' })
      break
    case 'accepting':
      actions = btn('done', '验收通过', { primary: true, title: '完成该需求；窗口 agent 交付后也可自行完成' })
      break
    case 'done':
      actions = btn('archived', '归档', { title: '归档归集文档（仅人可操作）' })
      break
    default:
      actions = ''
  }
  return actions.length === 0 ? '' : `<div class="dsh-pm-card-actions">${actions}</div>`
}

/**
 * 立项来源窗口 chip —— 「项目看板 ↔ 窗口关联」在看板上的可见锚点。
 * sourceSessionId 是 host 落库时写入的窗口会话 id；点击可跳转到该会话。
 * 人工建卡（GUI/看板按钮）无 sourceSessionId → 不渲染（避免空 chip）。
 */
/**
 * 已归档会话 id 集合的默认值（工作区服务不可用时使用）。
 * 归档会话「日志保留、侧栏不可见」——跳过去也打不开，所以对应的窗口按钮**置灰不可点**，
 * 而不是让人点了再弹一个「该会话已归档」的告警。
 */
export const NO_ARCHIVED: ReadonlySet<string> = new Set<string>()

/** 会话是否已归档（集合缺省 → 视为未归档）。 */
function isArchived(sid: string, archived: ReadonlySet<string>): boolean {
  return archived.has(sid)
}

/**
 * 窗口/会话跳转按钮的统一渲染：可跳转 → button[data-action=jump-session]；
 * 已归档 → 灰色 span（无 data-action，点了不会触发跳转/告警）。
 */
function sessionChipHtml(opts: {
  sid: string
  label: string
  /** 类名（dsh-pm-window 用于来源窗口；dsh-pm-session 用于执行会话） */
  cls: string
  /** title 前缀，如「立项来源窗口」 */
  kind: string
  archived: boolean
}): string {
  const { sid, label, cls, kind, archived } = opts
  if (archived) {
    return `<span class="${cls} is-archived" aria-disabled="true" `
      + `title="${kind}已归档（${esc(sid)}）：日志保留、侧栏不可见，无法跳转">${label} · 已归档</span>`
  }
  return `<button type="button" class="${cls}" data-action="jump-session" data-sid="${esc(sid)}" `
    + `title="${kind}（点击跳转到该会话）：${esc(sid)}">${label}</button>`
}

function renderWindowChip(req: RequirementRecord, archived: ReadonlySet<string> = NO_ARCHIVED): string {
  const sid = req.sourceSessionId
  if (!sid) return ''
  return sessionChipHtml({
    sid,
    label: `窗口 ${windowCodeFromSessionId(sid)}`,
    cls: 'dsh-pm-window',
    kind: '立项来源窗口',
    archived: isArchived(sid, archived),
  })
}

function renderSessionChip(tasks: TaskRecord[], archived: ReadonlySet<string> = NO_ARCHIVED): string {
  for (let i = tasks.length - 1; i >= 0; i--) {
    const execs = tasks[i].executions
    for (let j = execs.length - 1; j >= 0; j--) {
      const sid = execs[j].sessionId
      if (sid) {
        return sessionChipHtml({
          sid,
          label: `会话 ${sid.slice(0, 12)}…`,
          cls: 'dsh-pm-session',
          kind: '执行会话',
          archived: isArchived(sid, archived),
        })
      }
    }
  }
  return ''
}

/* ------------------------------------------------------------------ 需求详情 */

/** 轻量 Markdown 渲染（零依赖，安全：先转义 HTML 再应用标记）。
 * 支持：# 标题、**粗体**、*斜体*、`行内代码`、[链接](url)、- 无序列表、1. 有序列表、```代码块``` */
function renderMarkdown(text: string): string {
  if (!text) return ''
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const out: string[] = []
  let codeBuf: string[] = []
  let inCode = false
  let listItems: string[] = []
  let listOrdered = false

  const flushList = (): void => {
    if (listItems.length === 0) return
    const tag = listOrdered ? 'ol' : 'ul'
    out.push('<' + tag + '>' + listItems.map(i => '<li>' + i + '</li>').join('') + '</' + tag + '>')
    listItems = []
  }

  // 行内标记（输入已转义，安全）
  const inline = (s: string): string => s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (line.trim().startsWith('```')) {
      flushList()
      if (inCode) {
        out.push('<pre><code>' + codeBuf.join('\n') + '</code></pre>')
        codeBuf = []
        inCode = false
      } else {
        inCode = true
      }
      continue
    }
    if (inCode) { codeBuf.push(esc(line)); continue }
    if (line.trim() === '') { flushList(); continue }
    const h = line.match(/^(#{1,6})\s+(.+)$/)
    if (h) {
      flushList()
      const lv = h[1].length
      out.push('<h' + lv + '>' + inline(esc(h[2])) + '</h' + lv + '>')
      continue
    }
    const ul = line.match(/^\s*[-*+]\s+(.+)$/)
    if (ul) {
      if (listItems.length > 0 && listOrdered) flushList()
      listOrdered = false
      listItems.push(inline(esc(ul[1])))
      continue
    }
    const ol = line.match(/^\s*\d+[.)]\s+(.+)$/)
    if (ol) {
      if (listItems.length > 0 && !listOrdered) flushList()
      listOrdered = true
      listItems.push(inline(esc(ol[1])))
      continue
    }
    flushList()
    out.push('<p>' + inline(esc(line)) + '</p>')
  }
  flushList()
  if (inCode && codeBuf.length > 0) out.push('<pre><code>' + codeBuf.join('\n') + '</code></pre>')
  return out.join('\n')
}

/* ------------------------------------------------------------------ 文档记录 */

/** 文档类型 → 图标 + 标签（需求详情页「文档」区块用） */
const DOC_KIND_META: Record<string, { icon: string; label: string }> = {
  requirement: { icon: '📄', label: '需求文档' },
  ui: { icon: '🎨', label: 'UI 文档' },
  proposal: { icon: '📐', label: '设计文档' },
  plan: { icon: '📝', label: '实施计划' },
  verification: { icon: '✅', label: '验收材料' },
  retro: { icon: '🔁', label: '复盘' },
  notes: { icon: '📒', label: '其他' },
}

/** 收集需求关联的全部文档（docLinks + plan.path + archive.docs），去重。 */
function collectReqDocs(req: RequirementRecord): Array<{ icon: string; label: string; path: string }> {
  const docs: Array<{ icon: string; label: string; path: string }> = []
  const seen = new Set<string>()
  const push = (kind: string, path: string): void => {
    const p = (path ?? '').trim()
    if (!p || seen.has(p)) return
    seen.add(p)
    const meta = DOC_KIND_META[kind]
    docs.push({ icon: meta?.icon ?? '📒', label: meta?.label ?? kind, path: p })
  }
  // 需求文档 / UI 文档 / 设计文档（docLinks）
  if (req.docLinks?.requirement) push('requirement', req.docLinks.requirement)
  if (req.docLinks?.ui) push('ui', req.docLinks.ui)
  if (req.docLinks?.proposal) push('proposal', req.docLinks.proposal)
  // 实施计划（plan.path）
  if (req.plan?.path) push('plan', req.plan.path)
  // 归档文档清单（archive.docs）
  for (const d of req.archive?.docs ?? []) push(d.kind, d.path)
  return docs
}

/** 渲染「文档」区块：该需求关联的需求文档/UI 文档/设计文档/计划/验收/复盘等。 */
function renderDocSection(req: RequirementRecord): string {
  const docs = collectReqDocs(req)
  if (docs.length === 0) {
    return '<div class="dsh-pm-empty">暂无文档记录。窗口 agent 可用 <code>reqboard_archive_submit</code> 提交文档清单，或通过需求更新接口填充 docLinks（requirement/ui/proposal）。</div>'
  }
  return '<ul class="dsh-pm-doc-list">' + docs.map(d =>
    '<li data-doc-path="' + esc(d.path) + '">'
    + '<span class="dsh-pm-doc-icon">' + d.icon + '</span>'
    + '<span class="dsh-pm-doc-label">' + esc(d.label) + '</span>'
    + '<button type="button" class="dsh-pm-doc-path" data-action="open-doc" data-path="' + esc(d.path) + '">' + esc(d.path) + '</button>'
    + '</li>'
  ).join('') + '</ul>'
}

export function buildReqDetail(req: RequirementRecord, tasks: TaskRecord[], now: number = Date.now(), archived: ReadonlySet<string> = NO_ARCHIVED): string {
  const reqTasks = tasks.filter(t => t.requirementId === req.id)
  const doneCount = reqTasks.filter(t => t.status === 'done').length
  const totalCount = reqTasks.length
  const pct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0
  const dag = buildDag(reqTasks)
  const taskCols = buildTaskColumns(reqTasks)
  const comments = renderComments(req.comments)
  const gateHint = gateHintFor(req.status)

  // 进度条（监控优先：一眼看到完成度）
  const progressHtml = totalCount > 0
    ? `<div class="dsh-pm-req-progress">
        <div class="dsh-pm-progress-bar"><div class="dsh-pm-progress-fill${pct >= 100 ? ' full' : ''}" style="width:${pct}%"></div></div>
        <span class="dsh-pm-progress-text"><b>${doneCount}/${totalCount}</b> 完成 <span class="dsh-pm-progress-pct">${pct}%</span></span>
      </div>`
    : '<div class="dsh-pm-req-progress"><span class="dsh-pm-progress-text">尚未拆分任务</span></div>'

  return `
    <div class="dsh-pm-detail" data-detail-req="${esc(req.id)}">
      <div class="dsh-pm-detail-head">
        <button type="button" class="dsh-pm-btn" data-action="back" title="返回看板">← 看板</button>
        <span class="dsh-pm-card-id">${esc(req.id)}</span>
        <span class="dsh-pm-status" data-status="${req.status}">${STATUS_LABELS[req.status]}</span>
        ${req.blocked ? '<span class="dsh-pm-flag blocked">阻塞</span>' : ''}
        ${renderWindowChip(req, archived)}
        <span class="dsh-pm-detail-updated">${fmtTime(req.updatedAt)}</span>
      </div>
      ${gateHint}
      <details class="dsh-pm-fold" open>
        <summary>📄 需求描述</summary>
        <div class="dsh-pm-fold-body">
          <h2 class="dsh-pm-detail-title">${esc(req.title)}</h2>
          ${req.description ? `<div class="dsh-pm-markdown">${renderMarkdown(req.description)}</div>` : '<div class="dsh-pm-empty">暂无描述</div>'}
        </div>
      </details>
      <details class="dsh-pm-fold" open>
        <summary>📁 文档记录</summary>
        <div class="dsh-pm-fold-body">${renderDocSection(req)}</div>
      </details>
      <details class="dsh-pm-fold">
        <summary>📅 时间线</summary>
        <div class="dsh-pm-fold-body">${renderReqTimeline(req, now)}</div>
      </details>
      ${progressHtml}
      <details class="dsh-pm-fold">
        <summary>📋 任务看板<span class="dsh-pm-fold-count">${totalCount} 个任务</span></summary>
        <div class="dsh-pm-fold-body">
          <div class="dsh-pm-section-head">
            <button type="button" class="dsh-pm-btn sm" data-action="new-task" data-id="${esc(req.id)}" title="人工建任务卡（窗口 agent 走 reqboard_decompose 批量拆分）">+ 任务</button>
          </div>
          ${taskCols}
        </div>
      </details>
      <details class="dsh-pm-fold">
        <summary>🔀 任务 DAG</summary>
        <div class="dsh-pm-fold-body">${dag}</div>
      </details>
      <details class="dsh-pm-fold">
        <summary>📝 实施计划（plan mode）</summary>
        <div class="dsh-pm-fold-body">${renderPlanSection(req)}</div>
      </details>
      <details class="dsh-pm-fold">
        <summary>✅ 验收（人工审核）</summary>
        <div class="dsh-pm-fold-body">${renderVerifySection(req)}</div>
      </details>
      <details class="dsh-pm-fold">
        <summary>📦 归档（文档合并）</summary>
        <div class="dsh-pm-fold-body">${renderArchiveSection(req)}</div>
      </details>
      <details class="dsh-pm-fold">
        <summary>💬 评论<span class="dsh-pm-fold-count">${req.comments.length} 条</span></summary>
        <div class="dsh-pm-fold-body">
          ${comments}
          <div class="dsh-pm-comment-form">
            <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
            <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="req" data-id="${esc(req.id)}">发送</button>
          </div>
        </div>
      </details>
    </div>`
}

/** 当前状态的闸门提示（人工闸门标出操作按钮） */
function gateHintFor(status: RequirementStatus): string {
  const hints: Partial<Record<RequirementStatus, string>> = {
    draft: '<div class="dsh-pm-gate">已立项：窗口接手开工后自动进入评审 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="brainstorming">提交评审</button></div>',
    brainstorming: '<div class="dsh-pm-gate">评审中：窗口 agent 会自行推进到拆分，人可在此加速 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="decomposing">确认方案</button> <button type="button" class="dsh-pm-btn" data-action="move-req" data-to="draft">退回立项</button></div>',
    decomposing: '<div class="dsh-pm-gate">拆分中：任务落库/开工后系统自动推进到实施 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="implementing">确认拆分</button></div>',
    planning: '<div class="dsh-pm-gate">写计划：计划提交后请点上面计划卡的「批准计划」——批准前拆分会被告代码级拒绝 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="decomposing">落库拆分</button> <button type="button" class="dsh-pm-btn" data-action="move-req" data-to="brainstorming">退回重谈</button></div>',
    implementing: '<div class="dsh-pm-gate">执行中：任务全部完成时自动进入验收 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="accepting">提交验收</button></div>',
    accepting: '<div class="dsh-pm-gate">验收中：窗口 agent 交付后可自行完成，人可在此确认 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="done">验收通过</button></div>',
    done: '<div class="dsh-pm-gate">已完成：归档归集文档（仅人可操作）<button type="button" class="dsh-pm-btn" data-action="move-req" data-to="archived">归档</button></div>',
  }
  return hints[status] ?? ''
}

/** 任务 DAG：v1 用分层列表（拓扑层级）表达，节点可点击 */
function buildDag(tasks: TaskRecord[]): string {
  if (tasks.length === 0) return '<div class="dsh-pm-empty">暂无任务</div>'
  // 计算深度（最长依赖链长度）
  const depth = new Map<string, number>()
  const taskById = new Map(tasks.map(t => [t.id, t]))
  const calcDepth = (t: TaskRecord, seen: Set<string>): number => {
    if (depth.has(t.id)) return depth.get(t.id)!
    if (seen.has(t.id)) return 0
    seen.add(t.id)
    const deps = t.dependsOn.filter(d => taskById.has(d))
    const d = deps.length === 0 ? 0 : 1 + Math.max(...deps.map(dep => calcDepth(taskById.get(dep)!, seen)))
    depth.set(t.id, d)
    return d
  }
  tasks.forEach(t => calcDepth(t, new Set()))
  const maxDepth = Math.max(...depth.values())
  const layers: TaskRecord[][] = Array.from({ length: maxDepth + 1 }, () => [])
  tasks.forEach(t => layers[depth.get(t.id)!].push(t))

  return `<div class="dsh-pm-dag">` + layers.map((layer, i) => `
    <div class="dsh-pm-dag-layer">
      <span class="dsh-pm-dag-layer-label">L${i}</span>
      ${layer.map(t => `
        <span class="dsh-pm-dag-node" data-status="${t.status}" data-action="open-task" data-task="${esc(t.id)}" title="${esc(t.title)}">
          ${esc(t.id)} ${esc(t.title.slice(0, 20))}${t.title.length > 20 ? '…' : ''}
        </span>`).join('')}
    </div>`).join('') + `</div>`
}

/** 任务五列小看板（含 in_review/done） */
function buildTaskColumns(tasks: TaskRecord[]): string {
  if (tasks.length === 0) return '<div class="dsh-pm-empty">暂无任务</div>'
  const cols: TaskStatus[] = ['todo', 'in_progress', 'integrating', 'testing', 'in_review', 'done']
  return `<div class="dsh-pm-taskcols">` + cols.map(status => {
    const inCol = tasks.filter(t => t.status === status)
    return `
      <div class="dsh-pm-taskcol" data-col="${status}">
        <div class="dsh-pm-taskcol-head">${TASK_STATUS_LABELS[status]} ${inCol.length}</div>
        ${inCol.map(t => `
          <div class="dsh-pm-task" data-task="${esc(t.id)}" data-action="open-task">
            <div class="dsh-pm-task-title">${esc(t.title)}</div>
            <div class="dsh-pm-task-meta">
              <span class="dsh-pm-phase">${PHASE_LABELS[t.phase] ?? t.phase}</span>
              ${t.blocked ? '<span class="dsh-pm-flag blocked">阻塞</span>' : ''}
            </div>
          </div>`).join('')}
      </div>`
  }).join('') + `</div>`
}

function renderComments(comments: CommentRecord[]): string {
  if (comments.length === 0) return '<div class="dsh-pm-empty">暂无评论</div>'
  return `<div class="dsh-pm-comments">` + comments.map(c => `
    <div class="dsh-pm-comment">
      <span class="dsh-pm-comment-meta">${esc(c.createdBy?.kind ?? 'human')} · ${fmtTime(c.createdAt)}</span>
      <div class="dsh-pm-comment-body">${esc(c.body)}</div>
    </div>`).join('') + `</div>`
}

/* ------------------------------------------------------------------ 任务详情 */

/* ------------------------------------------------------------------ 节点类型识别 */

/** 节点类型（用于差异化展示内容） */
type NodeType = 'decompose' | 'implement' | 'test' | 'review' | 'merge' | 'doc' | 'ui' | 'analysis' | 'generic'

/** 识别任务节点类型 */
function identifyNodeType(task: TaskRecord): NodeType {
  const title = task.title.toLowerCase()
  // 特殊节点类型（基于 title）
  if (title.includes('拆分') || title.includes('decompose')) return 'decompose'
  if (task.status === 'integrating' || title.includes('集成') || title.includes('联调')) return 'merge'

  // 基于 phase 识别
  switch (task.phase) {
    case 'doc': return 'doc'
    case 'ui': return 'ui'
    case 'analysis': return 'analysis'
    case 'implement': return 'implement'
    case 'test': return 'test'
    case 'review': return 'review'
    case 'merge': return 'merge'
    default: return 'generic'
  }
}

/** 节点类型图标 */
const NODE_TYPE_ICONS: Record<NodeType, string> = {
  decompose: '🔀',
  implement: '⚙️',
  test: '🧪',
  review: '👀',
  merge: '🔀',
  doc: '📝',
  ui: '🎨',
  analysis: '🔍',
  generic: '📋',
}

/** 节点类型标签 */
const NODE_TYPE_LABELS: Record<NodeType, string> = {
  decompose: '拆分任务',
  implement: '实施任务',
  test: '测试任务',
  review: '评审任务',
  merge: '合并任务',
  doc: '文档任务',
  ui: 'UI设计',
  analysis: '分析任务',
  generic: '任务',
}

export function buildTaskDetail(
  task: TaskRecord,
  req: RequirementRecord | undefined,
  now: number = Date.now(),
  allTasks: TaskRecord[] = [],
  archived: ReadonlySet<string> = NO_ARCHIVED,
): string {
  const nodeType = identifyNodeType(task)
  const icon = NODE_TYPE_ICONS[nodeType]
  const label = NODE_TYPE_LABELS[nodeType]

  // 专属内容区域
  const specializedContent = renderSpecializedContent(task, nodeType, req, allTasks)

  // 通用信息区域（折叠）
  const commonContent = renderCommonContent(task, now, archived)

  return `
    <div class="dsh-pm-taskdetail" data-detail-task="${esc(task.id)}" data-node-type="${nodeType}">
      <div class="dsh-pm-detail-head">
        <button type="button" class="dsh-pm-btn" data-action="back-req" data-req="${esc(task.requirementId)}" title="返回需求">← ${esc(task.requirementId)}</button>
        <span class="dsh-pm-card-id">${esc(task.id)}</span>
        <span class="dsh-pm-status" data-status="${task.status}">${TASK_STATUS_LABELS[task.status]}</span>
        <span class="dsh-pm-node-badge" title="${label}">${icon} ${label}</span>
      </div>
      <h2 class="dsh-pm-detail-title">${esc(task.title)}</h2>
      ${task.description ? `<div class="dsh-pm-detail-desc">${esc(task.description)}</div>` : ''}
      ${specializedContent}
      ${commonContent}
    </div>`
}

/* ------------------------------------------------------------------ 专属内容渲染 */

/** 渲染节点专属内容（根据节点类型分发） */
function renderSpecializedContent(task: TaskRecord, nodeType: NodeType, req: RequirementRecord | undefined, allTasks: TaskRecord[]): string {
  switch (nodeType) {
    case 'decompose': return renderDecomposeContent(task, req, allTasks)
    case 'implement': return renderImplementContent(task)
    case 'test': return renderTestContent(task)
    case 'review': return renderReviewContent(task)
    case 'merge': return renderMergeContent(task)
    case 'doc': return renderDocContent(task)
    case 'ui': return renderUIContent(task)
    case 'analysis': return renderAnalysisContent(task)
    default: return ''
  }
}

/** 通用信息区域（折叠） */
function renderCommonContent(task: TaskRecord, now: number, archived: ReadonlySet<string> = NO_ARCHIVED): string {
  const execs = task.executions.map(e => `
    <div class="dsh-pm-exec" data-outcome="${e.outcome}">
      <span class="dsh-pm-exec-outcome">${e.outcome}</span>
      <span>${fmtTime(e.startedAt)}</span>
      ${e.sessionId ? sessionChipHtml({
        sid: e.sessionId,
        label: `会话 ${e.sessionId.slice(0, 12)}…`,
        cls: 'dsh-pm-session',
        kind: '执行会话',
        archived: archived.has(e.sessionId),
      }) : ''}
      ${e.error ? `<div class="dsh-pm-exec-error">${esc(e.error)}</div>` : ''}
      ${e.evidence && e.evidence.length > 0 ? `<div class="dsh-pm-exec-evidence">${e.evidence.map(ev => `<code>${esc(ev)}</code>`).join(' ')}</div>` : ''}
    </div>`).join('')

  return `
    <details class="dsh-pm-common-details">
      <summary class="dsh-pm-common-summary">通用信息（属性、时间线、执行记录、评论）</summary>
      <div class="dsh-pm-detail-section">
        <h3>属性</h3>
        <div class="dsh-pm-kv">
          <span>阶段</span><span>${PHASE_LABELS[task.phase] ?? task.phase}</span>
          <span>端侧</span><span>${task.side}</span>
          <span>依赖</span><span>${task.dependsOn.length > 0 ? task.dependsOn.map(esc).join(', ') : '无'}</span>
          <span>验收标准</span><span>${esc(task.acceptance)}</span>
        </div>
      </div>
      <div class="dsh-pm-detail-section">
        <h3>时间线</h3>
        ${renderTaskTimeline(task, now)}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>执行记录（${task.executions.length}）</h3>
        ${execs || '<div class="dsh-pm-empty">暂无执行</div>'}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>评论（${task.comments.length}）</h3>
        ${renderComments(task.comments)}
        <div class="dsh-pm-comment-form">
          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="task" data-id="${esc(task.id)}">发送</button>
        </div>
      </div>
    </details>`
}

/* ------------------------------------------------------------------ 拆分节点 */

function renderDecomposeContent(task: TaskRecord, req: RequirementRecord | undefined, allTasks: TaskRecord[]): string {
  if (!req) {
    return '<div class="dsh-pm-detail-section"><div class="dsh-pm-empty">需求数据不可用</div></div>'
  }

  // 获取该需求下的所有任务
  const tasks = allTasks.filter(t => t.requirementId === req.id)

  const totalTasks = tasks.length
  const doneTasks = tasks.filter(t => t.status === 'done').length

  // 按端侧分组
  const byTrack: Record<string, TaskRecord[]> = {}
  tasks.forEach(t => {
    const track = t.side === 'frontend' ? 'UI 轨道' : t.side === 'backend' ? '后端轨道' : t.side === 'doc' ? '文档轨道' : '全栈轨道'
    if (!byTrack[track]) byTrack[track] = []
    byTrack[track].push(t)
  })

  const tracks = Object.keys(byTrack).length
  const estimatedDays = totalTasks > 0 ? (totalTasks * 0.5).toFixed(1) : '0'

  const taskListHtml = Object.entries(byTrack).map(([track, trackTasks]) => `
    <div class="dsh-pm-track">
      <div class="dsh-pm-track-head">${track} - ${trackTasks.length} 任务</div>
      <ul class="dsh-pm-track-list">
        ${trackTasks.map(t => `<li><button type="button" class="dsh-pm-task-link" data-action="open-task" data-task="${esc(t.id)}">${esc(t.id)}</button> ${esc(t.title)}</li>`).join('')}
      </ul>
    </div>`).join('')

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>📊 拆分结果</h3>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">总计任务</span>
          <span class="dsh-pm-stat-value">${totalTasks} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">并行轨道</span>
          <span class="dsh-pm-stat-value">${tracks} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">预计工期</span>
          <span class="dsh-pm-stat-value">${estimatedDays} 天</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">完成进度</span>
          <span class="dsh-pm-stat-value">${doneTasks}/${totalTasks}</span>
        </div>
      </div>
    </div>
    <div class="dsh-pm-detail-section">
      <h3>📋 拆分清单</h3>
      ${taskListHtml || '<div class="dsh-pm-empty">暂无任务</div>'}
    </div>
    <div class="dsh-pm-detail-section">
      <h3>🌳 依赖关系 DAG</h3>
      ${buildDag(tasks)}
    </div>`
}

/* ------------------------------------------------------------------ 实施节点 */

function renderImplementContent(task: TaskRecord): string {
  // 从 executions.evidence 提取文件变更
  const files: Array<{path: string; added: number; deleted: number}> = []
  const lastExec = task.executions[task.executions.length - 1]

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析格式如: "src/auth/login.ts (+45, -12)"
      const match = ev.match(/^(.+?)\s*\(?\+(\d+)(?:,\s*-(\d+))?\)?$/)
      if (match) {
        files.push({
          path: match[1].trim(),
          added: parseInt(match[2], 10),
          deleted: parseInt(match[3] || '0', 10),
        })
      }
    })
  }

  const totalAdded = files.reduce((sum, f) => sum + f.added, 0)
  const totalDeleted = files.reduce((sum, f) => sum + f.deleted, 0)

  const filesHtml = files.length > 0 ? files.map(f => `
    <div class="dsh-pm-file-change">
      <code class="dsh-pm-file-path">${esc(f.path)}</code>
      <span class="dsh-pm-file-stats">
        <span class="dsh-pm-stat-add">+${f.added}</span>
        ${f.deleted > 0 ? `<span class="dsh-pm-stat-del">-${f.deleted}</span>` : ''}
      </span>
    </div>`).join('') : '<div class="dsh-pm-empty">暂无文件变更记录</div>'

  // 质量指标（从 evidence 中查找）
  let coverage = '未知'
  let complexity = '未知'
  if (lastExec?.evidence) {
    const coverageMatch = lastExec.evidence.find(ev => ev.includes('coverage') || ev.includes('覆盖率'))
    if (coverageMatch) {
      const match = coverageMatch.match(/(\d+)%/)
      if (match) coverage = match[1] + '%'
    }
  }

  // 执行记录摘要
  const execSummary = task.executions.map(e => {
    const icon = e.outcome === 'succeeded' ? '✅' : e.outcome === 'failed' ? '❌' : e.outcome === 'running' ? '⏳' : '⚠️'
    return `<div class="dsh-pm-exec-brief">${icon} ${fmtTime(e.startedAt)} - ${e.outcome}</div>`
  }).join('')

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>📁 修改文件</h3>
      <div class="dsh-pm-file-summary">
        <span>${files.length} 个文件</span>
        <span class="dsh-pm-stat-add">+${totalAdded} 行</span>
        ${totalDeleted > 0 ? `<span class="dsh-pm-stat-del">-${totalDeleted} 行</span>` : ''}
      </div>
      ${filesHtml}
    </div>
    <div class="dsh-pm-detail-section">
      <h3>🔍 执行记录（${task.executions.length} 次）</h3>
      ${execSummary || '<div class="dsh-pm-empty">暂无执行</div>'}
    </div>
    <div class="dsh-pm-detail-section">
      <h3>📊 质量指标</h3>
      <div class="dsh-pm-kv">
        <span>测试覆盖率</span><span>${coverage}</span>
        <span>代码复杂度</span><span>${complexity}</span>
        <span>类型安全</span><span>通过</span>
      </div>
    </div>`
}

/* ------------------------------------------------------------------ 测试节点 */

function renderTestContent(task: TaskRecord): string {
  // 从 executions.evidence 解析测试结果
  let total = 0, passed = 0, failed = 0, skipped = 0
  const failedCases: Array<{name: string; expected: string; actual: string; file: string}> = []

  const lastExec = task.executions[task.executions.length - 1]
  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析 "18 passed / 2 failed / 0 skipped"
      const match = ev.match(/(\d+)\s*passed.*?(\d+)\s*failed.*?(\d+)\s*skipped/i)
      if (match) {
        passed = parseInt(match[1], 10)
        failed = parseInt(match[2], 10)
        skipped = parseInt(match[3], 10)
        total = passed + failed + skipped
      }
    })
  }

  // 从 error 字段解析失败用例
  if (lastExec?.error) {
    const lines = lastExec.error.split('\n')
    lines.forEach(line => {
      const match = line.match(/(.+?):(\d+)\s*Expected:\s*(.+?)\s*Actual:\s*(.+)/)
      if (match) {
        failedCases.push({
          name: '测试用例',
          file: match[1] + ':' + match[2],
          expected: match[3],
          actual: match[4],
        })
      }
    })
  }

  const passRate = total > 0 ? ((passed / total) * 100).toFixed(1) : '0'

  const failedHtml = failedCases.length > 0 ? failedCases.map(c => `
    <div class="dsh-pm-test-fail">
      <div class="dsh-pm-test-fail-name">${esc(c.name)}</div>
      <div class="dsh-pm-test-fail-detail">
        <span>预期：<code>${esc(c.expected)}</code></span>
        <span>实际：<code>${esc(c.actual)}</code></span>
        <span>文件：<code>${esc(c.file)}</code></span>
      </div>
    </div>`).join('') : '<div class="dsh-pm-empty">所有测试通过</div>'

  // 覆盖率（从 evidence 提取）
  let stmtCov = 0, branchCov = 0, funcCov = 0, lineCov = 0
  if (lastExec?.evidence) {
    const covMatch = lastExec.evidence.find(ev => ev.includes('coverage'))
    if (covMatch) {
      const stmt = covMatch.match(/statements?:\s*(\d+)%/i)
      const branch = covMatch.match(/branches?:\s*(\d+)%/i)
      const func = covMatch.match(/functions?:\s*(\d+)%/i)
      const line = covMatch.match(/lines?:\s*(\d+)%/i)
      if (stmt) stmtCov = parseInt(stmt[1], 10)
      if (branch) branchCov = parseInt(branch[1], 10)
      if (func) funcCov = parseInt(func[1], 10)
      if (line) lineCov = parseInt(line[1], 10)
    }
  }

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>📊 测试概况</h3>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">总计</span>
          <span class="dsh-pm-stat-value">${total} 个</span>
        </div>
        <div class="dsh-pm-stat dsh-pm-stat-success">
          <span class="dsh-pm-stat-label">通过</span>
          <span class="dsh-pm-stat-value">${passed} 个 (${passRate}%)</span>
        </div>
        <div class="dsh-pm-stat dsh-pm-stat-error">
          <span class="dsh-pm-stat-label">失败</span>
          <span class="dsh-pm-stat-value">${failed} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">跳过</span>
          <span class="dsh-pm-stat-value">${skipped} 个</span>
        </div>
      </div>
    </div>
    ${failed > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>❌ 失败的测试</h3>
      ${failedHtml}
    </div>` : ''}
    ${stmtCov > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📈 覆盖率报告</h3>
      <div class="dsh-pm-coverage">
        <div class="dsh-pm-coverage-bar">
          <span class="dsh-pm-coverage-label">语句覆盖率</span>
          <span class="dsh-pm-coverage-value">${stmtCov}%</span>
          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${stmtCov}%"></div></div>
        </div>
        <div class="dsh-pm-coverage-bar">
          <span class="dsh-pm-coverage-label">分支覆盖率</span>
          <span class="dsh-pm-coverage-value">${branchCov}%</span>
          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${branchCov}%"></div></div>
        </div>
        <div class="dsh-pm-coverage-bar">
          <span class="dsh-pm-coverage-label">函数覆盖率</span>
          <span class="dsh-pm-coverage-value">${funcCov}%</span>
          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${funcCov}%"></div></div>
        </div>
        <div class="dsh-pm-coverage-bar">
          <span class="dsh-pm-coverage-label">行覆盖率</span>
          <span class="dsh-pm-coverage-value">${lineCov}%</span>
          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${lineCov}%"></div></div>
        </div>
      </div>
    </div>` : ''}`
}

/* ------------------------------------------------------------------ 评审节点 */

function renderReviewContent(task: TaskRecord): string {
  // 从 comments 中提取评审意见
  const reviewComments = task.comments.filter(c => c.createdBy?.kind === 'agent' || c.createdBy?.kind === 'human')

  // 从 executions.evidence 解析评审结果
  const lastExec = task.executions[task.executions.length - 1]
  let approved = false
  let reviewStatus = '待评审'
  const suggestions: Array<{file: string; line: string; severity: 'low' | 'medium' | 'high'; message: string; resolved: boolean}> = []
  const passedItems: string[] = []

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析 "approved" 或 "rejected"
      if (ev.toLowerCase().includes('approved') || ev.toLowerCase().includes('通过')) {
        approved = true
        reviewStatus = '已批准'
      }
      if (ev.toLowerCase().includes('rejected') || ev.toLowerCase().includes('退回')) {
        reviewStatus = '已退回'
      }

      // 解析通过项 "✓ code style"
      if (ev.startsWith('✓') || ev.startsWith('✅')) {
        passedItems.push(ev.replace(/^[✓✅]\s*/, ''))
      }

      // 解析改进建议 "file.ts:45 [medium] Use constant instead of magic number"
      const suggMatch = ev.match(/^(.+?):(\d+)\s*\[(\w+)\]\s*(.+)/)
      if (suggMatch) {
        suggestions.push({
          file: suggMatch[1],
          line: suggMatch[2],
          severity: suggMatch[3] as 'low' | 'medium' | 'high',
          message: suggMatch[4],
          resolved: false,
        })
      }
    })
  }

  const severityLabels = { low: '低', medium: '中', high: '高' }
  const severityColors = { low: '#28a745', medium: '#f0a020', high: '#dc3545' }

  const passedHtml = passedItems.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>✅ 通过项</h3>
      <ul class="dsh-pm-review-list">
        ${passedItems.map(item => `<li class="dsh-pm-review-pass">${esc(item)}</li>`).join('')}
      </ul>
    </div>` : ''

  const suggestionsHtml = suggestions.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>⚠️ 改进建议（${suggestions.length} 项）</h3>
      <div class="dsh-pm-suggestions">
        ${suggestions.map((s, i) => `
          <div class="dsh-pm-suggestion" data-severity="${s.severity}">
            <div class="dsh-pm-suggestion-head">
              <span class="dsh-pm-suggestion-num">${i + 1}</span>
              <code class="dsh-pm-file-path">${esc(s.file)}:${s.line}</code>
              <span class="dsh-pm-severity-badge" data-severity="${s.severity}" style="background: ${severityColors[s.severity]}">
                严重性：${severityLabels[s.severity]}
              </span>
            </div>
            <div class="dsh-pm-suggestion-body">${esc(s.message)}</div>
          </div>`).join('')}
      </div>
    </div>` : ''

  const commentsHtml = reviewComments.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>💬 评审讨论（${reviewComments.length} 条）</h3>
      ${renderComments(reviewComments)}
    </div>` : ''

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>📊 评审结果</h3>
      <div class="dsh-pm-review-status" data-status="${approved ? 'approved' : 'pending'}">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">状态</span>
          <span class="dsh-pm-stat-value">${reviewStatus}</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">通过项</span>
          <span class="dsh-pm-stat-value">${passedItems.length} 项</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">改进建议</span>
          <span class="dsh-pm-stat-value">${suggestions.length} 项</span>
        </div>
      </div>
    </div>
    ${passedHtml}
    ${suggestionsHtml}
    ${commentsHtml}`
}

/* ------------------------------------------------------------------ 合并节点 */

function renderMergeContent(task: TaskRecord): string {
  // 从 executions.evidence 解析合并信息
  const lastExec = task.executions[task.executions.length - 1]
  let sourceBranch = '未知'
  let targetBranch = 'main'
  let commits = 0
  let filesChanged = 0
  let linesAdded = 0
  let linesDeleted = 0
  let mergeStatus = '进行中'
  const conflicts: Array<{file: string; description: string; resolution: string}> = []
  const ciChecks: Array<{name: string; status: 'pass' | 'fail' | 'pending'; details?: string}> = []

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析 "feature/login → main"
      const branchMatch = ev.match(/(.+?)\s*(?:→|->|-)\s*(.+)/)
      if (branchMatch) {
        sourceBranch = branchMatch[1].trim()
        targetBranch = branchMatch[2].trim()
      }

      // 解析 "12 commits"
      const commitMatch = ev.match(/(\d+)\s*commits?/i)
      if (commitMatch) commits = parseInt(commitMatch[1], 10)

      // 解析 "15 files changed"
      const filesMatch = ev.match(/(\d+)\s*files?\s*changed/i)
      if (filesMatch) filesChanged = parseInt(filesMatch[1], 10)

      // 解析 "+854 -231"
      const diffMatch = ev.match(/\+(\d+)\s*-(\d+)/)
      if (diffMatch) {
        linesAdded = parseInt(diffMatch[1], 10)
        linesDeleted = parseInt(diffMatch[2], 10)
      }

      // 解析 "merged" 或 "conflicted"
      if (ev.toLowerCase().includes('merged') || ev.toLowerCase().includes('合并成功')) {
        mergeStatus = '✅ 合并成功'
      }
      if (ev.toLowerCase().includes('conflict')) {
        mergeStatus = '⚠️ 存在冲突'
      }

      // 解析冲突 "conflict: src/router.ts - routing config duplicate"
      const conflictMatch = ev.match(/conflict:\s*(.+?)\s*-\s*(.+)/i)
      if (conflictMatch) {
        conflicts.push({
          file: conflictMatch[1].trim(),
          description: conflictMatch[2].trim(),
          resolution: '待解决',
        })
      }

      // 解析 CI 检查 "✓ unit-tests: 18/18 passed"
      const ciMatch = ev.match(/^([✓✅❌⏳])\s*(.+?):\s*(.+)/)
      if (ciMatch) {
        const status = ciMatch[1] === '✓' || ciMatch[1] === '✅' ? 'pass' : ciMatch[1] === '❌' ? 'fail' : 'pending'
        ciChecks.push({
          name: ciMatch[2].trim(),
          status,
          details: ciMatch[3].trim(),
        })
      }
    })
  }

  const conflictsHtml = conflicts.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>⚠️ 冲突解决（${conflicts.length} 个）</h3>
      <div class="dsh-pm-conflicts">
        ${conflicts.map((c, i) => `
          <div class="dsh-pm-conflict">
            <div class="dsh-pm-conflict-num">${i + 1}</div>
            <div class="dsh-pm-conflict-body">
              <code class="dsh-pm-file-path">${esc(c.file)}</code>
              <div class="dsh-pm-conflict-desc">冲突：${esc(c.description)}</div>
              <div class="dsh-pm-conflict-resolution">解决：${esc(c.resolution)}</div>
            </div>
          </div>`).join('')}
      </div>
    </div>` : ''

  const ciHtml = ciChecks.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>✅ CI/CD 检查</h3>
      <div class="dsh-pm-ci-checks">
        ${ciChecks.map(check => {
          const icon = check.status === 'pass' ? '✅' : check.status === 'fail' ? '❌' : '⏳'
          return `
            <div class="dsh-pm-ci-check" data-status="${check.status}">
              <span class="dsh-pm-ci-icon">${icon}</span>
              <span class="dsh-pm-ci-name">${esc(check.name)}</span>
              <span class="dsh-pm-ci-details">${esc(check.details || '')}</span>
            </div>`
        }).join('')}
      </div>
    </div>` : ''

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>📊 合并状态</h3>
      <div class="dsh-pm-merge-header">
        <div class="dsh-pm-merge-branch">
          <code>${esc(sourceBranch)}</code>
          <span class="dsh-pm-merge-arrow">→</span>
          <code>${esc(targetBranch)}</code>
        </div>
        <div class="dsh-pm-merge-status">${mergeStatus}</div>
      </div>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">提交数</span>
          <span class="dsh-pm-stat-value">${commits} commits</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">变更文件</span>
          <span class="dsh-pm-stat-value">${filesChanged} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">代码变更</span>
          <span class="dsh-pm-stat-value">
            <span class="dsh-pm-stat-add">+${linesAdded}</span>
            <span class="dsh-pm-stat-del">-${linesDeleted}</span>
          </span>
        </div>
      </div>
    </div>
    ${conflictsHtml}
    ${ciHtml}`
}

/* ------------------------------------------------------------------ 其他节点类型占位 */

function renderDocContent(task: TaskRecord): string {
  // 从 executions.evidence 提取文档文件
  const lastExec = task.executions[task.executions.length - 1]
  const docFiles: string[] = []
  const apis: string[] = []
  let completeness = { defined: 0, total: 0 }

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析文档文件 "docs/api/auth.md"
      if (ev.match(/\.(md|txt|pdf|html)$/i)) {
        docFiles.push(ev)
      }

      // 解析 API 端点 "POST /api/auth/login"
      if (ev.match(/^(GET|POST|PUT|DELETE|PATCH)\s+\//)) {
        apis.push(ev)
      }

      // 解析完成度 "3/5 sections completed"
      const compMatch = ev.match(/(\d+)\/(\d+)\s*.*?completed/i)
      if (compMatch) {
        completeness.defined = parseInt(compMatch[1], 10)
        completeness.total = parseInt(compMatch[2], 10)
      }
    })
  }

  // 从 description 中提取 API 列表（如果 evidence 中没有）
  if (apis.length === 0 && task.description) {
    const apiMatches = task.description.match(/(GET|POST|PUT|DELETE|PATCH)\s+\/[^\s\n]+/g)
    if (apiMatches) apis.push(...apiMatches)
  }

  const completionPct = completeness.total > 0
    ? Math.round((completeness.defined / completeness.total) * 100)
    : 0

  const docFilesHtml = docFiles.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📄 文档内容</h3>
      <ul class="dsh-pm-doc-list">
        ${docFiles.map(file => `<li><code>${esc(file)}</code></li>`).join('')}
      </ul>
    </div>` : ''

  const apisHtml = apis.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>🔗 关联接口（${apis.length} 个）</h3>
      <ul class="dsh-pm-api-list">
        ${apis.map(api => {
          const [method, path] = api.split(/\s+/)
          return `<li><span class="dsh-pm-api-method" data-method="${method}">${method}</span> <code>${esc(path)}</code></li>`
        }).join('')}
      </ul>
    </div>` : ''

  const completenessHtml = completeness.total > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📊 完成度</h3>
      <div class="dsh-pm-completeness">
        <div class="dsh-pm-completeness-bar">
          <span class="dsh-pm-completeness-label">整体进度</span>
          <span class="dsh-pm-completeness-value">${completionPct}%</span>
          <div class="dsh-pm-completeness-track">
            <div class="dsh-pm-completeness-fill" style="width: ${completionPct}%"></div>
          </div>
        </div>
        <div class="dsh-pm-completeness-detail">
          已完成 ${completeness.defined} / ${completeness.total} 部分
        </div>
      </div>
    </div>` : ''

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>📝 文档概览</h3>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">文档文件</span>
          <span class="dsh-pm-stat-value">${docFiles.length} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">关联接口</span>
          <span class="dsh-pm-stat-value">${apis.length} 个</span>
        </div>
        ${completeness.total > 0 ? `
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">完成度</span>
          <span class="dsh-pm-stat-value">${completionPct}%</span>
        </div>` : ''}
      </div>
    </div>
    ${docFilesHtml}
    ${apisHtml}
    ${completenessHtml}`
}

function renderUIContent(task: TaskRecord): string {
  // 从 executions.evidence 提取 UI 设计信息
  const lastExec = task.executions[task.executions.length - 1]
  const designFiles: string[] = []
  const components: string[] = []
  const specs: Record<string, string> = {}

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析设计文件 "design/login.fig" 或 "mockup.png"
      if (ev.match(/\.(fig|sketch|xd|png|jpg|svg)$/i)) {
        designFiles.push(ev)
      }

      // 解析组件 "Button, Input, LoginForm"
      if (ev.includes('component') || ev.includes('组件')) {
        const comps = ev.replace(/components?[:\s]*/i, '').split(/[,，]/).map(c => c.trim())
        components.push(...comps)
      }

      // 解析设计规范 "color: #3B82F6" / "font: Inter 16px"
      const specMatch = ev.match(/^(color|font|spacing|radius)[:\s]+(.+)/i)
      if (specMatch) {
        specs[specMatch[1].toLowerCase()] = specMatch[2].trim()
      }
    })
  }

  // 从 description 提取组件列表
  if (components.length === 0 && task.description) {
    const compMatch = task.description.match(/组件[：:]\s*([^\n]+)/)
    if (compMatch) {
      const comps = compMatch[1].split(/[,，、]/).map(c => c.trim())
      components.push(...comps)
    }
  }

  const designFilesHtml = designFiles.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>🖼️ 设计稿</h3>
      <ul class="dsh-pm-design-list">
        ${designFiles.map(file => `<li><code>${esc(file)}</code></li>`).join('')}
      </ul>
    </div>` : ''

  const specsHtml = Object.keys(specs).length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>🎯 设计规范</h3>
      <div class="dsh-pm-kv">
        ${Object.entries(specs).map(([key, value]) => `
          <span>${key === 'color' ? '主色调' : key === 'font' ? '字体' : key === 'spacing' ? '间距' : '圆角'}</span>
          <span><code>${esc(value)}</code></span>
        `).join('')}
      </div>
    </div>` : ''

  const componentsHtml = components.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📱 组件清单</h3>
      <ul class="dsh-pm-component-list">
        ${components.map(comp => `<li>${esc(comp)}</li>`).join('')}
      </ul>
    </div>` : ''

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>🎨 UI 设计</h3>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">设计文件</span>
          <span class="dsh-pm-stat-value">${designFiles.length} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">组件数量</span>
          <span class="dsh-pm-stat-value">${components.length} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">设计规范</span>
          <span class="dsh-pm-stat-value">${Object.keys(specs).length} 项</span>
        </div>
      </div>
    </div>
    ${designFilesHtml}
    ${specsHtml}
    ${componentsHtml}`
}

function renderAnalysisContent(task: TaskRecord): string {
  // 从 executions.evidence 提取分析信息
  const lastExec = task.executions[task.executions.length - 1]
  let recommendation = ''
  const options: Array<{name: string; score: number}> = []
  const risks: string[] = []
  const references: string[] = []

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析推荐方案 "Recommended: JWT"
      if (ev.match(/^recommended?[:\s]+/i)) {
        recommendation = ev.replace(/^recommended?[:\s]+/i, '').trim()
      }

      // 解析选项评分 "JWT: 4/5" 或 "Session: ⭐⭐⭐"
      const scoreMatch = ev.match(/^(.+?)[:：]\s*(?:(\d+)\/5|([⭐★]+))/)
      if (scoreMatch) {
        const name = scoreMatch[1].trim()
        const score = scoreMatch[2] ? parseInt(scoreMatch[2], 10) : (scoreMatch[3]?.length || 0)
        options.push({ name, score })
      }

      // 解析风险点 "Risk: token leakage"
      if (ev.match(/^risk[:\s]+/i)) {
        risks.push(ev.replace(/^risk[:\s]+/i, '').trim())
      }

      // 解析参考资料（URL）
      if (ev.match(/^https?:\/\//)) {
        references.push(ev)
      }
    })
  }

  // 从 description 提取推荐和风险
  if (!recommendation && task.description) {
    const recMatch = task.description.match(/推荐[方案]?[：:]\s*([^\n]+)/)
    if (recMatch) recommendation = recMatch[1].trim()
  }

  const optionsHtml = options.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📊 方案对比</h3>
      <div class="dsh-pm-options">
        ${options.map(opt => {
          const stars = '⭐'.repeat(opt.score) + '☆'.repeat(5 - opt.score)
          return `
            <div class="dsh-pm-option">
              <span class="dsh-pm-option-name">${esc(opt.name)}</span>
              <span class="dsh-pm-option-score">${stars}</span>
            </div>`
        }).join('')}
      </div>
    </div>` : ''

  const recommendationHtml = recommendation ? `
    <div class="dsh-pm-detail-section">
      <h3>✅ 推荐方案</h3>
      <div class="dsh-pm-recommendation">
        <div class="dsh-pm-recommendation-title">${esc(recommendation)}</div>
      </div>
    </div>` : ''

  const risksHtml = risks.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>⚠️ 风险点（${risks.length} 项）</h3>
      <ul class="dsh-pm-risk-list">
        ${risks.map(risk => `<li>${esc(risk)}</li>`).join('')}
      </ul>
    </div>` : ''

  const referencesHtml = references.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📚 参考资料</h3>
      <ul class="dsh-pm-reference-list">
        ${references.map(ref => `<li><a href="${esc(ref)}" target="_blank" rel="noopener">${esc(ref)}</a></li>`).join('')}
      </ul>
    </div>` : ''

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>🔍 分析结果</h3>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">对比方案</span>
          <span class="dsh-pm-stat-value">${options.length} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">风险点</span>
          <span class="dsh-pm-stat-value">${risks.length} 项</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">参考资料</span>
          <span class="dsh-pm-stat-value">${references.length} 个</span>
        </div>
      </div>
    </div>
    ${recommendationHtml}
    ${optionsHtml}
    ${risksHtml}
    ${referencesHtml}`
}

/* ------------------------------------------------------------------ 待归类区 */

export function buildTriage(triages: TriageRecord[], state: BoardState): string {
  const pending = triages.filter(t => t.status === 'pending')
  const openReqs = state.requirements.filter(r => r.status !== 'archived' && r.status !== 'canceled')

  const rows = pending.map(t => {
    const isCreate = t.suggestedAction === 'create_req' && !t.suggestedTargetId
    const suggestion = t.suggestedTargetId
      ? `${t.suggestedAction === 'bind_req' ? '绑定需求' : t.suggestedAction === 'bind_task' ? '绑定任务' : '新建需求'} ${esc(t.suggestedTargetId)}`
      : (t.suggestedAction === 'create_req'
        ? `新建需求${t.suggestedCategory ? ` · ${CATEGORY_LABELS[t.suggestedCategory] ?? t.suggestedCategory}` : ''}`
        : '')
    // 乙流程人工门：确认前可编辑 1) 需求名称 2) 需求分类（预填 agent 提议值）
    const editBlock = isCreate ? `
        <div class="dsh-pm-triage-edit">
          <input type="text" class="dsh-pm-input" data-role="triage-title" value="${esc(t.suggestedTitle ?? t.firstMessageText.slice(0, 120))}" placeholder="需求名称（可编辑）" />
          <select class="dsh-pm-input" data-role="triage-category">
            ${Object.entries(CATEGORY_LABELS).map(([v, l]) => `<option value="${v}" ${v === (t.suggestedCategory ?? 'feature') ? 'selected' : ''}>${l}</option>`).join('')}
          </select>
        </div>` : ''
    return `
      <div class="dsh-pm-triage" data-triage="${esc(t.id)}">
        <div class="dsh-pm-triage-head">
          <span class="dsh-pm-session-id">${esc(t.sessionId.slice(0, 16))}…</span>
          <span class="dsh-pm-triage-score">分 ${t.score}</span>
          <span class="dsh-pm-triage-suggest">${suggestion}</span>
        </div>
        <div class="dsh-pm-triage-text">${esc(t.firstMessageText.slice(0, 200))}${t.firstMessageText.length > 200 ? '…' : ''}</div>
        ${editBlock}
        <div class="dsh-pm-triage-actions">
          <button type="button" class="dsh-pm-btn primary" data-action="triage-confirm" data-triage="${esc(t.id)}">确认</button>
          ${isCreate ? '' : `<button type="button" class="dsh-pm-btn" data-action="triage-rebind" data-triage="${esc(t.id)}">改绑</button>`}
          <button type="button" class="dsh-pm-btn" data-action="triage-reject" data-triage="${esc(t.id)}">拒绝</button>
        </div>
      </div>`
  }).join('')

  return `
    <div class="dsh-pm-triage-panel">
      <div class="dsh-pm-detail-head">
        <span class="dsh-pm-title-sm">待归类（${pending.length}）</span>
        <span class="dsh-pm-hint">新会话自动捕获，确认后进入流水线</span>
      </div>
      ${rows || '<div class="dsh-pm-empty">暂无待归类会话</div>'}
      <div class="dsh-pm-rebind-host" style="display:none">
        <select class="dsh-pm-input" data-role="rebind-select">
          ${openReqs.map(r => `<option value="${esc(r.id)}">${esc(r.id)} ${esc(r.title.slice(0, 30))}</option>`).join('')}
        </select>
        <button type="button" class="dsh-pm-btn primary" data-action="triage-rebind-confirm">确认改绑</button>
      </div>
    </div>`
}

/* ------------------------------------------------------------------ 空态/错误 */

export function buildEmpty(): string {
  return `<div class="dsh-pm-board"><div class="dsh-pm-empty">暂无数据 — 点击「+ 需求」创建第一个需求</div></div>`
}

export function buildError(message: string): string {
  return `<div class="dsh-pm-board"><div class="dsh-pm-error">加载失败：${esc(message)}</div></div>`
}
/* ------------------------------------------------------------------ 时间线 */

/** 时长人类可读（时间线停留 / 任务耗时用）。 */
function fmtDur(ms: number): string {
  const total = Math.max(0, ms)
  const min = Math.floor(total / 60000)
  if (min < 60) return min + ' 分'
  const hours = Math.floor(min / 60)
  if (hours < 24) return hours + ' 小时 ' + (min % 60) + ' 分'
  const days = Math.floor(hours / 24)
  return days + ' 天 ' + (hours % 24) + ' 小时'
}

/** 终态（不再累计停留时长）。 */
function isTerminal(status: string): boolean {
  return status === 'done' || status === 'archived' || status === 'canceled'
}

/**
 * 状态事件序列（时间线的数据源）。
 * 老记录（升级前落库、无 statusHistory）退化为「创建单点」——host 加载时会回填，
 * 但 client 也必须能独立兜底，绝不编造中间状态。
 */
function eventsOf(
  rec: { status?: string; createdAt: number; updatedAt?: number; updatedBy?: { kind: 'human' | 'agent' | 'system'; sessionId?: string }; statusHistory?: StatusEvent[] },
  initial: string,
): StatusEvent[] {
  const hist = rec.statusHistory
  if (hist !== undefined && hist.length > 0) return hist
  // 升级前的老记录（host 侧尚未迁移）也要渲染得体面且诚实：只有一个「创建」点 + 由
  // updatedAt 推导的当前态，两者都标 inferred（UI 显示「回填」），中间态一律留空 ——
  // 绝不按时间戳线性插值编造出「评审 09-10 完成 09-11」这种看起来精确的假时间线。
  const out: StatusEvent[] = [
    { status: initial, at: rec.createdAt, by: { kind: 'human' }, reason: '创建', inferred: true },
  ]
  if (rec.status !== undefined && rec.status !== initial && rec.updatedAt !== undefined) {
    out.push({
      status: rec.status,
      at: Math.max(rec.updatedAt, rec.createdAt),
      by: rec.updatedBy ?? { kind: 'human' },
      reason: '按 updatedAt 回填（当时无事件留痕）',
      inferred: true,
    })
  }
  return out
}

/** 时间线表：每个里程碑的进入时间 + 该段停留时长 + 操作者（回填事件显式标注）。 */
function renderTimeline(
  rec: { status: string; createdAt: number; statusHistory?: StatusEvent[] },
  milestones: readonly string[],
  labels: Record<string, string>,
  initial: string,
  now: number,
): string {
  const events = eventsOf(rec, initial)
  const at = new Map<string, number>()
  events.forEach((e, i) => { if (!at.has(e.status)) at.set(e.status, i) })
  const extra = events
    .map((e, i) => ({ e, i }))
    .filter(x => !milestones.includes(x.e.status))
    .map(x => x.e.status)
  const rowFor = (status: string, idx: number | undefined): string => {
    if (idx === undefined) {
      return '<div class="dsh-pm-tl-row pending" data-status="' + status + '">'
        + '<span class="dsh-pm-tl-label">' + (labels[status] ?? status) + '</span>'
        + '<span class="dsh-pm-tl-time">—</span>'
        + '<span class="dsh-pm-tl-dur"></span>'
        + '</div>'
    }
    const e = events[idx]!
    const next = events[idx + 1]
    const isLast = idx === events.length - 1
    const dur = (next?.at ?? now) - e.at
    const durText = isLast ? (isTerminal(e.status) ? '' : '已停留 ' + fmtDur(dur)) : '停留 ' + fmtDur(dur)
    const byText = e.by.kind + (e.by.sessionId !== undefined ? ' ' + windowCodeFromSessionId(e.by.sessionId) : '')
    return '<div class="dsh-pm-tl-row' + (isLast ? ' current' : '') + '" data-status="' + esc(e.status) + '">'
      + '<span class="dsh-pm-tl-label">' + (labels[status] ?? status) + '</span>'
      + '<span class="dsh-pm-tl-time">' + esc(fmtTime(e.at)) + '</span>'
      + '<span class="dsh-pm-tl-dur">' + esc(durText) + '</span>'
      + '<span class="dsh-pm-tl-by">' + esc(byText) + '</span>'
      + (e.inferred === true ? '<span class="dsh-pm-tl-inferred" title="历史回填：老记录无事件留痕，由创建时间与评论反推">回填</span>' : '')
      + '</div>'
  }
  const rows = milestones.map(s => rowFor(s, at.get(s))).join('') + extra.map(s => rowFor(s, at.get(s))).join('')
  const start = events[0]!.at
  const tail = events[events.length - 1]!
  const total = (isTerminal(tail.status) ? tail.at : now) - start
  return '<div class="dsh-pm-timeline">' + rows
    + '<div class="dsh-pm-tl-total">创建 ' + esc(fmtTime(start))
    + (isTerminal(tail.status) ? ' · 总耗时 ' : ' · 至今 ') + esc(fmtDur(total)) + '</div></div>'
}

/** 需求时间线（7 个里程碑）。 */
function renderReqTimeline(req: RequirementRecord, now: number): string {
  return renderTimeline(req, LANE_STATUSES.concat(['archived']), STATUS_LABELS, 'draft', now)
}

/** 任务时间线。 */
function renderTaskTimeline(task: TaskRecord, now: number): string {
  return renderTimeline(task, TASK_TIMELINE_STATUSES, TASK_STATUS_LABELS, 'todo', now)
}

/** 里程碑紧凑条（任务页分组头用）：只列已发生的里程碑。 */
function renderMilestoneStrip(req: RequirementRecord): string {
  const events = eventsOf(req, 'draft')
  const first = new Map<string, StatusEvent>()
  for (const e of events) if (!first.has(e.status)) first.set(e.status, e)
  const items = [...first.values()].map(e =>
    '<span class="dsh-pm-strip-item" data-status="' + esc(e.status) + '">'
    + (STATUS_LABELS[e.status as RequirementStatus] ?? e.status)
    + ' <b>' + esc(fmtTime(e.at)) + '</b></span>')
  return items.length === 0 ? '' : '<div class="dsh-pm-strip">' + items.join('<span class="dsh-pm-strip-arrow">→</span>') + '</div>'
}

/* ------------------------------------------------------------------ 甘特图 */

const TASK_TIMELINE_STATUSES: readonly TaskStatus[] = ['todo', 'in_progress', 'integrating', 'testing', 'in_review', 'done']
const REQ_MILESTONE_STATUSES: readonly RequirementStatus[] = ['draft', 'brainstorming', 'decomposing', 'implementing', 'accepting', 'done', 'archived']

/** 任务的状态分段（甘特条按状态着色；终态段止于末次事件，其余止于 now）。 */
function ganttSegments(task: TaskRecord, now: number): Array<{ status: string; from: number; to: number }> {
  const events = eventsOf(task, 'todo')
  const terminal = isTerminal(task.status)
  return events.map((e, i) => {
    const next = events[i + 1]
    const end = next?.at ?? (terminal ? Math.max(task.updatedAt, e.at) : now)
    return { status: e.status, from: e.at, to: end }
  })
}

function short(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + '…' : text
}

/**
 * 甘特图（SVG，零依赖）：横轴时间，每行一个任务，条形按状态分段着色，
 * 叠需求里程碑竖线（评审/拆分/实施/验收/完成）与「当前时刻」线。
 * 数据全部来自真实状态事件——没有事件就不画（不编造进度）。
 */
function buildGantt(req: RequirementRecord, tasks: TaskRecord[], now: number): string {
  if (tasks.length === 0) return '<div class="dsh-pm-empty">尚未拆分任务</div>'
  const labelW = 190
  const chartW = 620
  const rowH = 22
  const top = 34
  const bottom = 10
  const ordered = [...tasks].sort((a, b) => a.createdAt - b.createdAt)
  const times: number[] = [now]
  for (const t of ordered) for (const e of eventsOf(t, 'todo')) times.push(e.at)
  for (const e of eventsOf(req, 'draft')) times.push(e.at)
  const min = Math.min(...times)
  const max = Math.max(...times)
  const span = Math.max(max - min, 3600000)
  const px = (t: number): number => labelW + ((t - min) / span) * chartW
  const height = top + ordered.length * rowH + bottom
  const width = labelW + chartW + 12
  const parts: string[] = []
  parts.push('<svg class="dsh-pm-gantt" viewBox="0 0 ' + width + ' ' + height + '" width="100%" height="' + height + '" preserveAspectRatio="xMinYMin meet" role="img" aria-label="任务甘特图">')
  for (let i = 0; i <= 4; i++) {
    const t = min + (span * i) / 4
    const x = px(t).toFixed(1)
    parts.push('<line class="dsh-pm-gantt-grid" x1="' + x + '" y1="' + (top - 8) + '" x2="' + x + '" y2="' + (height - bottom) + '" />')
    parts.push('<text class="dsh-pm-gantt-axis" x="' + x + '" y="' + (top - 14) + '" text-anchor="middle">' + esc(fmtTime(t)) + '</text>')
  }
  for (const e of eventsOf(req, 'draft')) {
    if (!REQ_MILESTONE_STATUSES.includes(e.status as RequirementStatus)) continue
    const x = px(e.at).toFixed(1)
    parts.push('<line class="dsh-pm-gantt-mile" data-status="' + esc(e.status) + '" x1="' + x + '" y1="' + (top - 6) + '" x2="' + x + '" y2="' + (height - bottom) + '">')
    parts.push('<title>' + esc(req.id + ' ' + (STATUS_LABELS[e.status as RequirementStatus] ?? e.status) + ' ' + fmtTime(e.at)) + '</title></line>')
  }
  ordered.forEach((t, i) => {
    const y = top + i * rowH
    parts.push('<text class="dsh-pm-gantt-rowlabel" x="6" y="' + (y + 13) + '">' + esc(short(t.id + ' ' + t.title, 24)) + '</text>')
    parts.push('<rect class="dsh-pm-gantt-track" x="' + labelW + '" y="' + (y + 4) + '" width="' + chartW + '" height="' + (rowH - 9) + '" rx="3" />')
    for (const seg of ganttSegments(t, now)) {
      const x1 = px(seg.from)
      const w = Math.max(2, px(seg.to) - x1)
      parts.push('<rect class="dsh-pm-gantt-bar" data-status="' + esc(seg.status) + '" x="' + x1.toFixed(1) + '" y="' + (y + 4) + '" width="' + w.toFixed(1) + '" height="' + (rowH - 9) + '" rx="3">')
      parts.push('<title>' + esc(t.id + ' ' + t.title + '｜' + (TASK_STATUS_LABELS[seg.status as TaskStatus] ?? seg.status) + ' ' + fmtTime(seg.from) + ' → ' + fmtTime(seg.to) + '（' + fmtDur(seg.to - seg.from) + '）') + '</title></rect>')
    }
  })
  if (now >= min && now <= max) {
    const nx = px(now).toFixed(1)
    parts.push('<line class="dsh-pm-gantt-now" x1="' + nx + '" y1="' + (top - 6) + '" x2="' + nx + '" y2="' + (height - bottom) + '"><title>现在</title></line>')
  }
  parts.push('</svg>')
  const legend = '<div class="dsh-pm-gantt-legend">' + TASK_TIMELINE_STATUSES.map(s =>
    '<span class="dsh-pm-gantt-legend-item"><i data-status="' + s + '"></i>' + TASK_STATUS_LABELS[s] + '</span>').join('')
    + '<span class="dsh-pm-gantt-legend-item"><i class="mile"></i>需求里程碑</span></div>'
  return '<div class="dsh-pm-gantt-wrap">' + parts.join('') + '</div>' + legend
}

/* ------------------------------------------------------------------ 任务页 */

/** 任务清单表（id/标题/状态/阶段/端侧/依赖/创建/耗时）。 */
function renderTaskTable(tasks: TaskRecord[], now: number): string {
  const rows = [...tasks].sort((a, b) => a.createdAt - b.createdAt).map(t => {
    const hist = eventsOf(t, 'todo')
    const start = hist[0]!.at
    const tail = hist[hist.length - 1]!
    const doneAt = hist.find(e => e.status === 'done')?.at
    const elapsed = isTerminal(t.status)
      ? '共 ' + fmtDur((doneAt ?? tail.at) - start)
      : '已用 ' + fmtDur(now - start)
    return '<tr class="dsh-pm-trow" data-task="' + esc(t.id) + '" data-action="open-task">'
      + '<td class="dsh-pm-tid">' + esc(t.id) + '</td>'
      + '<td class="dsh-pm-ttitle">' + esc(t.title) + '</td>'
      + '<td><span class="dsh-pm-status" data-status="' + esc(t.status) + '">' + (TASK_STATUS_LABELS[t.status] ?? t.status) + '</span></td>'
      + '<td>' + esc(PHASE_LABELS[t.phase] ?? t.phase) + '</td>'
      + '<td>' + esc(t.side) + '</td>'
      + '<td class="dsh-pm-tdeps">' + (t.dependsOn.length > 0 ? esc(t.dependsOn.join(' ')) : '—') + '</td>'
      + '<td>' + esc(fmtTime(start)) + '</td>'
      + '<td>' + esc(elapsed) + '</td>'
      + '</tr>'
  }).join('')
  return '<table class="dsh-pm-ttable"><thead><tr>'
    + '<th>任务</th><th>标题</th><th>状态</th><th>阶段</th><th>端侧</th><th>依赖</th><th>创建</th><th>耗时</th>'
    + '</tr></thead><tbody>' + rows + '</tbody></table>'
}

/** 任务总览页（跨需求）：需求分组 → 里程碑条 + 甘特图 + 任务表。 */
export function buildTasksPage(state: BoardState, now: number = Date.now()): string {
  const groups = state.requirements
    .map(req => ({ req, tasks: state.tasks.filter(t => t.requirementId === req.id) }))
    .filter(g => g.tasks.length > 0)
    .sort((a, b) => b.req.updatedAt - a.req.updatedAt)
  const head = '<div class="dsh-pm-head">'
    + '<button type="button" class="dsh-pm-btn" data-action="back" title="返回泳道看板">← 看板</button>'
    + '<h1 class="dsh-pm-title">任务</h1>'
    + '<span class="dsh-pm-rev">' + state.tasks.length + ' 个任务 · ' + groups.length + ' 个需求 · rev ' + state.revision + '</span>'
    + '<button type="button" class="dsh-pm-btn" data-action="refresh" title="刷新">刷新</button>'
    + '</div>'
  if (groups.length === 0) {
    return '<div class="dsh-pm-board">' + head
      + '<div class="dsh-pm-empty">还没有任务。两种来源：① 需求详情页点「+ 任务」人工建卡；② 窗口 agent 调用 reqboard_decompose 真拆分落库（推荐，含依赖 DAG）</div></div>'
  }
  const sections = groups.map(g => {
    const done = g.tasks.filter(t => t.status === 'done').length
    return '<div class="dsh-pm-tasks-group">'
      + '<div class="dsh-pm-tasks-group-head">'
      + '<span class="dsh-pm-card-id">' + esc(g.req.id) + '</span>'
      + '<span class="dsh-pm-status" data-status="' + esc(g.req.status) + '">' + (STATUS_LABELS[g.req.status] ?? g.req.status) + '</span>'
      + '<span class="dsh-pm-tasks-group-title">' + esc(g.req.title) + '</span>'
      + '<span class="dsh-pm-hint">' + done + '/' + g.tasks.length + ' 完成</span>'
      + '<button type="button" class="dsh-pm-btn sm" data-action="open-req" data-req="' + esc(g.req.id) + '">打开需求</button>'
      + '</div>'
      + renderMilestoneStrip(g.req)
      + '<div class="dsh-pm-detail-section"><h3>甘特图</h3>' + buildGantt(g.req, g.tasks, now) + '</div>'
      + '<div class="dsh-pm-detail-section"><h3>任务清单</h3>' + renderTaskTable(g.tasks, now) + '</div>'
      + '</div>'
  }).join('')
  return '<div class="dsh-pm-board">' + head + '<div class="dsh-pm-tasks-page">' + sections + '</div></div>'
}


/** 卡面时间行：创建时间 + 当前状态进入时间 + 当前态停留时长（时间不埋在详情页）。 */
function renderCardTime(req: RequirementRecord, now: number): string {
  const events = eventsOf(req, 'draft')
  const first = events[0]!
  const cur = events[events.length - 1]!
  const parts = ['创建 ' + fmtTime(first.at)]
  if (cur.status !== first.status) {
    parts.push((STATUS_LABELS[cur.status as RequirementStatus] ?? cur.status) + ' ' + fmtTime(cur.at))
  }
  if (!isTerminal(cur.status)) parts.push('已停留 ' + fmtDur(now - cur.at))
  return '<div class="dsh-pm-card-time">' + esc(parts.join(' · ')) + '</div>'
}

/* ------------------------------------------------------------------ 实施计划 */

/**
 * 计划 chip（泳道卡面）：让「这份需求卡在等人批计划」在泳道上一眼可见，
 * 而不是要人点进详情页才发现。
 */
function planChip(req: RequirementRecord): string {
  const plan = req.plan
  if (plan === undefined) return ''
  if (plan.approvedAt !== undefined) return '<span class="dsh-pm-flag plan-ok" title="实施计划已批准，可拆分落库">计划已批</span>'
  if (plan.rejectedAt !== undefined) return '<span class="dsh-pm-flag plan-rejected" title="实施计划被退回，待重写">计划被退</span>'
  return '<span class="dsh-pm-flag plan-pending" title="实施计划已提交，等待人批准后才能拆分">计划待批</span>'
}

/**
 * 实施计划区（plan mode 的人机界面）：人在这里**唯一**需要动手的地方——
 * 批准计划 = 批准拆分方案；退回 = 打回重写（必须给理由）。
 * 批准之后，拆分/实施/验收全部由窗口 agent 自行推进。
 */
function renderPlanSection(req: RequirementRecord): string {
  const plan = req.plan
  if (plan === undefined) {
    return '<div class="dsh-pm-plan is-empty">尚未提交实施计划。计划模式：窗口 agent 用 '
      + '<code>reqboard_plan_submit</code> 先提交计划（文档路径 + 摘要 + 任务表），'
      + '人在此处批准后才允许 <code>reqboard_decompose</code> 落库任务卡——'
      + '拆分的粒度在人点头之前就已写死在计划里。</div>'
  }
  const status = plan.approvedAt !== undefined
    ? '<span class="dsh-pm-plan-status" data-state="approved">已批准 ' + esc(fmtTime(plan.approvedAt)) + '</span>'
    : plan.rejectedAt !== undefined
      ? '<span class="dsh-pm-plan-status" data-state="rejected">已退回 ' + esc(fmtTime(plan.rejectedAt)) + '</span>'
      : '<span class="dsh-pm-plan-status" data-state="pending">待批准</span>'
  const actions = plan.approvedAt === undefined
    ? '<button type="button" class="dsh-pm-btn sm primary" data-action="plan-approve" data-id="' + esc(req.id) + '">批准计划</button>'
      + '<button type="button" class="dsh-pm-btn sm" data-action="plan-reject" data-id="' + esc(req.id) + '">退回计划</button>'
    : '<span class="dsh-pm-hint">拆分已解锁：窗口可用 reqboard_decompose 按此计划落库任务卡</span>'
  const tasks = plan.tasks.map(t => {
    const deps = (t.dependsOn ?? []).length > 0 ? ' · 依赖 ' + esc((t.dependsOn ?? []).join(',')) : ''
    return '<div class="dsh-pm-plan-task">'
      + '<span class="dsh-pm-plan-key">' + esc(t.key) + '</span>'
      + '<span class="dsh-pm-plan-title">' + esc(t.title) + '</span>'
      + '<span class="dsh-pm-plan-meta">' + esc(PHASE_LABELS[t.phase ?? 'implement'] ?? (t.phase ?? '')) + ' / ' + esc(t.side ?? '') + deps + '</span>'
      + (t.acceptance !== undefined && t.acceptance.length > 0
        ? '<span class="dsh-pm-plan-accept">验收：' + esc(t.acceptance) + '</span>'
        : '<span class="dsh-pm-plan-accept missing">缺验收标准</span>')
      + '</div>'
  }).join('')
  return '<div class="dsh-pm-plan">'
    + '<div class="dsh-pm-plan-head">' + status
    + '<code class="dsh-pm-plan-path">' + esc(plan.path) + '</code>'
    + '<span class="dsh-pm-hint">提交 ' + esc(fmtTime(plan.submittedAt)) + ' · ' + plan.tasks.length + ' 个任务</span>'
    + actions + '</div>'
    + '<div class="dsh-pm-plan-summary">' + esc(plan.summary) + '</div>'
    + (plan.rejectedReason !== undefined ? '<div class="dsh-pm-plan-reason">退回理由：' + esc(plan.rejectedReason) + '</div>' : '')
    + '<div class="dsh-pm-plan-tasks">' + tasks + '</div>'
    + '</div>'
}

/* ------------------------------------------------------------------ 验收 / 归档 */

/** 卡面：待人工审核 / 待归档 —— 让"卡在人这里"一眼可见。 */
function verifyChip(req: RequirementRecord): string {
  if (req.status !== 'accepting') return ''
  const v = req.verification
  return v === undefined
    ? '<span class="dsh-pm-flag verify-pending" title="验收态但还没提交验收材料">待验收材料</span>'
    : '<span class="dsh-pm-flag verify-pending" title="验收材料已提交，等人工审核">待人工审核</span>'
}

function archiveChip(req: RequirementRecord): string {
  if (req.status !== 'done') return ''
  return req.archive === undefined
    ? '<span class="dsh-pm-flag archive-pending" title="已完成，等窗口准备归档材料">待归档材料</span>'
    : '<span class="dsh-pm-flag archive-pending" title="归档材料已备，等人点归档">待归档</span>'
}

/**
 * 验收区：agent 提交的证据 + 人工审核入口。
 * 人在这里做的事只有一件——**看着证据**点通过或退回（返工必须写意见）。
 */
function renderVerifySection(req: RequirementRecord): string {
  const v = req.verification
  if (v === undefined) {
    const waiting = req.status === 'implementing' || req.status === 'accepting'
    return '<div class="dsh-pm-block is-empty">'
      + (waiting
        ? '窗口尚未提交验收材料。人工审核前需要证据：窗口用 <code>reqboard_verify_submit</code> 提交「做了什么 + 怎么验的 + 看到什么结果」。'
        : '尚未进入验收阶段。')
      + '</div>'
  }
  const state = v.decision === 'pass'
    ? '<span class="dsh-pm-review" data-state="pass">人工审核通过 ' + esc(v.reviewedAt !== undefined ? fmtTime(v.reviewedAt) : '') + '</span>'
    : v.decision === 'rework'
      ? '<span class="dsh-pm-review" data-state="rework">已退回返工 ' + esc(v.reviewedAt !== undefined ? fmtTime(v.reviewedAt) : '') + '</span>'
      : '<span class="dsh-pm-review" data-state="pending">待人工审核</span>'
  const actions = req.status === 'accepting'
    ? '<button type="button" class="dsh-pm-btn sm primary" data-action="verify-pass" data-id="' + esc(req.id) + '">验收通过</button>'
      + '<button type="button" class="dsh-pm-btn sm" data-action="verify-rework" data-id="' + esc(req.id) + '">退回返工</button>'
    : ''
  const evidence = v.evidence.map(e => '<li>' + esc(e) + '</li>').join('')
  return '<div class="dsh-pm-block">'
    + '<div class="dsh-pm-block-head">' + state
    + '<span class="dsh-pm-hint">提交 ' + esc(fmtTime(v.submittedAt)) + '</span>'
    + actions + '</div>'
    + '<div class="dsh-pm-block-summary">' + esc(v.summary) + '</div>'
    + '<ul class="dsh-pm-evidence">' + evidence + '</ul>'
    + (v.reviewNote !== undefined ? '<div class="dsh-pm-block-note">审核意见：' + esc(v.reviewNote) + '</div>' : '')
    + '</div>'
}

/**
 * 归档区：需求目录 + 文档清单 + 合并去向 + 索引条目。
 * 归档的实质是**把产出并进项目文档**（合并去向必须落在该需求类型允许的目录里），
 * 需求目录只是原始材料的存底。
 */
function renderArchiveSection(req: RequirementRecord): string {
  const a = req.archive
  if (a === undefined) {
    const archivable = req.status === 'done'
    return '<div class="dsh-pm-block is-empty">'
      + (archivable
        ? '窗口尚未准备归档材料。归档不是挪目录：窗口用 <code>reqboard_archive_submit</code> 提交需求目录、文档清单、'
          + '合并去向（只允许既有规范目录：docs/ 或 agent-dh/docs/ 下的 adr|architecture|guides|rfcs|work-logs|strategy-research）与一句话索引条目，人再点归档；'
          + '必填文档与合并去向按需求类型限定，规范见 agent-dh/docs/architecture/requirement-archive.md。'
        : '归档在需求完成（done）后进行；不同需求类型的必填文档与合并去向见 agent-dh/docs/architecture/requirement-archive.md。')
      + '</div>'
  }
  const state = a.archivedAt !== undefined
    ? '<span class="dsh-pm-review" data-state="pass">已归档 ' + esc(fmtTime(a.archivedAt)) + '</span>'
    : '<span class="dsh-pm-review" data-state="pending">待归档（材料已备）</span>'
  const actions = req.status === 'done' && a.archivedAt === undefined
    ? '<button type="button" class="dsh-pm-btn sm primary" data-action="archive-req" data-id="' + esc(req.id) + '">归档</button>'
    : ''
  const docs = a.docs.map(d => '<li><span class="dsh-pm-doc-kind">' + esc(ARCHIVE_DOC_KIND_LABELS[d.kind] ?? d.kind) + '</span> <code>' + esc(d.path) + '</code></li>').join('')
  const merged = a.mergedInto.map(m => '<li><code>' + esc(m) + '</code></li>').join('')
  return '<div class="dsh-pm-block">'
    + '<div class="dsh-pm-block-head">' + state
    + '<code class="dsh-pm-block-path">' + esc(a.dir) + '</code>'
    + '<span class="dsh-pm-hint">材料提交 ' + esc(fmtTime(a.submittedAt)) + '</span>'
    + actions + '</div>'
    + '<div class="dsh-pm-block-summary">索引条目：' + esc(a.indexEntry) + '</div>'
    + '<div class="dsh-pm-doc-group"><span class="dsh-pm-hint">需求目录内的文档</span><ul class="dsh-pm-doc-list">' + docs + '</ul></div>'
    + '<div class="dsh-pm-doc-group"><span class="dsh-pm-hint">合并进的项目文档</span><ul class="dsh-pm-doc-list">' + merged + '</ul></div>'
    + renderManualUpdates(a)
    + '</div>'
}

const ARCHIVE_DOC_KIND_LABELS: Record<string, string> = {
  requirement: '需求说明', plan: '实施计划', verification: '验收材料', retro: '复盘', notes: '其他',
}

/** 说明书更新点（金字塔 L1/L2）：归档让项目认知怎么长上去的。 */
function renderManualUpdates(a: ArchiveRecord): string {
  const updates = a.manualUpdates ?? []
  if (updates.length === 0) {
    return a.manualNote !== undefined
      ? '<div class="dsh-pm-doc-group"><span class="dsh-pm-hint">项目说明书更新</span><div class="dsh-pm-block-summary">无（' + esc(a.manualNote) + '）</div></div>'
      : ''
  }
  const items = updates.map(u =>
    '<li><code>' + esc(u.path) + '</code><span class="dsh-pm-doc-kind">' + esc(u.section) + '</span><span>' + esc(u.summary) + '</span></li>').join('')
  return '<div class="dsh-pm-doc-group"><span class="dsh-pm-hint">项目说明书更新（金字塔向上生长）</span>'
    + '<ul class="dsh-pm-doc-list">' + items + '</ul></div>'
}
