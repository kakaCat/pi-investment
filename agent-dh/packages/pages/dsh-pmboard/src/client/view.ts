/**
 * 项目看板视图 —— 数据到 innerHTML 的纯渲染（参照 holdings view.ts 模式）。
 * 三层：泳道看板（需求状态列）/ 需求详情（任务 DAG + 任务列 + 评论）/ 待归类区。
 * 所有用户文本经 esc() 转义；交互经 data-action 属性委派到 board-mount。
 *
 * @module dsh-pmboard/client/view
 */
import { esc } from '@pi-investment/page-kit/client'
import type { BoardState, ReqCard, RequirementRecord, RequirementStatus, TaskRecord, TaskStatus, TriageRecord } from './types.ts'

/* ------------------------------------------------------------------ utils */

const STATUS_LABELS: Record<RequirementStatus, string> = {
  draft: '立项', reviewing: '评审', decomposing: '拆分', implementing: '实施',
  accepting: '验收', done: '完成', archived: '归档', canceled: '取消',
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

/** 主链 7 态（泳道列），archived/canceled 走底部归档区 */
export const LANE_STATUSES: readonly RequirementStatus[] = [
  'draft', 'reviewing', 'decomposing', 'implementing', 'accepting', 'done',
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
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
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

export function buildBoard(state: BoardState): string {
  const cards = toReqCards(state)
  const lanes = LANE_STATUSES.map(status => {
    const inLane = cards.filter(c => c.req.status === status)
    const cardsHtml = inLane.map(c => renderReqCard(c)).join('')
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

  const archived = state.requirements.filter(r => r.status === 'archived' || r.status === 'canceled')
  const archivedHtml = archived.length > 0
    ? `<div class="dsh-pm-archived-bar">
         <span class="dsh-pm-archived-label">归档/取消 ${archived.length}</span>
         ${archived.map(r => `<span class="dsh-pm-archived-chip" data-status="${r.status}">${esc(r.id)} ${esc(r.title)}</span>`).join('')}
       </div>`
    : ''

  return `
    <div class="dsh-pm-board">
      <div class="dsh-pm-head">
        <h1 class="dsh-pm-title">项目看板</h1>
        <span class="dsh-pm-rev">rev ${state.revision}</span>
        <button type="button" class="dsh-pm-btn" data-action="refresh" title="刷新">刷新</button>
        <button type="button" class="dsh-pm-btn primary" data-action="new-req" title="新建需求">+ 需求</button>
      </div>
      <div class="dsh-pm-lanes">${lanes}</div>
      ${archivedHtml}
    </div>`
}

function renderReqCard(card: ReqCard): string {
  const { req, tasks, doneCount, totalCount, readyIds, blocked } = card
  const pct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0
  const cat = req.category ? `<span class="dsh-pm-cat" data-cat="${req.category}">${CATEGORY_LABELS[req.category] ?? req.category}</span>` : ''
  const blockedChip = blocked ? '<span class="dsh-pm-flag blocked">阻塞</span>' : ''
  const pausedChip = req.paused ? '<span class="dsh-pm-flag paused">暂停</span>' : ''
  const readyChip = readyIds.length > 0 ? `<span class="dsh-pm-flag ready">${readyIds.length} ready</span>` : ''
  // 窗口 chip：立项来源窗口（窗口↔需求关联）+ 最近执行会话
  const sessionChip = renderWindowChip(req) + renderSessionChip(tasks)
  const actions = cardActions(req)

  return `
    <div class="dsh-pm-card${blocked ? ' is-blocked' : ''}" data-req="${esc(req.id)}" data-action="open-req">
      <div class="dsh-pm-card-top">
        <span class="dsh-pm-card-id">${esc(req.id)}</span>
        ${cat}${blockedChip}${pausedChip}${readyChip}
      </div>
      <div class="dsh-pm-card-title">${esc(req.title)}</div>
      <div class="dsh-pm-card-progress">
        <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${pct}%"></div></div>
        <span class="dsh-pm-card-pct">${progress(doneCount, totalCount)}</span>
      </div>
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
    const cls = opts?.primary === true ? 'dsh-pm-card-btn primary' : 'dsh-pm-card-btn'
    const title = opts?.title !== undefined ? ` title="${esc(opts.title)}"` : ''
    return `<button type="button" class="${cls}" data-action="move-req" data-to="${to}" data-id="${esc(req.id)}"${title}>${label}</button>`
  }
  let actions = ''
  switch (req.status) {
    case 'draft':
      actions = btn('reviewing', '提交评审', { primary: true, title: '进入评审（方案共创）；窗口接手开工时也会自动进入' })
        + btn('canceled', '取消', { title: '取消该需求' })
      break
    case 'reviewing':
      actions = btn('decomposing', '确认方案', { primary: true, title: '人工闸门：方案确认后进入拆分' })
        + btn('draft', '退回', { title: '退回立项' })
      break
    case 'decomposing':
      actions = btn('implementing', '确认拆分', { primary: true, title: '人工闸门：任务 DAG 确认后进入实施' })
      break
    case 'implementing':
      actions = btn('accepting', '提交验收', { primary: true, title: '实施完成 → 验收（任务全部完成时也会自动进入）' })
      break
    case 'accepting':
      actions = btn('done', '验收通过', { primary: true, title: '人工闸门：验收通过即完成' })
      break
    case 'done':
      actions = btn('archived', '归档', { title: '人工闸门：归档归集文档' })
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
function renderWindowChip(req: RequirementRecord): string {
  const sid = req.sourceSessionId
  if (!sid) return ''
  const code = windowCodeFromSessionId(sid)
  return `<button type="button" class="dsh-pm-window" data-action="jump-session" data-sid="${esc(sid)}" title="立项来源窗口（点击跳转到该会话）：${esc(sid)}">窗口 ${esc(code)}</button>`
}

function renderSessionChip(tasks: TaskRecord[]): string {
  for (let i = tasks.length - 1; i >= 0; i--) {
    const execs = tasks[i].executions
    for (let j = execs.length - 1; j >= 0; j--) {
      const sid = execs[j].sessionId
      if (sid) {
        return `<button type="button" class="dsh-pm-session" data-action="jump-session" data-sid="${esc(sid)}" title="跳转到执行会话">会话 ${esc(sid.slice(0, 12))}…</button>`
      }
    }
  }
  return ''
}

/* ------------------------------------------------------------------ 需求详情 */

export function buildReqDetail(req: RequirementRecord, tasks: TaskRecord[]): string {
  const reqTasks = tasks.filter(t => t.requirementId === req.id)
  const dag = buildDag(reqTasks)
  const taskCols = buildTaskColumns(reqTasks)
  const comments = renderComments(req.comments)
  const gateHint = gateHintFor(req.status)

  return `
    <div class="dsh-pm-detail" data-detail-req="${esc(req.id)}">
      <div class="dsh-pm-detail-head">
        <button type="button" class="dsh-pm-btn" data-action="back" title="返回看板">← 看板</button>
        <span class="dsh-pm-card-id">${esc(req.id)}</span>
        <span class="dsh-pm-status" data-status="${req.status}">${STATUS_LABELS[req.status]}</span>
        ${req.blocked ? '<span class="dsh-pm-flag blocked">阻塞</span>' : ''}
        ${renderWindowChip(req)}
        <span class="dsh-pm-detail-updated">${fmtTime(req.updatedAt)}</span>
      </div>
      <h2 class="dsh-pm-detail-title">${esc(req.title)}</h2>
      ${req.description ? `<div class="dsh-pm-detail-desc">${esc(req.description)}</div>` : ''}
      ${gateHint}
      <div class="dsh-pm-detail-section">
        <h3>任务 DAG</h3>
        ${dag}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>任务（${reqTasks.length}）</h3>
        ${taskCols}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>评论（${req.comments.length}）</h3>
        ${comments}
        <div class="dsh-pm-comment-form">
          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="req" data-id="${esc(req.id)}">发送</button>
        </div>
      </div>
    </div>`
}

/** 当前状态的闸门提示（人工闸门标出操作按钮） */
function gateHintFor(status: RequirementStatus): string {
  const hints: Partial<Record<RequirementStatus, string>> = {
    draft: '<div class="dsh-pm-gate">需求已立项：窗口接手开工后自动进入评审 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="reviewing">提交评审</button></div>',
    reviewing: '<div class="dsh-pm-gate">人工闸门：方案确认后进入拆分 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="decomposing">确认方案</button> <button type="button" class="dsh-pm-btn" data-action="move-req" data-to="draft">退回立项</button></div>',
    decomposing: '<div class="dsh-pm-gate">人工闸门：DAG 确认后进入实施 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="implementing">确认拆分</button></div>',
    accepting: '<div class="dsh-pm-gate">人工闸门：验收通过后完成 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="done">验收通过</button></div>',
    done: '<div class="dsh-pm-gate">人工闸门：归档归集文档 <button type="button" class="dsh-pm-btn" data-action="move-req" data-to="archived">归档</button></div>',
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

export function buildTaskDetail(task: TaskRecord, req: RequirementRecord | undefined): string {
  const execs = task.executions.map(e => `
    <div class="dsh-pm-exec" data-outcome="${e.outcome}">
      <span class="dsh-pm-exec-outcome">${e.outcome}</span>
      <span>${fmtTime(e.startedAt)}</span>
      ${e.sessionId ? `<button type="button" class="dsh-pm-session" data-action="jump-session" data-sid="${esc(e.sessionId)}">会话 ${esc(e.sessionId.slice(0, 12))}…</button>` : ''}
      ${e.error ? `<div class="dsh-pm-exec-error">${esc(e.error)}</div>` : ''}
      ${e.evidence && e.evidence.length > 0 ? `<div class="dsh-pm-exec-evidence">${e.evidence.map(ev => `<code>${esc(ev)}</code>`).join(' ')}</div>` : ''}
    </div>`).join('')

  return `
    <div class="dsh-pm-taskdetail" data-detail-task="${esc(task.id)}">
      <div class="dsh-pm-detail-head">
        <button type="button" class="dsh-pm-btn" data-action="back-req" data-req="${esc(task.requirementId)}" title="返回需求">← ${esc(task.requirementId)}</button>
        <span class="dsh-pm-card-id">${esc(task.id)}</span>
        <span class="dsh-pm-status" data-status="${task.status}">${TASK_STATUS_LABELS[task.status]}</span>
      </div>
      <h2 class="dsh-pm-detail-title">${esc(task.title)}</h2>
      ${task.description ? `<div class="dsh-pm-detail-desc">${esc(task.description)}</div>` : ''}
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
    </div>`
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
