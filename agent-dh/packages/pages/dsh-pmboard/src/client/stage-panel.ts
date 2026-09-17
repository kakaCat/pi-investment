/**
 * 阶段详情面板 v4 —— 单节点「工作记录」渲染器（纯字符串，template method 模式）。
 *
 * 设计稿：docs/requirements/REQ-31e11f/stage-detail-design.md（v4，用户已确认）：
 *   - 一个一个的：点哪个节点只看哪个节点，纯文字排版，零装饰（无 pill/徽章/进度条）；
 *   - 核心是产物文档、拆分方案、实施列表（做到哪/做了多少/还剩多少）；
 *   - 每个任务标明执行者（w-xxx=窗口 / sub w-xxx=subagent）与时间，失败标红可追溯；
 *   - 颜色纪律：正文黑 / 辅助灰 / 链接蓝 / 警示红。
 *
 * 结构（renderStagePanel 固定骨架）：
 *   1. 面板头：状态符 + 节点名 · 状态一句话 + 右侧最近动态时间；
 *   2. 节点专属内容（StageRenderers[stage].renderBody 分发）；
 *   3. 产物文档行（文字链接，可点开；缺失必备产物红字）；
 *   4. 动态（谁/何时/做了什么，最近 5 条）；
 *   5. 产物追溯链一行。
 *
 * renderStageNode(overview, stage) = 看板/会话框共用入口：从全流程一览取该节点、
 * 推导行状态（done/current/pending/skipped）后调 renderStagePanel。
 *
 * @module dsh-pmboard/client/stage-panel
 */
import {
  type StageDetail,
  type StageOverview,
  type StageKey,
  type StageArtifact,
  type StageTaskExecution,
  type ArtifactKind,
  type StatusEvent,
  STAGE_ARTIFACT_REQUIREMENTS,
  CATEGORY_FLOW_PROFILES,
  stageEnabledFor,
  windowCodeFromSessionId,
  ALL_STAGE_KEYS,
} from '../shared/protocol.js'
import { esc } from '@pi-investment/page-kit/client'

// ---------------------------------------------------------------------------
// 常量
// ---------------------------------------------------------------------------

/** 节点中文标签（与 conversation-progress FLOW 一致）。 */
export const STAGE_LABELS: Record<StageKey, string> = {
  draft: '立项',
  brainstorming: '需求分析',
  planning: '技术设计',
  decomposing: '拆分',
  implementing: '实施',
  accepting: '验收',
  // REQ-9f4a44：done 不再是流水线节点（StageKey 已移除）
  archived: '归档',
}

/** 产物种类中文标签。 */
const ARTIFACT_KIND_LABELS: Record<ArtifactKind, string> = {
  requirement: '需求文档',
  plan: '实施计划',
  decomposition: '拆分方案',
  task_detail: '任务卡',
  verification: '验收材料',
  archive: '归档材料',
}

/** 追溯链顺序（requirement → plan → decomposition → task_detail → verification → archive）。 */
const TRACE_CHAIN_ORDER: ArtifactKind[] = [
  'requirement',
  'plan',
  'decomposition',
  'task_detail',
  'verification',
  'archive',
]

/** 任务状态中文标签。 */
const TASK_STATUS_LABELS: Record<string, string> = {
  todo: '待开始',
  in_progress: '开发中',
  integrating: '联调中',
  testing: '测试中',
  in_review: '待评审',
  done: '已完成',
  canceled: '已取消',
}

/** 任务状态字形（纯文字监控，不用图标库）。 */
const TASK_STATUS_GLYPH: Record<string, string> = {
  todo: '○',
  in_progress: '◐',
  integrating: '◐',
  testing: '◐',
  in_review: '◐',
  done: '✓',
  canceled: '✕',
}

/** 节点行状态。 */
export type StageRowState = 'done' | 'current' | 'pending' | 'skipped'

const ROW_STATE_GLYPH: Record<StageRowState, string> = {
  done: '✓', current: '●', pending: '○', skipped: '—',
}

// ---------------------------------------------------------------------------
// 内部工具
// ---------------------------------------------------------------------------

