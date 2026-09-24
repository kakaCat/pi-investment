/**
 * 产物 chips / 五道人工确认门 / 卡面操作行 / 拆分计划区块（REQ-47939a t11 机械拆分）。
 *
 * @module dsh-pmboard/client/views/artifacts
 */
import { esc } from '../html.js'
import type { ReqCard, RequirementRecord, RequirementStatus } from '../types.ts'
import type { ArtifactKind, StageArtifact, StageKey } from '../../shared/protocol.ts'
import { ARTIFACT_CONFIRM_GATES, REQ_TRANSITIONS, STAGE_ARTIFACT_REQUIREMENTS, confirmGateKindFor, flowProfileFor, fmtTokens } from '../../shared/protocol.ts'
import { CATEGORY_LABELS, NO_ARCHIVED, PHASE_LABELS, STATUS_LABELS, fmtDur, fmtTime, isTerminal, progress, renderSessionChip, renderWindowChip } from '../render/dom-utils.ts'
import { eventsOf } from './timeline.ts'
import { artifactKindLabel } from '../../shared/artifact-labels.ts'
import { progressText, renderAutoBadge, renderAutoControls, subtaskProgress } from '../render/subtask-view.ts'
import { archiveChip, verifyChip } from './verification.ts'

/* ------------------------------------------------------------------ 产物 chips（五道人工确认门，REQ-31e11f t7） */

// REQ-260922182638-0777：种类中文名唯一事实源 = shared/artifact-labels.ts（本文件不再建本地映射表）
/**
 * 计算需求在当前分类流程下，各确认门的产物状态。
 * 返回每个门的 { kind, status: 'confirmed'|'pending'|'missing', artifact? }。
 */
export function computeGateStatuses(req: RequirementRecord): Array<{
  kind: ArtifactKind
  status: 'confirmed' | 'pending' | 'missing'
  artifact?: StageArtifact
}> {
  const profile = flowProfileFor(req.category)
  const results: Array<{ kind: ArtifactKind; status: 'confirmed' | 'pending' | 'missing'; artifact?: StageArtifact }> = []
  for (const gateKey of profile.confirmGates) {
    const kind = ARTIFACT_CONFIRM_GATES[gateKey]
    if (kind === undefined) continue
    const artifact = (req.artifacts ?? []).find(a => a.kind === kind)
    if (artifact === undefined) {
      results.push({ kind, status: 'missing' })
    } else if (kind === 'design') {
      // REQ-2d1c74 FR-2：成组确认语义——任何一份设计文档无章都算待确认
      const anyUnconfirmed = (req.artifacts ?? []).some(a => a.kind === 'design' && a.confirmedAt === undefined)
      results.push(anyUnconfirmed ? { kind, status: 'pending', artifact } : { kind, status: 'confirmed', artifact })
    } else if (artifact.confirmedAt !== undefined) {
      results.push({ kind, status: 'confirmed', artifact })
    } else {
      results.push({ kind, status: 'pending', artifact })
    }
  }
  return results
}

/**
 * 当前生效的门：从 req.status 找下一态，用 confirmGateKindFor 算出产物 kind。
 * 无门（如 draft/implementing 或分类跳过）→ undefined。
 */
export function currentGateKind(req: RequirementRecord): ArtifactKind | undefined {
  const transitions = REQ_TRANSITIONS[req.status]
  if (transitions === undefined || transitions.length === 0) return undefined
  // 找第一个人工确认门对应的 next status
  for (const to of transitions) {
    const kind = confirmGateKindFor(req.category, req.status, to)
    if (kind !== undefined) return kind
  }
  return undefined
}

