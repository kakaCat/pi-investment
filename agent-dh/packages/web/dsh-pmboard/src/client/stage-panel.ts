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
  type MainStageKey,
  type StatusEvent,
  STAGE_ARTIFACT_REQUIREMENTS,
  CATEGORY_FLOW_PROFILES,
  stageEnabledFor,
  windowCodeFromSessionId,
  ALL_STAGE_KEYS,
} from '../shared/protocol.js'
import { ITEM_STATUS_BADGE } from '../shared/protocol.js'
import { esc } from './html.js'
import { displayDocPath } from './open-doc.ts'
import { CATEGORY_DELTAS, COMMON_ROOT_SECTIONS } from '../application/internal/category-doc-sets.js'
import { fmt } from '../domain/text/fmt.js'
import { artifactKindLabel, docFileLabel, taskCardLabel } from '../shared/artifact-labels.js'
import type { StageTaskRef } from '../shared/protocol.js'

// ---------------------------------------------------------------------------
// 常量
// ---------------------------------------------------------------------------

/** 节点中文标签（与 conversation-progress FLOW 一致）。键域=7 个主节点（legacy done 无标签）。 */
export const STAGE_LABELS: Record<MainStageKey, string> = {
  draft: '立项',
  brainstorming: '需求分析',
  design: '设计',
  decomposing: '拆分',
  implementing: '实施',
  accepting: '验收',
  // REQ-9f4a44：done 不再是流水线节点（legacy 兼容，不在 MainStageKey 里）
  archived: '归档',
}

// REQ-260922182638-0777：产物种类/文件名中文名唯一事实源 = shared/artifact-labels.ts
// （本文件不再建本地映射表；未知值由共享函数中文兜底，不写 ?? kind）
/**
 * 「同类多份」产物种类：同一个节点下会有**多条同 kind 的产物记录**，每条是一份独立文档。
 *
 * 目前只有 design——设计节点的交付物是**一整套**文档（architecture.md / data-model.md /
 * interfaces.md / test-cases.md…），同一 kind 下会有多条产物。其余种类一份需求只有一份。
 * 为什么需要这张表：追溯链按 kind 取显示名，同类多份时全部渲染成同一个词
 * （设计节点上四份文档全叫「设计文档」），人根本分不出谁是谁——2026-09-21 用户反馈。
 */
const MULTI_DOC_KINDS: ReadonlySet<ArtifactKind> = new Set<ArtifactKind>(['design'])

/**
 * 追溯链上的产物显示名。
 *
 * - 单份产物（requirement / plan / decomposition / verification / archive）→ 种类中文名
 *   （人认的是「这一步交了没」）；
 * - 同类多份（design）→ **中文文档名**（架构文档 / 接口文档…，REQ-260922182638-0777 FR-4：
 *   不再裸显 architecture.md 等英文文件名；完整路径仍在 tooltip，排查线索不丢）。
 *   未知文件名由 docFileLabel 中文兜底（「设计文档（foo.md）」）。
 */
function traceNodeLabel(kind: ArtifactKind, path: string): string {
  if (!MULTI_DOC_KINDS.has(kind)) return artifactKindLabel(kind)
  return docFileLabel(path, kind)
}