/** 毫秒 → YYYY-MM-DD HH:mm。 */
function fmtTime(ms: number): string {
  const d = new Date(ms)
  const pad = (n: number) => String(n).padStart(2, '0')
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
}

/** 毫秒 → 相对时间（监控视角：刚刚 / N 分钟前 / N 小时前 / 昨天 HH:mm / MM-DD）。 */
function fmtRel(ms: number, now: number = Date.now()): string {
  const diff = now - ms
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前'
  const d = new Date(ms)
  const pad = (n: number) => String(n).padStart(2, '0')
  if (diff < 2 * 86400000) return '昨天 ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
  return pad(d.getMonth() + 1) + '-' + pad(d.getDate())
}

/** 截断（防长文本挤爆布局）。 */
function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + '…' : s
}

/** 操作者 → 短标识：人 / 系统 / w-xxx（窗口）/ sub w-xxx（subagent）。 */
function actorShort(by: { kind?: string; sessionId?: string } | undefined): string {
  if (by === undefined) return ''
  if (by.kind === 'human') return '人'
  if (by.kind === 'system') return '系统'
  const sid = by.sessionId
  if (typeof sid !== 'string' || sid.length === 0) return 'Agent'
  if (sid.startsWith('session-')) return windowCodeFromSessionId(sid)
  return 'sub ' + windowCodeFromSessionId(sid)
}

/** 任务的执行者短标识（最近一次执行会话，退到认领人）。 */
function executorOf(t: StageTaskExecution): string {
  const execs = t.executions ?? []
  const sid = execs.length > 0 ? execs[execs.length - 1].sessionId : t.claimedBy
  return actorShort(sid !== undefined ? { kind: 'agent', sessionId: sid } : undefined)
}

/** 任务的执行时间描述（完成时间 / 进行中起点 / 失败次数）。 */
function taskTimeText(t: StageTaskExecution): { text: string; failed: boolean } {
  const execs = t.executions ?? []
  const failedCount = execs.filter(e => e.outcome === 'failed').length
  if (t.status === 'done') {
    const ok = [...execs].reverse().find(e => e.outcome === 'succeeded' && e.endedAt !== undefined)
    const base = ok?.endedAt !== undefined ? fmtTime(ok.endedAt) : ''
    return { text: (base.length > 0 ? base + ' ' : '') + '完成', failed: false }
  }
  if (t.status === 'in_progress' || t.status === 'integrating' || t.status === 'testing') {
    const running = [...execs].reverse().find(e => e.outcome === 'running')
    const since = running !== undefined ? '（' + fmtRel(running.startedAt) + '开始）' : ''
    const failNote = failedCount > 0 ? ' · 失败 ' + failedCount + ' 次' : ''
    return { text: (TASK_STATUS_LABELS[t.status] ?? t.status) + since + failNote, failed: failedCount > 0 }
  }
  if (failedCount > 0) return { text: '失败 ' + failedCount + ' 次', failed: true }
  return { text: TASK_STATUS_LABELS[t.status] ?? t.status, failed: false }
}

// ---------------------------------------------------------------------------
// 各节点专属内容（template method 的变体部分）
// ---------------------------------------------------------------------------

type StageBodyRenderer = (payload: StageDetail) => string

const renderDraftBody: StageBodyRenderer = (payload) => {
  const body = (payload as Extract<StageDetail, { stage: 'draft' }>).body
  const meta = [
    body.sourceWindow ? '来源窗口 ' + body.sourceWindow : '',
    body.createdAt ? fmtTime(body.createdAt) : '',
  ].filter(s => s.length > 0).join(' · ')
  return (
    '<div class="dsh-pm-sn-body" data-stage="draft">' +
      '<div class="dsh-pm-sn-req-title">' + esc(body.title) + (body.category ? ' <span class="dsh-pm-sn-dim">（' + esc(body.category) + '）</span>' : '') + '</div>' +
      (body.description ? '<div class="dsh-pm-sn-text">' + esc(body.description) + '</div>' : '<div class="dsh-pm-sn-empty">暂无描述</div>') +
      (meta.length > 0 ? '<div class="dsh-pm-sn-dim">' + esc(meta) + '</div>' : '') +
    '</div>'
  )
}

