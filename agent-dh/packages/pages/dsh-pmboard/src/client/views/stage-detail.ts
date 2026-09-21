/**
 * 需求详情页骨架：进度点 / Tab / 操作条 / DAG / 任务表 / 评论（REQ-47939a t11 机械拆分）。
 *
 * @module dsh-pmboard/client/views/stage-detail
 */
import { esc } from '../html.js'
import type { RequirementRecord, RequirementStatus, TaskRecord, TaskStatus } from '../types.ts'
import { PROGRESS_DOT_STAGES, WORKFLOW_STAGES, getStageOrder } from '../workflow-constants.ts'
import { NO_ARCHIVED, PHASE_LABELS, STATUS_LABELS, TASK_STATUS_LABELS, fmtTime, renderComments, renderMarkdown, renderWindowChip, windowCodeFromSessionId } from '../render/dom-utils.ts'
import { renderReqTimeline } from './timeline.ts'
import { renderArchiveSection, renderDocSection, renderVerifySection } from './verification.ts'
import { renderInjectionInfo } from '../injection-info.ts'
import { renderSubtaskChain, subtaskChain } from '../render/subtask-view.ts'
import { renderTokenPlaceholder } from '../token-info.ts'
import { renderMarksPlaceholder } from '../marks-info.ts'

// ---------------------------------------------------------------------------
// 需求详情页：8 态进度点 + 4 Tab 分组（REQ-6f39b5）
// ---------------------------------------------------------------------------

/**
 * 渲染 8 态进度点
 * @param currentStatus 当前需求状态
 * @returns 进度点 HTML
 */
export function buildProgressDots(currentStatus: RequirementStatus): string {
  const currentOrder = getStageOrder(currentStatus as any)
  
  return `<div class="dsh-pm-progress-dots">${
    PROGRESS_DOT_STAGES.map(stage => {
      const { label, order } = WORKFLOW_STAGES[stage]
      const state = order < currentOrder ? 'completed' 
                  : order === currentOrder ? 'current' 
                  : ''
      return `
        <div class="dsh-pm-dot-wrapper ${state}">
          <div class="dsh-pm-dot"></div>
          <span class="dsh-pm-dot-label">${esc(label)}</span>
        </div>`
    }).join('')
  }</div>`
}

/**
 * 渲染 4 个 Tab 按钮
 * @returns Tab 导航 HTML
 */
export function buildTabs(): string {
  return `
    <div class="dsh-pm-tabs">
      <button type="button" class="dsh-pm-tab active" data-action="switch-tab" data-tab="overview">📋 概览</button>
      <button type="button" class="dsh-pm-tab" data-action="switch-tab" data-tab="execution">⚙️ 执行</button>
      <button type="button" class="dsh-pm-tab" data-action="switch-tab" data-tab="timeline">📅 时间线</button>
      <button type="button" class="dsh-pm-tab" data-action="switch-tab" data-tab="archive">📦 归档</button>
      <button type="button" class="dsh-pm-tab" data-action="switch-tab" data-tab="token">🪙 Token</button>
    </div>`
}

/**
 * 渲染 4 个 Tab 内容区（REQ-6f39b5）。
 * 内容映射（对照原型 prototype.html，原折叠区全部迁移，禁止功能丢失）：
 * - 概览：需求描述(markdown) + 文档记录 + 当前阶段详情(动态加载)
 * - 执行：进度条 + 任务看板(+任务按钮) + DAG + 甘特图 + 拆分计划
 * - 时间线：状态时间线 + 评论(含表单)
 * - 归档：验收 + 归档材料
 */