/** 路径归一（去前导 ./）：artifact.path 与 StageTaskRef.cardDoc 精确匹配前的对齐。 */
function normDocPath(p: string): string {
  return (p ?? '').replace(/^\.\//, '')
}

/**
 * 从节点 payload 的任务清单建 cardDoc → 任务名称 映射（decompose/implement 节点体均有 tasks）。
 * 用于追溯链任务卡逐张展开时取任务名（FR-5）；payload 无任务清单时返回空映射（降级编号形态）。
 */
function taskTitleByCardDoc(payload: StageDetail): Map<string, string> {
  const map = new Map<string, string>()
  const tasks = (payload.body as { tasks?: StageTaskRef[] } | undefined)?.tasks
  if (!Array.isArray(tasks)) return map
  for (const t of tasks) {
    if (typeof t?.cardDoc === 'string' && t.cardDoc.length > 0 && typeof t?.title === 'string' && t.title.length > 0) {
      map.set(normDocPath(t.cardDoc), t.title)
    }
  }
  return map
}

/** 追溯链顺序（requirement → design → plan → decomposition → task_detail → verification → archive）。 */
const TRACE_CHAIN_ORDER: ArtifactKind[] = [
  'requirement',
  'design',
  'plan',
  'decomposition',
  'task_detail',
  'verification',
  'archive',
]

/** 任务状态中文标签（2026-09-21 用户裁定：in_review=待复核，与需求级「验收」区分）。 */
const TASK_STATUS_LABELS: Record<string, string> = {
  todo: '待开始',
  in_progress: '开发中',
  integrating: '联调中',
  testing: '测试中',
  in_review: '待复核',
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

const renderDesignBody: StageBodyRenderer = (payload) => {
  const body = (payload as Extract<StageDetail, { stage: 'design' }>).body
  
  // 文档集要求展示（系统负责格式）
  let docSetHtml = ''
  if (body.category) {
    const delta = CATEGORY_DELTAS.find(d => d.category === body.category)
    if (delta) {
      const rootSections = [...COMMON_ROOT_SECTIONS, ...delta.rootSectionsDelta]
      const required = delta.requiredDesignDocs

      const rootList = rootSections.length > 0
        ? fmt('<div class="dsh-pm-sn-dim">根文档必填节：{sections}</div>', { sections: esc(rootSections.join('、')) })
        : ''

      // 设计文档逐份交付状态（REQ-81aabd FR-2）：已交 ✅ / 未交 ⬜，比对需求目录里的实际登记
      // （body.designDocs 由服务端设计节点装配器给出）。字段缺席时退回模板文件名清单。
      // REQ-2d1c74 FR-1/FR-2：条件必交带「条件·端侧」徽标；豁免项灰显并展示理由
      // （与 G2 完整性闸门共用同一份策略，页面上看到的缺口 = G2 拦截清单）。
      const designList = body.designDocs !== undefined
        ? (body.designDocs.length > 0
            ? body.designDocs.map(d => {
                if (d.exempted !== undefined) {
                  return fmt(
                    '<div class="dsh-pm-sn-dim" data-design-doc="{name}" data-exempted="yes" style="opacity:.55">🚫 design/{name}（已豁免：{reason}）</div>',
                    { name: esc(d.name), reason: esc(d.exempted) },
                  )
                }
                const badge = d.conditional !== undefined
                  ? fmt(' <span style="opacity:.75">〔条件·{side}〕</span>', { side: esc(d.conditional) })
                  : ''
                return fmt(
                  '<div class="dsh-pm-sn-dim" data-design-doc="{name}" data-submitted="{sub}">{mark} design/{name}{badge}</div>',
                  { name: esc(d.name), sub: d.submitted ? 'yes' : 'no', mark: d.submitted ? '✅ 已交' : '⬜ 未交', badge },
                )
              }).join('')
            : '<div class="dsh-pm-sn-dim">设计文档：无（本类型跳过设计文档）</div>')
        : (required.length > 0
            ? fmt('<div class="dsh-pm-sn-dim">设计文档：{list}</div>', { list: esc(required.map(d => 'design/' + d).join('、')) })
            : '<div class="dsh-pm-sn-dim">设计文档：无（本类型跳过设计文档）</div>')
      
      docSetHtml = (
        '<div class="dsh-pm-sn-docset">' +
          '<div class="dsh-pm-sn-text" style="font-weight: 500;">📋 本类型需要的文档</div>' +
          rootList +
          designList +
        '</div>'
      )
    }
  }
  
  if (!body.plan) {
    return '<div class="dsh-pm-sn-body" data-stage="design">' + docSetHtml + '<div class="dsh-pm-sn-empty">设计阶段只写设计文档（拆分计划在拆分阶段提交）</div></div>'
  }
  const plan = body.plan
  const statusLine = plan.approvedAt !== undefined
    ? '批准：' + (plan.approvedBy?.kind === 'human' ? '人' : 'Agent') + ' · ' + fmtTime(plan.approvedAt)
    : plan.rejectedAt !== undefined
      ? '退回：' + fmtTime(plan.rejectedAt) + (plan.rejectedReason ? ' · ' + plan.rejectedReason : '')
      : '提交：' + fmtTime(plan.submittedAt) + ' · 待批准'
  return (
    '<div class="dsh-pm-sn-body" data-stage="design">' +
      docSetHtml +
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
    return '<div class="dsh-pm-sn-body" data-stage="decomposing"><div class="dsh-pm-sn-empty">尚未提交拆分计划（提交并获批准后自动拆分任务）</div></div>'
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
      ? ' · <button type="button" class="dsh-pm-sn-doc" data-action="open-doc" data-path="' + esc(t.cardDoc) + '" title="' + esc(displayDocPath(t.cardDoc)) + '">任务卡</button>'
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
  v: { sheet?: { version: number; items: { id: string; source: { kind: 'requirement' } | { kind: 'task'; taskId: string }; criterion: string; status: string; opinion?: string }[]; reworkOnly?: boolean } },
): string {
  const sheet = v.sheet
  if (sheet === undefined || sheet.items.length === 0) return ''
  const reqId = (payload as { requirementId?: string }).requirementId ?? ''
  // 文案单点（REQ-47939a 返工）：与 host 判定用的 ACCEPT_ITEM_OPTIONS 同源，避免两处漂移
  const badge: Record<string, string> = { ...ITEM_STATUS_BADGE }
  const rows = sheet.items.map((it) => {
    const decided = it.status !== 'pending'
    const sourceKey = it.source.kind === 'requirement' ? 'requirement' : it.source.taskId
    return '<div class="dsh-pm-vitem" data-item-id="' + esc(it.id) + '" data-source="' + esc(sourceKey) + '">' +
      '<div class="dsh-pm-vitem-head">' +
        '<span class="dsh-pm-vitem-badge">' + (badge[it.status] ?? esc(it.status)) + '</span>' +
        '<span class="dsh-pm-vitem-src">' + esc(it.source.kind === 'requirement' ? '需求级' : it.source.taskId) + '</span>' +
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

const renderArchivedBody: StageBodyRenderer = (payload) => {
  const body = (payload as Extract<StageDetail, { stage: 'archived' }>).body
  if (!body.archive) {
    return '<div class="dsh-pm-sn-body" data-stage="archived"><div class="dsh-pm-sn-empty">暂无归档材料</div></div>'
  }
  const a = body.archive
  const merged = (a.mergedInto?.length ?? 0) > 0
    ? '<div class="dsh-pm-sn-dim">合并去向：' + (a.mergedInto ?? []).map(p => '<button type="button" class="dsh-pm-sn-doc" data-action="open-doc" data-path="' + esc(p) + '" title="' + esc(displayDocPath(p)) + '">' + esc(p) + '</button>').join(' · ') + '</div>'
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

export const StageRenderers: Record<MainStageKey, { renderBody: StageBodyRenderer }> = {
  draft: { renderBody: renderDraftBody },
  brainstorming: { renderBody: renderBrainstormBody },
  design: { renderBody: renderDesignBody },
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
    const reason = ev.reason !== undefined && ev.reason.length > 0 ? ev.reason : (STAGE_LABELS[ev.status as MainStageKey] ?? ev.status)
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
    if (kind === 'task_detail') {
      // REQ-260922182638-0777 FR-5：任务卡不再折叠「×N」——逐张列出且带任务名称
      // （名称经 artifact.path ↔ StageTaskRef.cardDoc 精确匹配；匹配不到降级「任务卡（t-xxx）」）
      const titles = taskTitleByCardDoc(payload)
      for (const artifact of list) {
        const label = taskCardLabel(artifact.path, titles.get(normDocPath(artifact.path)))
        chainItems.push(
          '<span class="dsh-pm-trace-node" data-kind="' + esc(kind) + '">' +
            '<button type="button" class="dsh-pm-sn-doc dsh-pm-trace-path" data-action="open-doc" data-path="' + esc(artifact.path) + '" title="' + esc(displayDocPath(artifact.path)) + '">' + esc(label) + '</button>' +
          '</span>'
        )
      }
      continue
    }
    for (const artifact of list) {
      // 同类多份（design）用中文文档名区分（FR-4），否则同节点多份文档全叫「设计文档」
      const label = traceNodeLabel(kind, artifact.path)
      chainItems.push(
        '<span class="dsh-pm-trace-node" data-kind="' + esc(kind) + '">' +
          '<button type="button" class="dsh-pm-sn-doc dsh-pm-trace-path" data-action="open-doc" data-path="' + esc(artifact.path) + '" title="' + esc(displayDocPath(artifact.path)) + '">' + esc(label) + '</button>' +
        '</span>'
      )
    }
  }

  // 缺失必备产物（红字追加在链尾）
  const registeredKinds = new Set(artifacts.map(a => a.kind))
  for (const kind of required) {
    if (!registeredKinds.has(kind)) {
      const kindLabel = artifactKindLabel(kind)
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

/** 面板头：这一步干了什么 / 进行到什么程度（一句话）。
 *  返回 string | undefined：legacy done 节点不在流水线里，没有专属一句话（运行期原样）。 */
export function stageHeadSummary(payload: StageDetail): string | undefined {
  if (!payload.enabled) return '本分类跳过'
  switch (payload.stage) {
    case 'draft': return '已立项'
    case 'brainstorming': {
      const b = (payload as Extract<StageDetail, { stage: 'brainstorming' }>).body
      const n = b.comments?.length ?? 0
      return n > 0 ? fmt('{n} 条评论', { n }) : '需求分析'
    }
    case 'design': {
      const b = (payload as Extract<StageDetail, { stage: 'design' }>).body
      // 旧管线存量兼容（2026-09-21 前：设计阶段交计划）：以"设计阶段确有 plan 产物"或
      // "有计划但一份设计文档都没交"识别；新管线需求的 PlanRecord 是拆分阶段才产生的，
      // 不能拿 req.plan 是否存在当判据（否则新需求也永远显示计划文案——线上实测踩到）
      const designPlanArtifact = (payload.artifacts ?? []).some(a => a.kind === 'plan' && a.stage === 'design')
      const submittedDesign = (b.designDocs ?? []).some(d => d.submitted)
      if (b.plan && (designPlanArtifact || !submittedDesign)) {
        if (b.plan.approvedAt !== undefined) return '计划已批准'
        if (b.plan.rejectedAt !== undefined) return '计划被退回'
        return '计划待批准'
      }
      // 现管线（2026-09-21 起设计阶段只写设计文档）：按逐份交付 / 人工确认取词（FR-8）
      const docs = (b.designDocs ?? []).filter(d => d.exempted === undefined)
      if (docs.length > 0) {
        const submitted = docs.filter(d => d.submitted).length
        if (submitted < docs.length) return fmt('设计文档 {n}/{N} 已交', { n: submitted, N: docs.length })
        const designArts = (payload.artifacts ?? []).filter(a => a.kind === 'design')
        const confirmed = designArts.length > 0 && designArts.every(a => a.confirmedAt !== undefined)
        return confirmed ? '设计已确认' : '待确认设计文档'
      }
      return '待提交设计文档'
    }
    case 'decomposing': {
      const b = (payload as Extract<StageDetail, { stage: 'decomposing' }>).body
      const n = b.tasks?.length ?? 0
      return n > 0 ? fmt('{n} 个任务', { n }) : '待拆分'
    }
    case 'implementing': {
      const b = (payload as Extract<StageDetail, { stage: 'implementing' }>).body
      const tasks = b.tasks ?? []
      const total = tasks.length
      if (total === 0) return '暂无任务'
      const done = tasks.filter(t => t.status === 'done').length
      const active = tasks.find(t => t.status === 'in_progress' || t.status === 'integrating' || t.status === 'testing')
      let s = fmt('{done}/{total} 完成', { done, total })
      if (total - done > 0) s += fmt(' · 剩 {n} 个', { n: total - done })
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
    // REQ-9f4a44：done 节点已移除（legacy 兼容分支，不在 MainStageKey 里）
    case 'done': return undefined
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
  const state: StageRowState = payload.enabled ? (opts.state ?? 'current') : 'skipped'
  const summary = stageHeadSummary(payload)
  const latestAt = payload.timeline.length > 0 ? payload.timeline[payload.timeline.length - 1].at : undefined

  const warn = payload.pendingConfirmation
    ? '<div class="dsh-pm-sn-warn">⚠ 有产物待人工确认</div>'
    : ''

  // done 无渲染器（legacy 节点）：显式短路，与注册表里没有该键的运行期行为一致
  const renderer = payload.stage === 'done' ? undefined : StageRenderers[payload.stage]
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
  const curIdx = (ALL_STAGE_KEYS as readonly string[]).indexOf(ov.currentStage)
  const idx = (ALL_STAGE_KEYS as readonly string[]).indexOf(stage)
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