const renderBrainstormBody: StageBodyRenderer = (payload) => {
  const body = (payload as Extract<StageDetail, { stage: 'brainstorming' }>).body
  const comments = body.comments ?? []
  if (comments.length === 0) {
    return '<div class="dsh-pm-sn-body" data-stage="brainstorming"><div class="dsh-pm-sn-empty">暂无评论</div></div>'
  }
  const rows = comments.map(c => {
    const who = actorShort(c.createdBy)
    const kind = c.createdBy?.kind ?? 'agent'
    return (
      '<div class="dsh-pm-sn-comment">' +
        '<div class="dsh-pm-sn-comment-who" data-actor="' + esc(kind) + '">' + esc(who) + '</div>' +
        '<div class="dsh-pm-sn-comment-text">' + esc(c.body) + '</div>' +
      '</div>'
    )
  }).join('')
  return '<div class="dsh-pm-sn-body" data-stage="brainstorming">' + rows + '</div>'
}

const renderPlanningBody: StageBodyRenderer = (payload) => {
  const body = (payload as Extract<StageDetail, { stage: 'planning' }>).body
  if (!body.plan) {
    return '<div class="dsh-pm-sn-body" data-stage="planning"><div class="dsh-pm-sn-empty">尚未提交实施计划</div></div>'
  }
  const plan = body.plan
  const statusLine = plan.approvedAt !== undefined
    ? '批准：' + (plan.approvedBy?.kind === 'human' ? '人' : 'Agent') + ' · ' + fmtTime(plan.approvedAt)
    : plan.rejectedAt !== undefined
      ? '退回：' + fmtTime(plan.rejectedAt) + (plan.rejectedReason ? ' · ' + plan.rejectedReason : '')
      : '提交：' + fmtTime(plan.submittedAt) + ' · 待批准'
  return (
    '<div class="dsh-pm-sn-body" data-stage="planning">' +
      (plan.summary ? '<div class="dsh-pm-sn-text">' + esc(plan.summary) + '</div>' : '') +
      '<div class="dsh-pm-sn-dim">' + plan.tasks.length + ' 个任务 · ' + esc(statusLine) + '</div>' +
    '</div>'
  )
}

/** 拓扑分层：按依赖深度分组（DAG 层级）。 */
function topoLevels<T extends { id: string; dependsOn?: string[] }>(tasks: T[]): Map<number, T[]> {
  const byId = new Map(tasks.map(t => [t.id, t]))
  const cache = new Map<string, number>()
  function lv(id: string): number {
    if (cache.has(id)) return cache.get(id)!
    const t = byId.get(id)
    if (!t || !t.dependsOn || t.dependsOn.length === 0) { cache.set(id, 0); return 0 }
    const l = 1 + Math.max(...t.dependsOn.map(d => lv(d)))
    cache.set(id, l)
    return l
  }
  for (const t of tasks) lv(t.id)
  const layers = new Map<number, T[]>()
  for (const t of tasks) {
    const l = cache.get(t.id) ?? 0
    if (!layers.has(l)) layers.set(l, [])
    layers.get(l)!.push(t)
  }
  return layers
}

const renderDecomposingBody: StageBodyRenderer = (payload) => {
  const body = (payload as Extract<StageDetail, { stage: 'decomposing' }>).body
  const tasks = body.tasks ?? []
  if (tasks.length === 0) {
    return '<div class="dsh-pm-sn-body" data-stage="decomposing"><div class="dsh-pm-sn-empty">尚未拆分任务</div></div>'
  }
  const layers = topoLevels(tasks)
  const sections: string[] = []
  for (const [lv, layerTasks] of [...layers.entries()].sort((a, b) => a[0] - b[0])) {
    const label = lv === 0
      ? '第 1 层 · 无依赖'
      : '第 ' + (lv + 1) + ' 层' + (layerTasks.length > 1 ? ' · ' + layerTasks.length + ' 个可并行' : '')
    const rows = layerTasks.map(t =>
      '<div class="dsh-pm-sn-dag-task">' +
        '<span class="dsh-pm-sn-task-id">' + esc(t.id) + '</span>' +
        '<span class="dsh-pm-sn-text">' + esc(t.title) + '</span>' +
      '</div>'
    ).join('')
    sections.push(
      '<div class="dsh-pm-sn-dag-layer">' +
        '<div class="dsh-pm-sn-dag-label">' + esc(label) + '</div>' +
        rows +
      '</div>'
    )
  }
  return '<div class="dsh-pm-sn-body" data-stage="decomposing">' + sections.join('') + '</div>'
}

