/**
 * 文档记录区块 + 验收/归档区块渲染（REQ-47939a t11 从 view.ts 机械拆分）。
 *
 * @module dsh-pmboard/client/views/verification
 */
import { esc } from '../html.js'
import type { ArchiveRecord, RequirementRecord } from '../types.ts'
import type { StageKey } from '../../shared/protocol.ts'
import { ALL_STAGE_KEYS } from '../../shared/protocol.ts'
import { fmtTime } from '../render/dom-utils.ts'

/* ------------------------------------------------------------------ 文档记录 */

/** 文档类型 → 图标 + 标签（需求详情页「文档」区块用） */
export const DOC_KIND_META: Record<string, { icon: string; label: string }> = {
  requirement: { icon: '📄', label: '需求文档' },
  ui: { icon: '🎨', label: 'UI 文档' },
  proposal: { icon: '📐', label: '设计文档' },
  plan: { icon: '📝', label: '拆分计划（旧版）' },
  decomposition: { icon: '🧩', label: '拆分计划' },
  design: { icon: '📐', label: '设计文档' },
  task_detail: { icon: '🗂️', label: '任务卡' },
  verification: { icon: '✅', label: '验收材料' },
  archive: { icon: '📦', label: '归档材料' },
  retro: { icon: '🔁', label: '复盘' },
  notes: { icon: '📒', label: '其他' },
}

/** 产物 stage 的流水线序（未知/缺省排在最后，不改变其余相对顺序）。 */
export function stageRankOf(stage: StageKey | string | undefined): number {
  const idx = stage === undefined ? -1 : (ALL_STAGE_KEYS as readonly string[]).indexOf(stage)
  return idx < 0 ? ALL_STAGE_KEYS.length : idx
}

/**
 * 收集需求关联的全部文档，去重。
 *
 * 来源与顺序（REQ-31e11f #6/#7：立项过程的文件必须全部进文档区）：
 *   ① req.artifacts（t4 登记的节点产物：requirement/plan/decomposition/task_detail/verification/archive）
 *      —— 按 stage 流水线顺序排列，这样 requirement.md → plan.md → decomposition.md →
 *      tasks/*.md → verification.md → archive 在文档区一眼连成一条链；
 *   ② docLinks（requirement/ui/proposal）；
 *   ③ plan.path（拆分计划文档）；
 *   ④ archive.docs（归档文档清单）。
 * 路径去重：同一文件既登记产物又出现在 docLinks/archive 时只展示一次（保留首次出现的口径）。
 */
export function collectReqDocs(req: RequirementRecord): Array<{ icon: string; label: string; path: string }> {
  const docs: Array<{ icon: string; label: string; path: string }> = []
  const seen = new Set<string>()
  const push = (kind: string, path: string): void => {
    const p = (path ?? '').trim()
    if (!p || seen.has(p)) return
    seen.add(p)
    const meta = DOC_KIND_META[kind]
    // REQ-f0579a t2：label = 种类可读名 · 文件名——af8a2ac0 要求显示文档真名
    // （追溯链不再四份全叫「设计文档」），board-info-fixes 契约要求种类可读名；两者双呈现。
    const fileName = p.split('/').pop() || p
    const kindLabel = meta?.label ?? kind
    docs.push({ icon: meta?.icon ?? '📒', label: kindLabel + ' · ' + fileName, path: p })
  }
  // ① 节点产物（t4 登记的 pipeline 产物），按 stage 顺序
  const artifacts = [...(req.artifacts ?? [])]
    .sort((a, b) => stageRankOf(a.stage) - stageRankOf(b.stage))
  for (const a of artifacts) push(a.kind, a.path)
  // ② 需求文档 / UI 文档 / 设计文档（docLinks）
  if (req.docLinks?.requirement) push('requirement', req.docLinks.requirement)
  if (req.docLinks?.ui) push('ui', req.docLinks.ui)
  if (req.docLinks?.proposal) push('proposal', req.docLinks.proposal)
  // REQ-6f39b5：extras 额外成果文件（如 HTML 原型——关键成果必须可见）
  for (const e of req.docLinks?.extras ?? []) {
    const p = (e.path ?? '').trim()
    if (!p || seen.has(p)) continue
    seen.add(p)
    docs.push({ icon: '🎁', label: e.label || '成果文件', path: p })
  }
  // ③ 拆分计划（plan.path）
  if (req.plan?.path) push('plan', req.plan.path)
  // ④ 归档文档清单（archive.docs）
  for (const d of req.archive?.docs ?? []) push(d.kind, d.path)
  return docs
}