export function buildTabContents(
  req: RequirementRecord,
  tasks: TaskRecord[],
  dag: string,
  comments: string,
  now: number
): string {
  return `
    <!-- 📋 概览 Tab（默认显示；REQ-6f39b5 对齐 prototype：描述 → 当前阶段高亮卡 → 文档）-->
    <div class="dsh-pm-tab-content active" data-tab-content="overview">
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">📄 需求描述</h3>
        <div class="dsh-pm-section-content">
          ${req.description ? `<div class="dsh-pm-md">${renderMarkdown(req.description)}</div>` : '<div class="dsh-pm-empty">暂无描述</div>'}
        </div>
      </div>
      <details class="dsh-pm-fold" open>
        <summary class="dsh-pm-section-title">🎯 当前阶段详情</summary>
        <div class="dsh-pm-stage-current">
          <div class="dsh-pm-stage-current-title">${STATUS_LABELS[req.status]}（${req.status}）</div>
          <div class="dsh-pm-stage-detail" id="dsh-pm-stage-detail-container"></div>
        </div>
      </details>
      <details class="dsh-pm-fold">
        <summary class="dsh-pm-section-title">💉 本次注入（只读）</summary>
        <div class="dsh-pm-section-content" id="dsh-pm-injection-info-container">${renderInjectionInfo([])}</div>
      </details>
      <details class="dsh-pm-fold">
        <summary class="dsh-pm-section-title">📁 文档记录</summary>
        <div class="dsh-pm-section-content">${renderDocSection(req)}</div>
      </details>
    </div>

    <!-- ⚙️ 执行 Tab（REQ-6f39b5 严格对齐 prototype：统计卡片 + DAG + 任务表格）-->
    <div class="dsh-pm-tab-content" data-tab-content="execution">
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat"><div class="dsh-pm-stat-label">总任务</div><div class="dsh-pm-stat-value">${tasks.length}</div></div>
        <div class="dsh-pm-stat dsh-pm-stat-success"><div class="dsh-pm-stat-label">已完成</div><div class="dsh-pm-stat-value">${tasks.filter(t => t.status === 'done').length}</div></div>
        <div class="dsh-pm-stat"><div class="dsh-pm-stat-label">开发中</div><div class="dsh-pm-stat-value">${tasks.filter(t => t.status === 'in_progress').length}</div></div>
        <div class="dsh-pm-stat"><div class="dsh-pm-stat-label">待开始</div><div class="dsh-pm-stat-value">${tasks.filter(t => t.status === 'todo').length}</div></div>
      </div>
      ${dag}
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">📋 任务列表</h3>
        ${buildTaskTable(tasks)}
      </div>
    </div>

    <!-- 📅 时间线 Tab -->
    <div class="dsh-pm-tab-content" data-tab-content="timeline">
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">📅 状态变更记录</h3>
        <div class="dsh-pm-section-content">${renderReqTimeline(req, now)}</div>
      </div>
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">💬 评论<span class="dsh-pm-fold-count">${req.comments.length} 条</span></h3>
        <div class="dsh-pm-section-content">
          ${comments}
          <div class="dsh-pm-comment-form" data-actor="human">
            <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论（以「人」身份记录）…" />
            <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="req" data-id="${esc(req.id)}">发送</button>
          </div>
        </div>
      </div>
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">🏷 条款接收状态<span class="dsh-pm-fold-count">谁接了 / 还没人接</span></h3>
        <div class="dsh-pm-section-content">
          <div id="dsh-pm-marks-container">${renderMarksPlaceholder('加载中…')}</div>
        </div>
      </div>
    </div>

    <!-- 🪙 Token Tab（REQ-a33899 t6）：按需求看 token 去向 + 固定/注入提示词成本 -->
    <div class="dsh-pm-tab-content" data-tab-content="token">
      <div id="dsh-pm-token-container">${renderTokenPlaceholder('加载中…')}</div>
    </div>

    <!-- 📦 归档 Tab -->
    <div class="dsh-pm-tab-content" data-tab-content="archive">
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">✅ 验收（人工审核）</h3>
        <div class="dsh-pm-section-content">${renderVerifySection(req)}</div>
      </div>
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">📦 归档（文档合并）</h3>
        <div class="dsh-pm-section-content">${renderArchiveSection(req)}</div>
      </div>
    </div>`
}