const renderImplementingBody: StageBodyRenderer = (payload) => {
  const body = (payload as Extract<StageDetail, { stage: 'implementing' }>).body
  const tasks = body.tasks ?? []
  if (tasks.length === 0) {
    return '<div class="dsh-pm-sn-body" data-stage="implementing"><div class="dsh-pm-sn-empty">暂无执行任务</div></div>'
  }
  // 按状态分组：进行中 → 已完成 → 待开始（监控视角：当前最优先）
  const active = tasks.filter(t => t.status === 'in_progress' || t.status === 'integrating' || t.status === 'testing')
  const done = tasks.filter(t => t.status === 'done')
  const pending = tasks.filter(t => t.status === 'todo' || t.status === 'in_review')

  const renderTask = (t: StageTaskExecution) => {
    const glyph = TASK_STATUS_GLYPH[t.status] ?? '○'
    const executor = executorOf(t)
    const time = taskTimeText(t)
    const isActive = active.includes(t)
    const cls = (isActive ? ' is-current' : '') + (time.failed ? ' is-failed' : '')
    const meta = [t.id, executor, time.text].filter(s => s.length > 0).join(' · ')
    const docBtn = t.cardDoc
      ? ' · <button type="button" class="dsh-pm-sn-doc" data-action="open-doc" data-path="' + esc(t.cardDoc) + '">任务卡</button>'
      : ''
    return (
      '<div class="dsh-pm-sn-task' + cls + '" data-status="' + esc(t.status) + '">' +
        '<div class="dsh-pm-sn-task-line1">' +
          '<span class="dsh-pm-sn-task-glyph">' + glyph + '</span>' +
          '<span class="dsh-pm-sn-task-title">' + esc(t.title) + '</span>' +
        '</div>' +
        '<div class="dsh-pm-sn-task-line2">' + esc(meta) + docBtn + '</div>' +
      '</div>'
    )
  }

  const sections: string[] = []
  if (active.length > 0) {
    sections.push(
      '<div class="dsh-pm-sn-group">' +
        '<div class="dsh-pm-sn-group-label is-active">进行中 ' + active.length + ' 个</div>' +
        active.map(renderTask).join('') +
      '</div>'
    )
  }
  if (done.length > 0) {
    sections.push(
      '<div class="dsh-pm-sn-group">' +
        '<div class="dsh-pm-sn-group-label">已完成 ' + done.length + ' 个</div>' +
        done.map(renderTask).join('') +
      '</div>'
    )
  }
  if (pending.length > 0) {
    sections.push(
      '<div class="dsh-pm-sn-group">' +
        '<div class="dsh-pm-sn-group-label">待开始 ' + pending.length + ' 个</div>' +
        pending.map(renderTask).join('') +
      '</div>'
    )
  }

  const windows = Object.entries(body.byWindow ?? {})
  const windowLine = windows.length > 1
    ? '<div class="dsh-pm-sn-dim">窗口分工：' + windows.map(([w, ids]) => esc(w) + ' ' + ids.length + ' 任务').join(' · ') + '</div>'
    : ''
  return (
    '<div class="dsh-pm-sn-body" data-stage="implementing">' +
      sections.join('') +
      windowLine +
    '</div>'
  )
}

/**
 * 验收单逐项渲染（REQ-2e9473 t14/W6）：每项 通过/不通过 单选 + 意见输入 +
 * 提交裁决按钮（data-action=submit-verdicts，由 board-mount 事件委派收集提交）。
 */