/** 渲染「文档」区块：该需求关联的需求文档/UI 文档/设计文档/计划/验收/复盘等。 */
export function renderDocSection(req: RequirementRecord): string {
  const docs = collectReqDocs(req)
  if (docs.length === 0) {
    return '<div class="dsh-pm-empty">暂无文档记录。窗口 agent 可用 <code>reqboard_archive_submit</code> 提交文档清单，或通过需求更新接口填充 docLinks（requirement/ui/proposal）。</div>'
  }
  return '<ul class="dsh-pm-doc-list">' + docs.map(d =>
    '<li data-doc-path="' + esc(d.path) + '">'
    + '<span class="dsh-pm-doc-icon">' + d.icon + '</span>'
    + '<span class="dsh-pm-doc-label">' + esc(d.label) + '</span>'
    + '<button type="button" class="dsh-pm-doc-path" data-action="open-doc" data-path="' + esc(d.path) + '">' + esc(d.path) + '</button>'
    + '</li>'
  ).join('') + '</ul>'
}

/* ------------------------------------------------------------------ 验收 / 归档 */

/** 卡面：待人工审核 / 待归档 —— 让"卡在人这里"一眼可见。 */
export function verifyChip(req: RequirementRecord): string {
  if (req.status !== 'accepting') return ''
  const v = req.verification
  return v === undefined
    ? '<span class="dsh-pm-flag verify-pending" title="验收态但还没提交验收材料">待验收材料</span>'
    : '<span class="dsh-pm-flag verify-pending" title="验收材料已提交，等人工审核">待人工审核</span>'
}

export function archiveChip(req: RequirementRecord): string {
  if (req.status !== 'done') return ''
  return req.archive === undefined
    ? '<span class="dsh-pm-flag archive-pending" title="已完成，等窗口准备归档材料">待归档材料</span>'
    : '<span class="dsh-pm-flag archive-pending" title="归档材料已备，等人点归档">待归档</span>'
}

/**
 * 验收区：agent 提交的证据 + 人工审核入口。
 * 人在这里做的事只有一件——**看着证据**点通过或退回（返工必须写意见）。
 */
export function renderVerifySection(req: RequirementRecord): string {
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
  // 裁决按钮已外置到详情头常驻操作条（renderActionBar）
  const actions = req.status === 'accepting'
    ? '<span class="dsh-pm-hint">请在详情头「本阶段操作」条点「验收通过」或「退回返工」</span>'
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
export function renderArchiveSection(req: RequirementRecord): string {
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
  // 归档按钮已外置到详情头常驻操作条（renderActionBar）
  const actions = req.status === 'done' && a.archivedAt === undefined
    ? '<span class="dsh-pm-hint">请在详情头「本阶段操作」条点「归档」</span>'
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
    + renderManualUpdates(a)
    + '</div>'
}

export const ARCHIVE_DOC_KIND_LABELS: Record<string, string> = {
  requirement: '需求说明', plan: '拆分计划', verification: '验收材料', retro: '复盘', notes: '其他',
}

/** 说明书更新点（金字塔 L1/L2）：归档让项目认知怎么长上去的。 */
export function renderManualUpdates(a: ArchiveRecord): string {
  const updates = a.manualUpdates ?? []
  if (updates.length === 0) {
    return a.manualNote !== undefined
      ? '<div class="dsh-pm-doc-group"><span class="dsh-pm-hint">项目说明书更新</span><div class="dsh-pm-block-summary">无（' + esc(a.manualNote) + '）</div></div>'
      : ''
  }
  const items = updates.map(u =>
    '<li><code>' + esc(u.path) + '</code><span class="dsh-pm-doc-kind">' + esc(u.section) + '</span><span>' + esc(u.summary) + '</span></li>').join('')
  return '<div class="dsh-pm-doc-group"><span class="dsh-pm-hint">项目说明书更新（金字塔向上生长）</span>'
    + '<ul class="dsh-pm-doc-list">' + items + '</ul></div>'
}