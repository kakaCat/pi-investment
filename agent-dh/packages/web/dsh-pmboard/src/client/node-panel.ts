/**
 * 会话流程节点详情面板渲染器（REQ-260923134706-e72f / FR-1..FR-5, FR-9）——设计基线
 * stage-modals-alpine.html 的落地实现。纯函数、零 IO：输入 StageOverview + 会话进度 +
 * 注入/隔离留痕，输出面板 HTML 字符串（React 壳经 dangerouslySetInnerHTML 注入）。
 *
 * 结构（根 .dsh-pm-np）：
 *   .dsh-pm-np-req   REQ 胶囊 + 需求标题
 *   .dsh-pm-np-head  状态胶囊 + 一句话进展 + 相对时间
 *   <details open> ℹ️ 基础信息（实施节点无此块，改为 [流程图][泳道] 双视图）
 *   <details>      🔄 执行流程（默认收起，调 node-panel-process 的 renderProcessFold）
 *
 * 数据诚实：文档/任务链接一律 data-action="open-doc"（走既有右侧栏链路）；
 * 无产物/无任务显示空态，绝不伪造。
 *
 * @module dsh-pmboard/client/node-panel
 */
import {
  type StageDetail,
  type StageOverview,
  type StageKey,
  type MainStageKey,
  type StageTaskRef,
} from '../shared/protocol.js'
import { esc } from './html.js'
import { displayDocPath } from './open-doc.ts'
import { docFileLabel, KIND_ICONS } from '../shared/artifact-labels.js'
import { stageHeadSummary, stageRowState, type StageRowState } from './stage-panel.ts'
import {
  renderProcessFold,
  STAGE_STATE_WORD,
  type IsolationLogEntry,
  type ProcessFoldContext,
} from './node-panel-process.ts'
import type { InjectionInfoEntry } from './injection-info.ts'

export interface NodePanelInput {
  overview: StageOverview
  stage: StageKey
  requirement: { id: string; title: string; promptDifficulty?: string | null; category?: string }
  injection?: InjectionInfoEntry[]
  isolation?: IsolationLogEntry[]
}

// ---------------------------------------------------------------------------
// 小工具
// ---------------------------------------------------------------------------

function rel(ms: number, now: number = Date.now()): string {
  const diff = now - ms
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  const d = new Date(ms)
  const pad = (n: number) => String(n).padStart(2, '0')
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
}