export function buildReqDetail(req: RequirementRecord, tasks: TaskRecord[], now: number = Date.now(), archived: ReadonlySet<string> = NO_ARCHIVED): string {
  const reqTasks = tasks.filter(t => t.requirementId === req.id)
  const dag = buildDag(reqTasks)
  const comments = renderComments(req.comments)
  const gateHint = gateHintFor(req.status)
  const actionBar = renderActionBar(req)

  return `
    <div class="dsh-pm-detail" data-detail-req="${esc(req.id)}">
      <div class="dsh-pm-detail-head">
        <button type="button" class="dsh-pm-btn" data-action="back" title="返回看板">← 看板</button>
        <span class="dsh-pm-card-id">${esc(req.id)}</span>
        <span class="dsh-pm-status" data-status="${req.status}">${STATUS_LABELS[req.status]}</span>
        ${req.blocked ? '<span class="dsh-pm-flag blocked">阻塞</span>' : ''}
        ${renderWindowChip(req, archived)}
        <span class="dsh-pm-detail-updated">${fmtTime(req.updatedAt)}</span>
        <h1 class="dsh-pm-detail-title">${esc(req.title)}</h1>
        ${buildProgressDots(req.status)}
      </div>
      ${actionBar}
      ${gateHint}
      ${buildTabs()}
      ${buildTabContents(req, reqTasks, dag, comments, now)}
    </div>`
}

/**
 * 当前状态的闸门提示（REQ-31e11f #8：只给**文字**说明）。
 * 操作按钮不在提示里 —— 统一由 renderActionBar 常驻在详情头下方，避免
 * 「按钮藏在折叠区/两处重复」；提示只说“现在该谁动手”。
 */
export function gateHintFor(status: RequirementStatus): string {
  const hints: Partial<Record<RequirementStatus, string>> = {
    draft: '已立项：窗口接手开工后自动进入需求分析，人可在上方操作条手动催办。',
    brainstorming: '需求分析中：窗口 agent 会自行推进到设计，人可在上方操作条确认方案或退回立项。',
    design: '设计中：计划提交后请在上方操作条点「批准计划」——批准前拆分会被告代码级拒绝。',
    decomposing: '拆分中：任务落库/开工后系统自动推进到实施，人可在上方操作条确认拆分。',
    implementing: '实施中：任务全部完成时自动进入验收，人可在上方操作条提交验收。',
    accepting: '验收中：看完验收材料后，在上方操作条点「验收通过」或「退回返工」。',
    done: '已完成（历史状态）：验收通过现已直接归档，此状态仅存在于旧记录。',
  }
  const text = hints[status]
  return text === undefined ? '' : '<div class="dsh-pm-gate">' + text + '</div>'
}

/**
 * 详情头下方的**常驻操作条**（REQ-31e11f #8：审批入口外置）。
 *
 * 问题：批准计划 / 验收通过 / 归档 三个按钮原本只存在于「拆分计划 / 验收 / 归档」
 * 三个默认折叠的 <details> 里 —— 用户看不到就等于没有。这里把当前阶段**所有人工
 * 闸门按钮**正面铺开，折叠区只保留内容（不再是唯一入口）。
 *
 * 覆盖四类：① 阶段推进/退回 move-req；② 计划裁决 plan-approve/plan-reject；
 * ③ 验收裁决 verify-pass/verify-rework；④ 归档 archive-req。
 * 同一动作只给一次（如验收态已交材料 → 只给 verify-pass，不再给等价的 move→done）。
 * 无任何可用操作时整条不渲染（不留空壳）。
 */
const BAR_LABEL = '<span class="dsh-pm-action-bar-label">本阶段操作</span>'

