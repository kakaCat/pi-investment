/**
 * 泳道看板（Kanban）与列表视图渲染（REQ-47939a t11 从 view.ts 机械拆分）。
 * 数据 → innerHTML 纯字符串，交互经 data-action 委派 board-mount；含待归类区。
 *
 * @module dsh-pmboard/client/views/board
 */
import { esc } from '../html.js'
import { renderPagination } from '../render/pagination.js'
import type { BoardState, ReqCard } from '../types.ts'
import { CATEGORY_LABELS, LANE_STATUSES, NO_ARCHIVED, STATUS_LABELS, fmtTime, sessionChipHtml, windowCodeFromSessionId } from '../render/dom-utils.ts'
import { cardActions, renderReqCard } from './artifacts.ts'
import { fmtTokens } from '../../shared/protocol.ts'

/** 需求卡片投影（视图层聚合，避免全量渲染） */
export function toReqCards(state: BoardState): ReqCard[] {
  return state.requirements
    // REQ-f0579a t2 恢复：done 不排除——REQ-6f39b5 设计为「done（待归档）归入验收泳道」，
    // 972b2262 基线归一曾把旧版（连 done 一起过滤）盖回，导致已完成需求从看板消失。
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
        ...(state.tokenTotals?.[req.id] !== undefined ? { tokenTotal: state.tokenTotals[req.id] } : {}),
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
    // REQ-6f39b5：done（待归档）需求归入验收泳道显示（REQ-f0579a t2 恢复，972b2262 曾丢失）
    const inLane = status === 'accepting'
      ? cards.filter(c => c.req.status === 'accepting' || c.req.status === 'done')
      : cards.filter(c => c.req.status === status)
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

export const LIST_SORT_LABELS: ReadonlyArray<{ key: ListSortKey; label: string }> = [
  { key: 'stage', label: '阶段' },
  { key: 'progress', label: '进度' },
  { key: 'updated', label: '最近更新' },
  { key: 'created', label: '创建时间' },
  { key: 'title', label: '名称' },
]

/** 流水线阶段序（越小越靠前：实施中在最上）—— stage 排序用。 */
export const STAGE_RANK: Record<string, number> = {
  implementing: 0, accepting: 1, decomposing: 2, design: 3, brainstorming: 4, draft: 5, done: 6,
}

export function listPct(card: ReqCard): number {
  return card.totalCount > 0 ? card.doneCount / card.totalCount : 0
}

/** 排序键 → 升序比较函数（方向由调用方翻转）。 */
export function listComparator(key: ListSortKey): (a: ReqCard, b: ReqCard) => number {
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
 * 分页（每页 10/20/50，复用 render/pagination，data-pmpage）。
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
  // REQ-9f4a44：终态是 archived（done 为历史遗留）——两者都归入"完成"区
  const active = cards.filter(c => c.req.status !== 'done' && c.req.status !== 'archived')
  const finished = cards.filter(c => c.req.status === 'done' || c.req.status === 'archived')
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
      rowsHtml.push(`<tr class="dsh-pm-list-grouphead" data-group="active"><td colspan="8">进行中 ${active.length}${globalIdx > 0 ? '（续）' : ''}</td></tr>`)
    }
    if (finished.length > 0 && (globalIdx === doneStart || (globalIdx === pageStart && globalIdx >= doneStart))) {
      rowsHtml.push(`<tr class="dsh-pm-list-grouphead" data-group="done"><td colspan="8">已完成 ${finished.length}${globalIdx > doneStart ? '（续）' : ''}</td></tr>`)
    }
    rowsHtml.push(renderListCard(slice[i], now, archived))
  }

  const pager = ordered.length > pageSize
    ? `<div class="dsh-pm-pager">${renderPagination({
        page, total: totalPages, totalItems: ordered.length, pageAttr: 'data-pmpage',
      })}</div>`
    : ''

  return `<div class="dsh-pm-list">${toolbar}<table class="dsh-pm-table"><thead><tr><th>ID</th><th>标题</th><th>分类</th><th>状态</th><th>进度</th><th>负责人</th><th>更新时间</th><th>操作</th></tr></thead><tbody>${rowsHtml.join('')}</tbody></table>${pager}</div>`
}

/** 列表工具条：排序键按钮（同键切换升降序）+ 每页条数 + 计数。 */
export function renderListToolbar(
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
export function renderListCard(card: ReqCard, _now: number, archived: ReadonlySet<string> = NO_ARCHIVED): string {
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

    // REQ-9f4a44：验收通过即 archived，材料随后补齐——未提交归档材料时给看板可见标记
    const archivePendingChip = req.status === 'archived' && req.archive === undefined
      ? '<span class="dsh-pm-chip is-warn">归档材料待补</span>'
      : ''

    // REQ-6f39b5：列表行改为表格结构（对齐 list-prototype.html）
    // 列：ID | 标题 | 分类 | 状态 | 进度 | 负责人 | 更新时间 | 操作
    const rowCls = 'dsh-pm-list-row' + (blocked ? ' is-blocked' : '')
      + ((req.status === 'done' || req.status === 'archived') ? ' is-archived' : '')
    const sessionBtn = sid !== undefined && sid.length > 0 && !sidArchived
      ? `<button type="button" class="dsh-pm-btn sm" data-action="jump-session" data-sid="${esc(sid)}" title="跳转到来源会话">会话</button>`
      : ''
    return `
      <tr class="${rowCls}" data-req="${esc(req.id)}" data-action="open-req">
        <td><span class="dsh-pm-card-id">${esc(req.id)}</span></td>
        <td class="dsh-pm-td-title">
          <span class="dsh-pm-list-title" data-action="open-req" data-req="${esc(req.id)}">${esc(req.title)}</span>
          ${card.tokenTotal !== undefined ? `<span class="dsh-pm-token-badge" title="累计 Token（会话快照差值合计）">🪙 ${esc(fmtTokens(card.tokenTotal))}</span>` : ''}
          ${blockedChip}${archivePendingChip}
        </td>
        <td>${cat}</td>
        <td><span class="dsh-pm-status-badge" data-status="${req.status}">${STATUS_LABELS[req.status]}</span></td>
        <td class="dsh-pm-td-progress">
          <div class="dsh-pm-list-progress">
            <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${pct}%"></div></div>
            <span class="dsh-pm-list-pct">${pct}%${active > 0 ? `（${active} 进行中）` : ''}</span>
          </div>
        </td>
        <td>${windowChip}</td>
        <td><span class="dsh-pm-list-when">${fmtTime(req.updatedAt)}</span></td>
        <td><div class="dsh-pm-list-actions">${cardActions(req)}${sessionBtn}</div></td>
      </tr>`
}

