/**
 * 项目看板视图 —— 数据到 innerHTML 的纯渲染（参照 holdings view.ts 模式）。
 * 三层：泳道看板（需求状态列）/ 需求详情（任务 DAG + 任务列 + 评论）/ 待归类区。
 * 所有用户文本经 esc() 转义；交互经 data-action 属性委派到 board-mount。
 *
 * @module dsh-pmboard/client/view
 */
import { esc } from '@pi-investment/page-kit/client'
import type { BoardState, ReqCard, RequirementRecord, RequirementStatus, StatusEvent, TaskRecord, TaskStatus, TriageRecord } from './types.ts'

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

export function buildBoard(state: BoardState, now: number = Date.now()): string {
  const cards = toReqCards(state)
  const lanes = LANE_STATUSES.map(status => {
    const inLane = cards.filter(c => c.req.status === status)
    const cardsHtml = inLane.map(c => renderReqCard(c, now)).join('')
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
        <button type="button" class="dsh-pm-btn" data-action="open-tasks" title="任务总览与甘特图">任务</button>
        <button type="button" class="dsh-pm-btn primary" data-action="new-req" title="新建需求">+ 需求</button>
      </div>
      <div class="dsh-pm-lanes">${lanes}</div>
      ${archivedHtml}
    </div>`
}

function renderReqCard(card: ReqCard, now: number): string {
  const { req, tasks, doneCount, totalCount, readyIds, blocked } = card
  const pct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0
  const cat = req.category ? `<span class="dsh-pm-cat" data-cat="${req.category}">${CATEGORY_LABELS[req.category] ?? req.category}</span>` : ''
  const planChipHtml = planChip(req) + verifyChip(req) + archiveChip(req)
  const blockedChip = blocked ? '<span class="dsh-pm-flag blocked">阻塞</span>' : ''
  const pausedChip = req.paused ? '<span class="dsh-pm-flag paused">暂停</span>' : ''
  const readyChip = readyIds.length > 0 ? `<span class="dsh-pm-flag ready">${readyIds.length} ready</span>` : ''
  // 窗口 chip：立项来源窗口（窗口↔需求关联）+ 最近执行会话
  const timeLine = renderCardTime(req, now)
  const sessionChip = renderWindowChip(req) + renderSessionChip(tasks)
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

export function buildReqDetail(req: RequirementRecord, tasks: TaskRecord[], now: number = Date.now()): string {
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
        <h3>实施计划（plan mode）</h3>
        ${renderPlanSection(req)}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>时间线</h3>
        ${renderReqTimeline(req, now)}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>任务 DAG</h3>
        ${dag}
      </div>
      <div class="dsh-pm-detail-section">
        <div class="dsh-pm-section-head">
          <h3>任务（${reqTasks.length}）</h3>
          <button type="button" class="dsh-pm-btn sm" data-action="new-task" data-id="${esc(req.id)}" title="人工建任务卡（窗口 agent 走 reqboard_decompose 批量拆分）">+ 任务</button>
        </div>
        ${taskCols}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>甘特图</h3>
        ${buildGantt(req, reqTasks, now)}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>验收（人工审核）</h3>
        ${renderVerifySection(req)}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>归档（文档合并）</h3>
        ${renderArchiveSection(req)}
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

export function buildTaskDetail(task: TaskRecord, req: RequirementRecord | undefined, now: number = Date.now()): string {
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
    + '</div>'
}

const ARCHIVE_DOC_KIND_LABELS: Record<string, string> = {
  requirement: '需求说明', plan: '实施计划', verification: '验收材料', retro: '复盘', notes: '其他',
}