/** 拓扑分层（DAG 层级）：按依赖深度分组。 */
function topoLevels<T extends { id: string; dependsOn?: string[] }>(tasks: T[]): Map<number, T[]> {
  const byId = new Map(tasks.map(t => [t.id, t]))
  const cache = new Map<string, number>()
  const lv = (id: string): number => {
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

/** 文档条目（doc-list 内一行）：图标 + 名 + →，点击右侧栏打开。 */
function docItem(path: string, label: string, icon?: string, extraAttrs?: string): string {
  return '<button type="button" class="dsh-pm-np-docitem" data-action="open-doc" data-path="' + esc(path) + '" title="' + esc(displayDocPath(path)) + '"' + (extraAttrs !== undefined ? ' ' + extraAttrs : '') + '>' +
    '<span class="dsh-pm-np-docitem-icon">' + (icon ?? '📄') + '</span>' +
    '<span class="dsh-pm-np-docitem-name">' + esc(label) + '</span>' +
    '<span class="dsh-pm-np-docitem-arrow">→</span>' +
  '</button>'
}

/** 基础信息行（label + value）。 */
function infoItem(label: string, value: string, cls?: string): string {
  return '<div class="dsh-pm-np-info"><div class="dsh-pm-np-info-label">' + esc(label) + '</div><div class="dsh-pm-np-info-value' + (cls ? ' ' + cls : '') + '">' + value + '</div></div>'
}

function empty(text: string): string { return '<div class="dsh-pm-np-empty">' + esc(text) + '</div>' }

// ---------------------------------------------------------------------------
// 各节点基础信息体
// ---------------------------------------------------------------------------

function renderDraftInfo(p: Extract<StageDetail, { stage: 'draft' }>, reqId: string): string {
  const b = p.body
  const parts: string[] = []
  if (b.description) parts.push(infoItem('📝 需求描述', esc(b.description), 'is-desc'))
  if (b.category) parts.push(infoItem('🏷️ 分类', '<span class="dsh-pm-np-tag">' + esc(b.category) + '</span>'))
  parts.push(infoItem('📂 文档位置', esc('docs/requirements/' + reqId + '/')))
  if (b.sourceWindow) parts.push(infoItem('👤 来源窗口', esc(b.sourceWindow)))
  if (b.createdAt) parts.push(infoItem('📅 创建时间', esc(rel(b.createdAt))))
  return parts.join('')
}

function renderBrainstormInfo(p: Extract<StageDetail, { stage: 'brainstorming' }>): string {
  const docs = (p.artifacts ?? []).filter(a => a.kind === 'requirement')
  if (docs.length === 0) return empty('尚无内容')
  return '<div class="dsh-pm-np-doclist">' + docs.map(a => docItem(a.path, docFileLabel(a.path, a.kind), KIND_ICONS[a.kind] ?? '📄')).join('') + '</div>'
}

function renderDesignInfo(p: Extract<StageDetail, { stage: 'design' }>): string {
  const b = p.body
  const parts: string[] = []
  if (b.designDocs !== undefined && b.designDocs.length > 0) {
    const rows = b.designDocs.map(d => {
      const badge = d.conditional !== undefined ? `〔条件·${d.conditional}〕` : ''
      const exempt = d.exempted !== undefined ? '（已豁免）' : ''
      const label = d.name + badge + exempt
      // 已交 = 可点开右栏（FR-9）；未交 = 灰字占位，不可点
      if (d.submitted) return docItem(d.path, label, '✅', 'data-submitted="yes"')
      return '<div class="dsh-pm-np-designdoc" data-submitted="no">⬜ ' + esc(label) + '</div>'
    }).join('')
    parts.push(infoItem('📚 设计文档', rows))
  } else {
    parts.push(empty('尚无设计文档'))
  }
  return parts.join('')
}

/** 无任务卡文档的编号旁小标记（2026-09-24 用户裁定：去掉标题「（无任务卡）」后缀——难看；改在任务编号右侧放灰色文档图标，悬停提示）。 */
function nodocIcon(t: StageTaskRef): string {
  return t.cardDoc ? '' : '<span class="dsh-pm-np-nodoc" title="无任务卡文档，不可点开">📄</span>'
}

/** DAG 分层渲染（拆分 + 实施共用）：节点 = 上编号下说明的卡片，可点击打开任务卡文档。 */
function renderDag(tasks: StageTaskRef[]): string {
  if (tasks.length === 0) return empty('暂无任务')
  const layers = topoLevels(tasks)
  const secs: string[] = []
  for (const [lv, ts] of [...layers.entries()].sort((a, b) => a[0] - b[0])) {
    const label = lv === 0 ? '第 1 层 · 无依赖' : `第 ${lv + 1} 层${ts.length > 1 ? ` · ${ts.length} 个可并行` : ''}`
    // 与泳道卡片同构：上编号下说明；有任务卡文档则可点击打开（用户裁定 REQ-260923134706-e72f t8）
    const chips = ts.map(t => {
      const open = t.cardDoc ? ' data-action="open-doc" data-path="' + esc(t.cardDoc) + '"' : ''
      // 内层复用泳道卡片的 -card-id/-card-title 类，保证编号/名称的上下结构与泳道图逐字一致（用户裁定 t8）
      return '<button type="button" class="dsh-pm-np-dag-node" data-status="' + esc(t.status) + '"' + open + ' title="' + esc(t.title) + '">' +
        '<span class="dsh-pm-np-card-id">' + esc(t.id) + nodocIcon(t) + '</span>' +
        '<span class="dsh-pm-np-card-title">' + esc(t.title) + '</span>' +
      '</button>'
    }).join('')
    secs.push('<div class="dsh-pm-np-dag-layer"><div class="dsh-pm-np-dag-label">' + esc(label) + '</div><div class="dsh-pm-np-dag-row">' + chips + '</div></div>')
  }
  return '<div class="dsh-pm-np-dag">' + secs.join('') + '</div>'
}

function renderDecomposingInfo(p: Extract<StageDetail, { stage: 'decomposing' }>): string {
  const b = p.body
  const parts: string[] = []
  if (b.decompositionDoc) {
    parts.push('<div class="dsh-pm-np-doclist">' + docItem(b.decompositionDoc, '拆分计划：decomposition.md') + '</div>')
  } else {
    // 未交也要显式占位，避免"文档行凭空消失"（FR-9）
    parts.push('<div class="dsh-pm-np-doclist"><div class="dsh-pm-np-designdoc" data-submitted="no">⬜ 拆分计划：decomposition.md（未交）</div></div>')
  }
  parts.push(`<div class="dsh-pm-np-sec-label">📊 DAG 层级</div>${renderDag(b.tasks ?? [])}`)
  return parts.join('')
}

const SWIM_LANES: Readonly<Array<{ key: string; label: string }>> = [
  { key: 'todo', label: '待开始' },
  { key: 'in_progress', label: '开发中' },
  { key: 'integrating', label: '联调中' },
  { key: 'testing', label: '测试中' },
  { key: 'in_review', label: '待复核' },
  { key: 'done', label: '已完成' },
]

/** 6 列看板泳道（设计稿 task-columns 定稿）：每列一个状态，列内卡片竖排可纵向滚动。 */
function renderSwimlane(tasks: StageTaskRef[]): string {
  const cols = SWIM_LANES.map(lane => {
    const ts = tasks.filter(t => t.status === lane.key)
    const cards = ts.map(t => {
      const open = t.cardDoc ? ' data-action="open-doc" data-path="' + esc(t.cardDoc) + '"' : ''
      return '<button type="button" class="dsh-pm-np-card" data-status="' + esc(t.status) + '"' + open + ' title="' + esc(t.title) + '">' +
        '<span class="dsh-pm-np-card-id">' + esc(t.id) + nodocIcon(t) + '</span>' +
        '<span class="dsh-pm-np-card-title">' + esc(t.title) + '</span>' +
      '</button>'
    }).join('')
    return '<div class="dsh-pm-np-col" data-col="' + lane.key + '">' +
      '<div class="dsh-pm-np-col-head">' + esc(lane.label) + '<span class="dsh-pm-np-col-count">' + ts.length + '</span></div>' +
      '<div class="dsh-pm-np-col-body">' + (cards || empty('无')) + '</div>' +
    '</div>'
  }).join('')
  return '<div class="dsh-pm-np-cols">' + cols + '</div>'
}

/** 实施节点：无基础信息块，改为 [DAG][泳道] 双视图（DAG 与拆分节点统一名称）。 */
function renderImplViews(p: Extract<StageDetail, { stage: 'implementing' }>): string {
  const tasks = p.body.tasks ?? []
  return '<div class="dsh-pm-np-tabs">' +
      '<button type="button" class="dsh-pm-np-tab is-active" data-action="np-switch-view" data-view="flow">DAG</button>' +
      `<button type="button" class="dsh-pm-np-tab" data-action="np-switch-view" data-view="list">泳道</button>` +
    '</div>' +
    `<div class="dsh-pm-np-pane" data-pane="flow"><div class="dsh-pm-np-pane-caption">🔀 任务依赖关系（按最长依赖链分层，节点可点击打开任务卡文档）</div>${renderDag(tasks)}</div>` +
    `<div class="dsh-pm-np-pane" data-pane="list" hidden><div class="dsh-pm-np-pane-caption">按状态分列 · 点击卡片打开任务文档</div>${renderSwimlane(tasks)}</div>`
}

function renderAcceptingInfo(p: Extract<StageDetail, { stage: 'accepting' }>): string {
  const v = p.body.verification
  if (!v) return empty('尚未提交验收材料')
  const parts: string[] = []
  const vdoc = (p.artifacts ?? []).find(a => a.kind === 'verification')
  if (vdoc) parts.push(`<div class="dsh-pm-np-doclist">${docItem(vdoc.path, `验收材料：${docFileLabel(vdoc.path, 'verification')}`)}</div>`)
  if (v.sheet && v.sheet.items.length > 0) {
    const items = v.sheet.items
    const passed = items.filter(i => i.status === 'passed').length
    const failed = items.filter(i => i.status === 'failed').length
    const pending = items.filter(i => i.status === 'pending').length
    parts.push(`<div class="dsh-pm-np-sec-label">📋 验收单 v${v.sheet.version}</div>` +
      `<div class="dsh-pm-np-stats">` +
        `<span class="dsh-pm-np-stat">📊 共 ${items.length} 项</span>` +
        `<span class="dsh-pm-np-stat is-pass">✅ 通过 ${passed}</span>` +
        (failed > 0 ? `<span class="dsh-pm-np-stat is-fail">❌ 不通过 ${failed}</span>` : '') +
        (pending > 0 ? `<span class="dsh-pm-np-stat is-pending">⏳ 待裁决 ${pending}</span>` : '') +
      `</div>`)
  }
  return parts.join('') || empty('尚无内容')
}

function renderArchivedInfo(p: Extract<StageDetail, { stage: 'archived' }>): string {
  const a = p.body.archive
  if (!a) return empty('暂无归档材料')
  const parts: string[] = []
  const at = a.archivedAt ?? a.submittedAt
  parts.push(`<div class="dsh-pm-np-archive-badge">✅ 已归档 · ${esc(rel(at))}</div>`)
  if (a.docs.length > 0) {
    parts.push(`<div class="dsh-pm-np-sec-label">📚 归档文档</div><div class="dsh-pm-np-doclist">` +
      a.docs.map(d => docItem(d.path, docFileLabel(d.path, d.kind), KIND_ICONS[d.kind] ?? (d.path.endsWith('/') ? '📁' : '📄'))).join('') + `</div>`)
  }
  if ((a.mergedInto?.length ?? 0) > 0) {
    parts.push(`<div class="dsh-pm-np-sec-label">🔗 合并到项目</div><div class="dsh-pm-np-doclist">` +
      a.mergedInto!.map(m => docItem(m, m)).join('') + `</div>`)
  }
  if (a.indexEntry) parts.push(`<div class="dsh-pm-np-sec-label">💡 一句话结论</div><div class="dsh-pm-np-conclusion">${esc(a.indexEntry)}</div>`)
  return parts.join('')
}

// ---------------------------------------------------------------------------
// 基础信息折叠（实施节点无此块）
// ---------------------------------------------------------------------------

function renderInfoFold(payload: StageDetail, reqId: string): string {
  let inner = ''
  switch (payload.stage) {
    case 'draft': inner = renderDraftInfo(payload as Extract<StageDetail, { stage: 'draft' }>, reqId); break
    case 'brainstorming': inner = renderBrainstormInfo(payload as Extract<StageDetail, { stage: 'brainstorming' }>); break
    case 'design': inner = renderDesignInfo(payload as Extract<StageDetail, { stage: 'design' }>); break
    case 'decomposing': inner = renderDecomposingInfo(payload as Extract<StageDetail, { stage: 'decomposing' }>); break
    case 'accepting': inner = renderAcceptingInfo(payload as Extract<StageDetail, { stage: 'accepting' }>); break
    case 'archived': inner = renderArchivedInfo(payload as Extract<StageDetail, { stage: 'archived' }>); break
    default: inner = ''
  }
  if (inner.length === 0) return ''
  return '<details class="dsh-pm-np-fold" open>' +
    `<summary><span class="dsh-pm-np-fold-icon">▸</span><span class="dsh-pm-np-fold-text">ℹ️ 基础信息</span></summary>` +
    '<div class="dsh-pm-np-fold-body">' + inner + '</div>' +
  '</details>'
}

// ---------------------------------------------------------------------------
// 面板头
// ---------------------------------------------------------------------------

function renderHead(payload: StageDetail, req: NodePanelInput['requirement'], state: StageRowState): string {
  const stage = payload.stage as MainStageKey
  // 未到达的节点统一说「未开始」，不再借用该节点的完成态词（FR-10）
  const word = state === 'pending' ? '未开始' : (STAGE_STATE_WORD[stage] ?? stage)
  const summary = payload.enabled ? (stageHeadSummary(payload) ?? '') : '本分类跳过'
  const latestAt = payload.timeline.length > 0 ? payload.timeline[payload.timeline.length - 1].at : undefined
  const title = (stage === 'draft' || stage === 'archived') ? '' : (summary ?? '')
  return '<div class="dsh-pm-np-req"><span class="dsh-pm-np-req-pill">' + esc(req.id) + '</span><span class="dsh-pm-np-req-title">' + esc(req.title) + '</span></div>' +
    '<div class="dsh-pm-np-head">' +
      '<span class="dsh-pm-np-head-state" data-state="' + esc(state) + '">' + esc(word) + '</span>' +
      (title ? '<span class="dsh-pm-np-head-title">' + esc(title) + '</span>' : '') +
      (latestAt !== undefined ? '<span class="dsh-pm-np-head-time">' + esc(rel(latestAt)) + '</span>' : '') +
    '</div>'
}

// ---------------------------------------------------------------------------
// 入口
// ---------------------------------------------------------------------------

/**
 * 渲染单节点详情面板（纯字符串）。overview 无该节点时回退第一个可用节点。
 * 分类跳过（enabled=false）时只显示「本分类跳过」，两段不渲染。
 */
export function renderNodePanel(input: NodePanelInput): string {
  const ov = input.overview
  let payload = ov.stages.find(s => s.stage === input.stage)
  if (payload === undefined) payload = ov.stages[0]
  if (payload === undefined) return '<div class="dsh-pm-np">' + empty('无节点数据') + '</div>'

  const stage = payload.stage as MainStageKey
  const state = stageRowState(ov, payload.stage)

  if (!payload.enabled) {
    return '<div class="dsh-pm-np" data-stage="' + esc(stage) + '" data-state="skipped">' +
      renderHead(payload, input.requirement, 'skipped') +
      empty('本分类跳过该节点') +
    '</div>'
  }

  const processCtx: ProcessFoldContext = {
    requirement: input.requirement,
    injection: input.injection ?? [],
    isolation: input.isolation ?? [],
  }

  const implViews = stage === 'implementing' ? renderImplViews(payload as Extract<StageDetail, { stage: 'implementing' }>) : ''
  const infoFold = stage === 'implementing' ? '' : renderInfoFold(payload, input.requirement.id)

  return '<div class="dsh-pm-np" data-stage="' + esc(stage) + '" data-state="' + esc(state) + '">' +
    renderHead(payload, input.requirement, state) +
    infoFold +
    implViews +
    renderProcessFold(payload, processCtx) +
  '</div>'
}