/** 产物 chip 单行：五门各自的状态一览（已确认=绿✓ / 待确认=橙可点 / 缺失=红）。 */
export function renderArtifactChips(req: RequirementRecord): string {
  const gates = computeGateStatuses(req)
  if (gates.length === 0) return ''
  const chips = gates.map(g => {
    const label = artifactKindLabel(g.kind)
    if (g.status === 'confirmed') {
      return '<span class="dsh-pm-artifact-chip confirmed" title="' + esc(label) + '已确认">✓ ' + esc(label) + '</span>'
    }
    if (g.status === 'pending') {
      return '<button type="button" class="dsh-pm-artifact-chip pending" data-action="confirm-artifact" data-id="' + esc(req.id) + '" data-kind="' + esc(g.kind) + '" title="点击确认' + esc(label) + '">⏳ ' + esc(label) + '</button>'
    }
    return '<span class="dsh-pm-artifact-chip missing" title="' + esc(label) + '缺失">✗ ' + esc(label) + '</span>'
  }).join('')
  return '<div class="dsh-pm-artifact-chips">' + chips + '</div>'
}

/**
 * 卡面「确认产物」主按钮（REQ-31e11f t7 核心：确认入口卡面外置）。
 * 仅当当前生效门有产物且待确认时渲染——一键确认，不用开抽屉。
 */
export function renderConfirmButton(req: RequirementRecord): string {
  const kind = currentGateKind(req)
  if (kind === undefined) return ''
  // REQ-2d1c74 FR-2：kind=design 是成组确认——任何一份无章即待确认，按钮文案写明「将确认全部 N 份设计文档」
  if (kind === 'design') {
    const designArts = (req.artifacts ?? []).filter(a => a.kind === 'design')
    if (designArts.length === 0 || designArts.every(a => a.confirmedAt !== undefined)) return ''
    const title = `一键确认全部 ${designArts.length} 份设计文档（成组确认），放行下一阶段`
    const text = `确认产物（全部 ${designArts.length} 份）`
    return '<button type="button" class="dsh-pm-btn sm primary dsh-pm-confirm-artifact" data-action="confirm-artifact" data-id="' + esc(req.id) + '" data-kind="' + esc(kind) + '" title="' + title + '">' + text + '</button>'
  }
  const artifact = (req.artifacts ?? []).find(a => a.kind === kind)
  if (artifact === undefined || artifact.confirmedAt !== undefined) return ''
  const label = artifactKindLabel(kind)
  return '<button type="button" class="dsh-pm-btn sm primary dsh-pm-confirm-artifact" data-action="confirm-artifact" data-id="' + esc(req.id) + '" data-kind="' + esc(kind) + '" title="一键确认' + esc(label) + '，放行下一阶段">确认产物</button>'
}

/** 派生展示：当前阶段产物完成度 + 待确认门数。 */
export function renderArtifactDerived(req: RequirementRecord): string {
  const profile = flowProfileFor(req.category)
  const allRequired: ArtifactKind[] = []
  for (const stage of profile.stages) {
    const kinds = STAGE_ARTIFACT_REQUIREMENTS[stage as StageKey]
    if (kinds !== undefined) allRequired.push(...kinds)
  }
  const present = (req.artifacts ?? []).length
  const total = allRequired.length
  const gates = computeGateStatuses(req)
  const pendingCount = gates.filter(g => g.status === 'pending').length
  if (total === 0 && pendingCount === 0) return ''
  const parts: string[] = []
  if (total > 0) parts.push('产物 ' + present + '/' + total)
  if (pendingCount > 0) parts.push(pendingCount + ' 门待确认')
  return '<div class="dsh-pm-artifact-derived">' + parts.join(' · ') + '</div>'
}