export function renderActionBar(req: RequirementRecord): string {
  const items: string[] = []
  /**
   * 「本阶段暂时没有可点的按钮」时的说明（REQ-9f4a44 后新增）。
   * 为什么需要它：整条不渲染 = 人在这个阶段看不到任何出口，会以为看板坏了。
   * 但也不能给"点了必被代码级拒绝"的假按钮（归档门要求验收材料已登记确认）。
   */
  const hints: string[] = []
  const add = (action: string, label: string, title: string, isPrimary = false): void => {
    const cls = isPrimary ? 'dsh-pm-btn primary' : 'dsh-pm-btn'
    items.push('<button type="button" class="' + cls + '" data-action="' + action
      + '" data-id="' + esc(req.id) + '" title="' + esc(title) + '">' + label + '</button>')
  }
  const move = (to: RequirementStatus, label: string, title: string, isPrimary = false): void => {
    const cls = isPrimary ? 'dsh-pm-btn primary' : 'dsh-pm-btn'
    items.push('<button type="button" class="' + cls + '" data-action="move-req" data-to="' + to
      + '" data-id="' + esc(req.id) + '" title="' + esc(title) + '">' + label + '</button>')
  }

  // 「立项取消」固定排操作条第一位（2026-09-20 用户裁定）：*→canceled 全在途态合法
  // 且仅人可点（REQ_TRANSITIONS）。此前只在 draft 渲染——在途需求找不到取消入口（实测）。
  if (req.status !== 'done' && req.status !== 'canceled' && req.status !== 'archived') {
    move('canceled', '立项取消', '取消该需求立项（仅人可操作）')
  }

  // REQ-6f39b5：推进按钮统一为「→ [下一阶段]」格式，阶段名对齐 workflow-stages.md
  switch (req.status) {
    case 'draft':
      move('brainstorming', '→ 需求分析', '进入需求分析；窗口接手开工时会自动进入', true)
      break
    case 'brainstorming':
      move('design', '→ 设计', '方案谈定 → 进入设计；设计阶段只写设计文档（计划归拆分阶段）', true)
      move('draft', '退回立项', '方案要重谈 → 退回立项')
      break
    case 'design':
      move('decomposing', '→ 拆分', '确认设计文档后进入拆分；拆分计划在拆分阶段提交并批准', true)
      move('brainstorming', '退回重谈', '方案要改 → 退回需求分析')
      break
    case 'decomposing':
      move('implementing', '→ 实施', '批准拆分计划后落库任务卡并进入实施', true)
      break
    case 'implementing':
      move('accepting', '→ 验收', '提交验收；任务全部完成时系统会自动推进', true)
      break
    case 'accepting':
      // REQ-a8d582 FR-3：显示条件**只看阶段**——进入验收态就铺按钮（按钮在下方统一加）。
      // 旧实现把"验收阶段"与"窗口已交验收材料"混为一谈，未交材料时只给一行提示、按钮不出现。
      // 用户 2026-09-20 明确订正："是验收阶段按钮就展示"。不合格/缺材料的风险改由
      // 点击后的确认弹框承担（board-mount 的 verify-pass 分支），不再靠隐藏按钮来回避。
      break
    case 'done':
      // done 为 legacy 死状态（REQ_TRANSITIONS: done: []），历史记录只读，不给转移按钮
      break
    default:
      break
  }

  if (req.plan !== undefined && req.plan.approvedAt === undefined) {
    add('plan-approve', '批准计划', '批准拆分计划 → 自动落库任务卡并进入实施', true)
    add('plan-reject', '退回计划', '退回拆分计划（窗口按理由重写）')
  }
  if (req.status === 'accepting') {
    // REQ-a8d582 FR-1/FR-3：只要在验收态就给按钮；有不合格项或未交材料时，点击先弹确认框。
    add('verify-pass', '验收通过', '人工审核通过（有不合格项或未交材料时会先弹确认框）', true)
    add('verify-rework', '退回返工', '退回返工（需填写意见）')
  }
  if (req.status === 'done' && req.archive !== undefined && req.archive.archivedAt === undefined) {
    add('archive-req', '归档', '归档：把产出并进项目文档', true)
  }

  if (items.length === 0 && hints.length === 0) return ''
  const hintHtml = hints.length === 0
    ? ''
    : '<span class="dsh-pm-action-bar-label">' + esc(hints.join('；')) + '</span>'
  return '<div class="dsh-pm-action-bar" data-req="' + esc(req.id) + '">'
    + BAR_LABEL
    + hintHtml
    + items.join('')
    + '</div>'
}

/** 任务 DAG：v1 用分层列表（拓扑层级）表达，节点可点击 */
export function buildDag(tasks: TaskRecord[]): string {
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

  return `<div class="dsh-pm-dag"><div class="dsh-pm-dag-title">🔀 任务依赖关系</div><div class="dsh-pm-dag-layers">` + layers.map((layer, i) => `
    <div class="dsh-pm-dag-layer">
      <span class="dsh-pm-dag-layer-label">L${i}</span>
      ${layer.map(t => `
        <span class="dsh-pm-dag-node" data-status="${t.status}" data-action="open-task" data-task="${esc(t.id)}" title="${esc(t.title)}">
          ${esc(t.id)} ${esc(t.title.slice(0, 20))}${t.title.length > 20 ? '…' : ''}
        </span>`).join('')}
    </div>`).join('') + `</div></div>`
}