function renderVerificationSheet(
  payload: StageDetail,
  v: { sheet?: { version: number; items: { id: string; source: string; criterion: string; status: string; opinion?: string }[]; reworkOnly?: boolean } },
): string {
  const sheet = v.sheet
  if (sheet === undefined || sheet.items.length === 0) return ''
  const reqId = (payload as { requirementId?: string }).requirementId ?? ''
  const badge: Record<string, string> = { pending: '⬜ 待验', passed: '✅ 通过', failed: '❌ 不通过' }
  const rows = sheet.items.map((it) => {
    const decided = it.status !== 'pending'
    return '<div class="dsh-pm-vitem" data-item-id="' + esc(it.id) + '" data-source="' + esc(it.source) + '">' +
      '<div class="dsh-pm-vitem-head">' +
        '<span class="dsh-pm-vitem-badge">' + (badge[it.status] ?? esc(it.status)) + '</span>' +
        '<span class="dsh-pm-vitem-src">' + esc(it.source === 'requirement' ? '需求级' : it.source) + '</span>' +
      '</div>' +
      '<div class="dsh-pm-sn-text">' + esc(truncate(it.criterion, 200)) + '</div>' +
      (decided
        ? (it.opinion ? '<div class="dsh-pm-sn-warn">意见：' + esc(truncate(it.opinion, 200)) + '</div>' : '')
        : '<div class="dsh-pm-vitem-actions">' +
            '<label><input type="radio" name="verdict-' + esc(it.id) + '" value="passed"> 通过</label>' +
            '<label><input type="radio" name="verdict-' + esc(it.id) + '" value="failed"> 不通过</label>' +
            '<input type="text" class="dsh-pm-vitem-opinion" placeholder="不通过时填意见（必填）">' +
          '</div>') +
    '</div>'
  }).join('')
  const allDecided = sheet.items.every(i => i.status !== 'pending')
  return '<div class="dsh-pm-vsheet" data-req="' + esc(reqId) + '" data-version="' + sheet.version + '">' +
    '<div class="dsh-pm-sn-label">验收单 v' + sheet.version + (sheet.reworkOnly === true ? '（返工续验：只含未过项）' : '') +
      ' · 共 ' + sheet.items.length + ' 项</div>' +
    rows +
    (allDecided
      ? '<div class="dsh-pm-sn-dim">本轮已裁决完毕：全部通过请点上方「验收通过」归档；有未过项已自动打回返工。</div>'
      : '<button type="button" class="dsh-pm-btn sm primary" data-action="submit-verdicts" data-req="' + esc(reqId) +
        '" data-version="' + sheet.version + '">提交裁决</button>') +
  '</div>'
}

const renderAcceptingBody: StageBodyRenderer = (payload) => {
  const body = (payload as Extract<StageDetail, { stage: 'accepting' }>).body
  if (!body.verification) {
    return '<div class="dsh-pm-sn-body" data-stage="accepting"><div class="dsh-pm-sn-empty">尚未提交验收材料</div></div>'
  }
  const v = body.verification
  const sheetHtml = renderVerificationSheet(payload, v)
  const evidence = (v.evidence ?? []).slice(0, 5)
  const evidenceRows = evidence.map(e => '<div class="dsh-pm-sn-line"><span class="dsh-pm-sn-text">- ' + esc(truncate(e, 140)) + '</span></div>').join('')
  return (
    '<div class="dsh-pm-sn-body" data-stage="accepting">' +
      (v.summary ? '<div class="dsh-pm-sn-text">' + esc(v.summary) + '</div>' : '') +
      sheetHtml +
      (evidence.length > 0 ? '<div class="dsh-pm-sn-label">证据（' + (v.evidence ?? []).length + ' 条）</div>' + evidenceRows : '') +
      (v.reviewNote ? '<div class="dsh-pm-sn-warn">审核意见：' + esc(truncate(v.reviewNote, 200)) + '</div>' : '') +
    '</div>'
  )
}