export function renderReqCard(card: ReqCard, now: number, archived: ReadonlySet<string> = NO_ARCHIVED): string {
  const { req, tasks, doneCount, totalCount, readyIds, blocked } = card
  const pct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0
  const cat = req.category ? `<span class="dsh-pm-cat" data-cat="${req.category}">${CATEGORY_LABELS[req.category] ?? req.category}</span>` : ''
  const planChipHtml = planChip(req) + verifyChip(req) + archiveChip(req)
  const blockedChip = blocked ? '<span class="dsh-pm-flag blocked">阻塞</span>' : ''
  const pausedChip = req.paused ? '<span class="dsh-pm-flag paused">暂停</span>' : ''
  // 自动链徽标 + 子卡进度（REQ-4842fe t-3be71b）：autoRun 缺省 = 存量需求 → 不显示徽标，外观不变
  const autoChip = req.autoRun !== undefined ? renderAutoBadge(req) : ''
  const sub = subtaskProgress(tasks)
  const readyChip = readyIds.length > 0 ? `<span class="dsh-pm-flag ready">${readyIds.length} ready</span>` : ''
  // 窗口 chip：立项来源窗口（窗口↔需求关联）+ 最近执行会话
  const timeLine = renderCardTime(req, now)
  const sessionChip = renderWindowChip(req, archived) + renderSessionChip(tasks, archived)
  const actions = cardActions(req)
  const artifactChips = renderArtifactChips(req)
  const confirmBtn = renderConfirmButton(req)
  const artifactDerived = renderArtifactDerived(req)

  return `
    <div class="dsh-pm-card${blocked ? ' is-blocked' : ''}${req.status === 'done' ? ' is-archived' : ''}" data-req="${esc(req.id)}" data-action="open-req">
      <div class="dsh-pm-card-top">
        <span class="dsh-pm-card-id">${esc(req.id)}</span>
        ${cat}${planChipHtml}${blockedChip}${pausedChip}${readyChip}${autoChip}
      </div>
      <div class="dsh-pm-card-title">${esc(req.title)}</div>
      <div class="dsh-pm-card-progress">
        <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${pct}%"></div></div>
        <span class="dsh-pm-card-pct">${progress(doneCount, totalCount)}</span>
        ${card.tokenTotal !== undefined ? `<span class="dsh-pm-token-badge" title="累计 Token（会话快照差值合计；口径见详情 Token tab）">🪙 ${esc(fmtTokens(card.tokenTotal))}</span>` : ''}
      </div>
      ${sub.subtasksTotal > 0 ? `<div class="dsh-pm-card-substat" title="父卡按依赖并行；子卡在父卡内串行">${esc(progressText(sub))}</div>` : ''}
      ${artifactChips}
      ${artifactDerived}
      ${timeLine}
      ${sessionChip}
      ${confirmBtn}
      ${req.autoRun !== undefined ? renderAutoControls(req) : ''}
      ${actions}
    </div>`
}

/**
 * 泳道卡面操作按钮 —— 状态推进不埋在详情页里（用户反馈「按钮太深」）。
 * 每个状态只给**下一步合法的人工操作**：闸门按钮本身就是闸门（人点 = 确认），
 * 非闸门态给便捷推进/退回。所有按钮自带 data-id，卡面直连 move-req
 * （不再依赖「当前处于详情态」）。
 */
