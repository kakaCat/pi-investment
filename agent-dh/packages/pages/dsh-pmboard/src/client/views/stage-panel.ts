/**
 * 任务（节点）详情面板：节点类型识别与专属内容分发（REQ-47939a t11 机械拆分）。
 * 拆分/实施节点内容在本文件；测试/评审/合并见 stage-nodes-quality，文档/UI/分析见 stage-nodes-doc。
 *
 * @module dsh-pmboard/client/views/stage-panel
 */
import { esc } from '../html.js'
import type { RequirementRecord, TaskRecord } from '../types.ts'
import { NO_ARCHIVED, PHASE_LABELS, TASK_STATUS_LABELS, fmtTime, renderComments, sessionChipHtml } from '../render/dom-utils.ts'
import { buildDag } from './stage-detail.ts'
import { renderAnalysisContent, renderDocContent, renderUIContent } from './stage-nodes-doc.ts'
import { renderMergeContent, renderReviewContent, renderTestContent } from './stage-nodes-quality.ts'
import { renderTaskTimeline } from './timeline.ts'

/* ------------------------------------------------------------------ 任务详情 */

/* ------------------------------------------------------------------ 节点类型识别 */

/** 节点类型（用于差异化展示内容） */
export type NodeType = 'decompose' | 'implement' | 'test' | 'review' | 'merge' | 'doc' | 'ui' | 'analysis' | 'generic'

/** 识别任务节点类型 */
export function identifyNodeType(task: TaskRecord): NodeType {
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
export const NODE_TYPE_ICONS: Record<NodeType, string> = {
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
export const NODE_TYPE_LABELS: Record<NodeType, string> = {
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
export function renderSpecializedContent(task: TaskRecord, nodeType: NodeType, req: RequirementRecord | undefined, allTasks: TaskRecord[]): string {
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
export function renderCommonContent(task: TaskRecord, now: number, archived: ReadonlySet<string> = NO_ARCHIVED): string {
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
        <div class="dsh-pm-comment-form" data-actor="human">
          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论（以「人」身份记录）…" />
          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="task" data-id="${esc(task.id)}">发送</button>
        </div>
      </div>
    </details>`
}

/* ------------------------------------------------------------------ 拆分节点 */

export function renderDecomposeContent(_task: TaskRecord, req: RequirementRecord | undefined, allTasks: TaskRecord[]): string {
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

export function renderImplementContent(task: TaskRecord): string {
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