/**
 * 任务五列小看板（含 in_review/done）。
 *
 * REQ-4842fe t-3be71b：**只有顶层卡进列** —— 子卡挂在自己的父卡下（折叠展开，原生 <details>），
 * 不再单列（否则同一张子卡既在列里又挂在父卡下，列计数与进度口径都会被重复计）。
 * 存量卡（无 parentId 且无名下子卡）外观与改造前一致，仅多一枚 [手动] 标。
 */
export function buildTaskColumns(tasks: TaskRecord[]): string {
  if (tasks.length === 0) return '<div class="dsh-pm-empty">暂无任务</div>'
  const cols: TaskStatus[] = ['todo', 'in_progress', 'integrating', 'testing', 'in_review', 'done']
  const top = tasks.filter(t => t.parentId === undefined)
  return `<div class="dsh-pm-taskcols">` + cols.map(status => {
    const inCol = top.filter(t => t.status === status)
    return `
      <div class="dsh-pm-taskcol" data-col="${status}">
        <div class="dsh-pm-taskcol-head">${TASK_STATUS_LABELS[status]} ${inCol.length}</div>
        ${inCol.map(t => {
          const chain = subtaskChain(tasks, t.id)
          const legacy = chain.length === 0
          const chainDone = chain.filter(x => x.status === 'done').length
          return `
          <div class="dsh-pm-task${legacy ? ' is-legacy' : ' is-parent'}" data-task="${esc(t.id)}" data-action="open-task">
            <div class="dsh-pm-task-title">${esc(t.title)}${legacy ? '<span class="dsh-pm-manual-chip" title="存量卡：未开启自动链，外观与推进方式与改造前一致">手动</span>' : ''}</div>
            <div class="dsh-pm-task-meta">
              <span class="dsh-pm-phase">${PHASE_LABELS[t.phase] ?? t.phase}</span>
              ${legacy ? '' : `<span class="dsh-pm-subcount">子卡 ${chainDone}/${chain.length}</span>`}
              ${t.blocked ? '<span class="dsh-pm-flag blocked">阻塞</span>' : ''}
            </div>
            ${legacy ? '' : renderSubtaskChain(tasks, t)}
          </div>`
        }).join('')}
      </div>`
  }).join('') + `</div>`
}

/**
 * 任务表格（REQ-6f39b5：对齐 prototype.html 执行 Tab 的 dsh-pm-task-table）。
 * 列：状态 | 任务 | 阶段 | 依赖 | 负责人 | 操作；行点击进任务详情。
 */
export function buildTaskTable(tasks: TaskRecord[]): string {
  if (tasks.length === 0) return '<div class="dsh-pm-empty">暂无任务</div>'
  const statusIcon = (s: TaskStatus): string =>
    s === 'done' ? '✓' : s === 'in_progress' ? '◐' : s === 'todo' ? '○' : '◐'
  const rows = tasks.map(t => {
    const deps = t.dependsOn.length > 0 ? t.dependsOn.map(x => esc(x)).join(',') : '-'
    const owner = t.claimedBy !== undefined && t.claimedBy.length > 0
      ? windowCodeFromSessionId(t.claimedBy)
      : '-'
    return `
      <tr data-action="open-task" data-task="${esc(t.id)}">
        <td><span class="dsh-pm-task-status ${t.status}">${statusIcon(t.status)} ${TASK_STATUS_LABELS[t.status]}</span></td>
        <td>${esc(t.title)}</td>
        <td>${PHASE_LABELS[t.phase] ?? t.phase}</td>
        <td>${deps}</td>
        <td>${owner}</td>
        <td><span class="dsh-pm-link">查看</span></td>
      </tr>`
  }).join('')
  return `
    <table class="dsh-pm-task-table">
      <thead><tr><th>状态</th><th>任务</th><th>阶段</th><th>依赖</th><th>负责人</th><th>操作</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`
}