export function cardActions(req: RequirementRecord): string {
  const btn = (to: RequirementStatus, label: string, opts?: { primary?: boolean; title?: string }): string => {
    const cls = opts?.primary === true ? 'dsh-pm-btn sm primary' : 'dsh-pm-btn sm'
    const title = opts?.title !== undefined ? ` title="${esc(opts.title)}"` : ''
    return `<button type="button" class="${cls}" data-action="move-req" data-to="${to}" data-id="${esc(req.id)}"${title}>${label}</button>`
  }
  let actions = ''
  // REQ-6f39b5：推进按钮统一为「→ [下一阶段]」格式，阶段名对齐 workflow-stages.md
  switch (req.status) {
    case 'draft':
      actions = btn('brainstorming', '→ 需求分析', { primary: true, title: '进入需求分析；窗口接手开工时会自动进入' })
        + btn('canceled', '取消', { title: '取消该需求（仅人可操作）' })
      break
    case 'brainstorming':
      actions = btn('design', '→ 设计', { primary: true, title: '方案谈定 → 进入设计阶段（计划在此阶段提交待人批准）' })
        + btn('draft', '退回', { title: '退回立项' })
        + btn('canceled', '取消', { title: '取消该需求（仅人可操作）' })
      break
    case 'design':
      actions = btn('decomposing', '→ 拆分', { primary: true, title: '计划获批后落库任务卡；未获批会被代码级拒绝' })
        + btn('brainstorming', '退回重谈', { title: '方案要改 → 退回需求分析' })
        + btn('canceled', '取消', { title: '取消该需求（仅人可操作）' })
      break
    case 'decomposing':
      actions = btn('implementing', '→ 实施', { primary: true, title: '进入实施；任务开工时系统会自动推进' })
        + btn('canceled', '取消', { title: '取消该需求（仅人可操作）' })
      break
    case 'implementing':
      actions = btn('accepting', '→ 验收', { primary: true, title: '进入验收；任务全部完成时系统会自动推进' })
        + btn('canceled', '取消', { title: '取消该需求（仅人可操作）' })
      break
    case 'accepting':
      // REQ-9f4a44：验收通过直接归档（accepting → archived），无 done 中转
      actions = btn('archived', '→ 归档', { primary: true, title: '验收通过并归档（归集文档）' })
        + btn('canceled', '取消', { title: '取消该需求（仅人可操作）' })
      break
    case 'done':
      // done 为 legacy 死状态（REQ_TRANSITIONS: done: []），历史记录只读，不给操作
      actions = ''
      break
    default:
      actions = ''
  }
  return actions.length === 0 ? '' : `<div class="dsh-pm-card-actions">${actions}</div>`
}


/** 卡面时间行：创建时间 + 当前状态进入时间 + 当前态停留时长（时间不埋在详情页）。 */
export function renderCardTime(req: RequirementRecord, now: number): string {
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

/* ------------------------------------------------------------------ 拆分计划 */

/**
 * 计划 chip（泳道卡面）：让「这份需求卡在等人批计划」在泳道上一眼可见，
 * 而不是要人点进详情页才发现。
 */
export function planChip(req: RequirementRecord): string {
  const plan = req.plan
  if (plan === undefined) return ''
  if (plan.approvedAt !== undefined) return '<span class="dsh-pm-flag plan-ok" title="拆分计划已批准，可拆分落库">计划已批</span>'
  if (plan.rejectedAt !== undefined) return '<span class="dsh-pm-flag plan-rejected" title="拆分计划被退回，待重写">计划被退</span>'
  return '<span class="dsh-pm-flag plan-pending" title="拆分计划已提交，等待人批准后才能拆分">计划待批</span>'
}

/**
 * 拆分计划区（plan mode 的人机界面）：人在这里**唯一**需要动手的地方——
 * 批准计划 = 批准拆分方案；退回 = 打回重写（必须给理由）。
 * 批准之后，拆分/实施/验收全部由窗口 agent 自行推进。
 */
export function renderPlanSection(req: RequirementRecord): string {
  const plan = req.plan
  if (plan === undefined) {
    return '<div class="dsh-pm-plan is-empty">尚未提交拆分计划。拆分计划在拆分（decomposing）阶段提交：窗口 agent 用 '
      + '<code>reqboard_submit(kind=plan)</code> 提交（decomposition.md + 摘要 + 任务表），'
      + '人在此处批准后才允许 <code>reqboard_decompose</code> 落库任务卡——'
      + '拆分的粒度在人点头之前就已写死在计划里。</div>'
  }
  const status = plan.approvedAt !== undefined
    ? '<span class="dsh-pm-plan-status" data-state="approved">已批准 ' + esc(fmtTime(plan.approvedAt)) + '</span>'
    : plan.rejectedAt !== undefined
      ? '<span class="dsh-pm-plan-status" data-state="rejected">已退回 ' + esc(fmtTime(plan.rejectedAt)) + '</span>'
      : '<span class="dsh-pm-plan-status" data-state="pending">待批准</span>'
  // 审批按钮已外置到详情头常驻操作条（renderActionBar）——折叠区只留状态与内容
  const actions = plan.approvedAt === undefined
    ? '<span class="dsh-pm-hint">计划待批：请在详情头「本阶段操作」条点「批准计划」或「退回计划」</span>'
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
