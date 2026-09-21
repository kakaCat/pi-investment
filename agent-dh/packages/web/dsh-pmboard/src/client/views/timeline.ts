/**
 * 时间线 / 甘特图 / 任务总览页渲染（REQ-47939a t11 从 view.ts 机械拆分）。
 *
 * @module dsh-pmboard/client/views/timeline
 */
import { esc } from '../html.js'
import type { BoardState, RequirementRecord, RequirementStatus, StatusEvent, TaskRecord, TaskStatus } from '../types.ts'
import { LANE_STATUSES, PHASE_LABELS, STATUS_LABELS, TASK_STATUS_LABELS, fmtDur, fmtTime, isTerminal, short, windowCodeFromSessionId } from '../render/dom-utils.ts'

/**
 * 状态事件序列（时间线的数据源）。
 * 老记录（升级前落库、无 statusHistory）退化为「创建单点」——host 加载时会回填，
 * 但 client 也必须能独立兜底，绝不编造中间状态。
 */
export function eventsOf(
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
export function renderTimeline(
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
export function renderReqTimeline(req: RequirementRecord, now: number): string {
  // REQ-6f39b5 用户裁定：时间线里程碑 7 态（不含 done/完成 —— REQ-9f4a44 后验收通过直接归档，
  // done 为 legacy 死状态，不再作为节点呈现）；archived 归档为最终节点
  return renderTimeline(req, [...LANE_STATUSES, 'archived'], STATUS_LABELS, 'draft', now)
}

/** 任务时间线。 */
export function renderTaskTimeline(task: TaskRecord, now: number): string {
  return renderTimeline(task, TASK_TIMELINE_STATUSES, TASK_STATUS_LABELS, 'todo', now)
}

/** 里程碑紧凑条（任务页分组头用）：只列已发生的里程碑。 */
export function renderMilestoneStrip(req: RequirementRecord): string {
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

export const TASK_TIMELINE_STATUSES: readonly TaskStatus[] = ['todo', 'in_progress', 'integrating', 'testing', 'in_review', 'done']
export const REQ_MILESTONE_STATUSES: readonly RequirementStatus[] = ['draft', 'brainstorming', 'decomposing', 'implementing', 'accepting', 'done', 'archived']

/** 任务的状态分段（甘特条按状态着色；终态段止于末次事件，其余止于 now）。 */
export function ganttSegments(task: TaskRecord, now: number): Array<{ status: string; from: number; to: number }> {
  const events = eventsOf(task, 'todo')
  const terminal = isTerminal(task.status)
  return events.map((e, i) => {
    const next = events[i + 1]
    const end = next?.at ?? (terminal ? Math.max(task.updatedAt, e.at) : now)
    return { status: e.status, from: e.at, to: end }
  })
}

/**
 * 甘特图（SVG，零依赖）：横轴时间，每行一个任务，条形按状态分段着色，
 * 叠需求里程碑竖线（需求分析/拆分/实施/验收/完成）与「当前时刻」线。
 * 数据全部来自真实状态事件——没有事件就不画（不编造进度）。
 */
export function buildGantt(req: RequirementRecord, tasks: TaskRecord[], now: number): string {
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
export function renderTaskTable(tasks: TaskRecord[], now: number): string {
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