const renderDoneBody: StageBodyRenderer = (payload) => {
  const body = (payload as Extract<StageDetail, { stage: 'done' }>).body
  const lines = [
    body.completedAt ? '完成于 ' + fmtTime(body.completedAt) : '',
    body.verificationDecision ? '验收结论：' + (body.verificationDecision === 'pass' ? '通过' : '返工') : '',
  ].filter(s => s.length > 0)
  if (lines.length === 0) return '<div class="dsh-pm-sn-body" data-stage="done"><div class="dsh-pm-sn-empty">—</div></div>'
  return '<div class="dsh-pm-sn-body" data-stage="done">' + lines.map(l => '<div class="dsh-pm-sn-text">' + esc(l) + '</div>').join('') + '</div>'
}

const renderArchivedBody: StageBodyRenderer = (payload) => {
  const body = (payload as Extract<StageDetail, { stage: 'archived' }>).body
  if (!body.archive) {
    return '<div class="dsh-pm-sn-body" data-stage="archived"><div class="dsh-pm-sn-empty">暂无归档材料</div></div>'
  }
  const a = body.archive
  const merged = (a.mergedInto?.length ?? 0) > 0
    ? '<div class="dsh-pm-sn-dim">合并去向：' + (a.mergedInto ?? []).map(p => '<button type="button" class="dsh-pm-sn-doc" data-action="open-doc" data-path="' + esc(p) + '">' + esc(p) + '</button>').join(' · ') + '</div>'
    : ''
  return (
    '<div class="dsh-pm-sn-body" data-stage="archived">' +
      '<div class="dsh-pm-sn-text">归档目录：' + esc(a.dir) + '</div>' +
      (a.indexEntry ? '<div class="dsh-pm-sn-text">' + esc(a.indexEntry) + '</div>' : '') +
      merged +
    '</div>'
  )
}

// ---------------------------------------------------------------------------
// StageRenderers 注册表（template method 的变体部分）
// ---------------------------------------------------------------------------

export const StageRenderers: Record<StageKey, { renderBody: StageBodyRenderer }> = {
  draft: { renderBody: renderDraftBody },
  brainstorming: { renderBody: renderBrainstormBody },
  planning: { renderBody: renderPlanningBody },
  decomposing: { renderBody: renderDecomposingBody },
  implementing: { renderBody: renderImplementingBody },
  accepting: { renderBody: renderAcceptingBody },
  // REQ-9f4a44：done 不再是流水线节点，无对应渲染器
  archived: { renderBody: renderArchivedBody },
}

// ---------------------------------------------------------------------------
// 固定区块：产物文档行 / 动态 / 追溯链
// ---------------------------------------------------------------------------



/** 动态：谁/何时/做了什么（最近 5 条，相对时间）。 */
function renderEvents(timeline: StatusEvent[]): string {
  if (timeline.length === 0) return ''
  const rows = timeline.slice(-5).reverse().map(ev => {
    const actor = actorShort(ev.by)
    const reason = ev.reason !== undefined && ev.reason.length > 0 ? ev.reason : (STAGE_LABELS[ev.status as StageKey] ?? ev.status)
    const inferred = ev.inferred === true ? ' <span class="dsh-pm-sn-dim">(回填)</span>' : ''
    const whoLine = [actor, fmtRel(ev.at)].filter(s => s.length > 0).join(' · ')
    return (
      '<div class="dsh-pm-sn-comment">' +
        '<div class="dsh-pm-sn-comment-who">' + esc(whoLine) + inferred + '</div>' +
        '<div class="dsh-pm-sn-comment-text">' + esc(reason) + '</div>' +
      '</div>'
    )
  }).join('')
  return '<div class="dsh-pm-sn-label">动态</div>' + rows
}

/** 产物追溯链一行（requirement → plan → … → archive），含缺失标记（红字）。 */
function renderTraceChain(payload: StageDetail): string {
  const artifacts = payload.artifacts ?? []
  const required = STAGE_ARTIFACT_REQUIREMENTS[payload.stage] ?? []
  if (artifacts.length === 0 && required.length === 0) return ''

  const byKind = new Map<ArtifactKind, StageArtifact[]>()
  for (const a of artifacts) {
    const list = byKind.get(a.kind) ?? []
    list.push(a)
    byKind.set(a.kind, list)
  }

  const chainItems: string[] = []
  for (const kind of TRACE_CHAIN_ORDER) {
    const list = byKind.get(kind)
    if (!list || list.length === 0) continue
    const kindLabel = ARTIFACT_KIND_LABELS[kind] ?? kind
    if (kind === 'task_detail') {
      // 任务卡汇总显示（逐个列太长，且任务列表里已有链接）
      chainItems.push(
        '<span class="dsh-pm-trace-node" data-kind="' + esc(kind) + '">' +
          '<span class="dsh-pm-sn-dim">' + esc(kindLabel) + '×' + list.length + '</span>' +
        '</span>'
      )
      continue
    }
    for (const artifact of list) {
      chainItems.push(
        '<span class="dsh-pm-trace-node" data-kind="' + esc(kind) + '">' +
          '<button type="button" class="dsh-pm-sn-doc dsh-pm-trace-path" data-action="open-doc" data-path="' + esc(artifact.path) + '">' + esc(kindLabel) + '</button>' +
        '</span>'
      )
    }
  }

  // 缺失必备产物（红字追加在链尾）
  const registeredKinds = new Set(artifacts.map(a => a.kind))
  for (const kind of required) {
    if (!registeredKinds.has(kind)) {
      const kindLabel = ARTIFACT_KIND_LABELS[kind] ?? kind
      chainItems.push('<span class="dsh-pm-trace-node is-missing" data-kind="' + esc(kind) + '">' +
        '<span class="dsh-pm-sn-doc is-missing">' + esc(kindLabel) + '（缺失）</span></span>')
    }
  }

  if (chainItems.length === 0) return ''

  return (
    '<div class="dsh-pm-trace-chain">' +
      chainItems.join('<span class="dsh-pm-trace-arrow">→</span>') +
    '</div>'
  )
}

// ---------------------------------------------------------------------------
// 面板头状态一句话
// ---------------------------------------------------------------------------

/** 面板头：这一步干了什么 / 进行到什么程度（一句话）。 */
export function stageHeadSummary(payload: StageDetail): string {
  if (!payload.enabled) return '本分类跳过'
  switch (payload.stage) {
    case 'draft': return '已立项'
    case 'brainstorming': {
      const b = (payload as Extract<StageDetail, { stage: 'brainstorming' }>).body
      const n = b.comments?.length ?? 0
      return n > 0 ? n + ' 条评论' : '需求分析'
    }
    case 'planning': {
      const b = (payload as Extract<StageDetail, { stage: 'planning' }>).body
      if (!b.plan) return '待提交计划'
      if (b.plan.approvedAt !== undefined) return '计划已批准'
      if (b.plan.rejectedAt !== undefined) return '计划被退回'
      return '计划待批准'
    }
    case 'decomposing': {
      const b = (payload as Extract<StageDetail, { stage: 'decomposing' }>).body
      const n = b.tasks?.length ?? 0
      return n > 0 ? n + ' 个任务' : '待拆分'
    }
    case 'implementing': {
      const b = (payload as Extract<StageDetail, { stage: 'implementing' }>).body
      const tasks = b.tasks ?? []
      const total = tasks.length
      if (total === 0) return '暂无任务'
      const done = tasks.filter(t => t.status === 'done').length
      const active = tasks.find(t => t.status === 'in_progress' || t.status === 'integrating' || t.status === 'testing')
      let s = done + '/' + total + ' 完成'
      if (total - done > 0) s += ' · 剩 ' + (total - done) + ' 个'
      if (active !== undefined) s += ' · 进行中 ' + active.id
      return s
    }
    case 'accepting': {
      const b = (payload as Extract<StageDetail, { stage: 'accepting' }>).body
      if (!b.verification) return '待提交验收材料'
      if (b.verification.decision === 'pass') return '验收通过'
      if (b.verification.decision === 'rework') return '验收被退回返工'
      return '待人工审核'
    }
    // REQ-9f4a44：done 节点已移除
    case 'archived': return '已归档'
  }
}

// ---------------------------------------------------------------------------
// renderStagePanel —— 固定骨架（template method 的固定部分）
// ---------------------------------------------------------------------------

export interface StagePanelOptions {
  /** 节点行状态（done/current/pending/skipped）；renderStageNode 推导后传入，默认 current。 */
  state?: StageRowState
}

/**
 * 渲染单节点详情面板（纯字符串，供 innerHTML 使用）。
 * 骨架：面板头（状态一句话+时间）→ 追溯链（置顶）→ 待确认警示 → 节点专属内容 → 产物文档行 → 动态。
 */
export function renderStagePanel(payload: StageDetail, opts: StagePanelOptions = {}): string {
  const label = STAGE_LABELS[payload.stage] ?? payload.stage
  const state: StageRowState = payload.enabled ? (opts.state ?? 'current') : 'skipped'
  const glyph = ROW_STATE_GLYPH[state]
  const summary = stageHeadSummary(payload)
  const latestAt = payload.timeline.length > 0 ? payload.timeline[payload.timeline.length - 1].at : undefined

  const warn = payload.pendingConfirmation
    ? '<div class="dsh-pm-sn-warn">⚠ 有产物待人工确认</div>'
    : ''

  const renderer = StageRenderers[payload.stage]
  const bodyHtml = payload.enabled
    ? (renderer ? renderer.renderBody(payload) : '<div class="dsh-pm-sn-empty">未知阶段</div>')
    : '<div class="dsh-pm-sn-body" data-stage="' + esc(payload.stage) + '"><div class="dsh-pm-sn-empty">该阶段在当前分类流程中不适用</div></div>'

  return (
    '<div class="dsh-pm-stage-panel dsh-pm-sn" data-stage="' + esc(payload.stage) + '" data-state="' + state + '">' +
      '<div class="dsh-pm-sn-head">' +
        '<span class="dsh-pm-sn-title">' + esc(summary) + '</span>' +
        (latestAt !== undefined ? '<span class="dsh-pm-sn-time">' + esc(fmtRel(latestAt)) + '</span>' : '') +
      '</div>' +
      renderTraceChain(payload) +
      warn +
      bodyHtml +
      renderEvents(payload.timeline) +
    '</div>'
  )
}

// ---------------------------------------------------------------------------
// renderStageNode —— 看板/会话框共用入口（从全流程一览渲染单个节点）
// ---------------------------------------------------------------------------

/** 推导节点行状态：skipped（分类跳过）/ done / current / pending。 */
export function stageRowState(ov: StageOverview, stage: StageKey): StageRowState {
  const payload = ov.stages.find(s => s.stage === stage)
  if (payload === undefined || !payload.enabled) return 'skipped'
  const curIdx = ALL_STAGE_KEYS.indexOf(ov.currentStage as StageKey)
  const idx = ALL_STAGE_KEYS.indexOf(stage)
  if (curIdx >= 0 && idx < curIdx) return 'done'
  if (idx === curIdx) return 'current'
  return 'pending'
}

/** 从全流程一览渲染指定节点的详情面板（点哪个看哪个；stage 不存在时回退第一个节点）。 */
export function renderStageNode(ov: StageOverview, stage: StageKey): string {
  const payload = ov.stages.find(s => s.stage === stage) ?? ov.stages[0]
  if (payload === undefined) return '<div class="dsh-pm-sn-empty">未知节点</div>'
  return renderStagePanel(payload, { state: stageRowState(ov, payload.stage) })
}

// ---------------------------------------------------------------------------
// 分类流程辅助
// ---------------------------------------------------------------------------

/**
 * 判断某分类流程是否跳过指定阶段。
 * 用于 conversation-progress 的流程图节点灰显。
 */
export function isStageSkippedForCategory(category: string | undefined, stage: StageKey): boolean {
  if (!category) return false
  return !stageEnabledFor(category as any, stage)
}

/** 获取分类流程的启用阶段列表。 */
export function getStagesForCategory(category: string | undefined): readonly StageKey[] {
  if (!category) return ALL_STAGE_KEYS
  const profile = CATEGORY_FLOW_PROFILES[category as keyof typeof CATEGORY_FLOW_PROFILES]
  return profile ? profile.stages : ALL_STAGE_KEYS
}
