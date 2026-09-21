/**
 * 子卡链与自动链控制面（REQ-4842fe FR-1/FR-12 / t-3be71b）——**纯字符串渲染函数**，可单测。
 *
 * 两件事：
 *  ① 自动状态徽标：运行中 / 已暂停 / 熔断 / 手动（口径 = design/observability §2）；
 *  ② 父卡 → 子卡链：折叠展开（原生 <details>，零 JS）、stageKind 徽标 + attempt、
 *     父卡进度 = 子卡 done/total；**存量卡不出现子卡区**（外观与现状一致）。
 *
 * 纪律：缺省字段一律按"未开启/存量卡"处理——老台账读出来必须与现状同形
 * （autoRun/advance/parentId/stageKind 全部可缺省）。
 *
 * @module dsh-pmboard/client/render/subtask-view
 */
import { esc } from '../html.js'
import type { RequirementRecord, StageKind, TaskRecord } from '../types.ts'
import { STAGE_LABELS } from '../../domain/task/SubtaskTemplate.js'
import { fmt } from '../../domain/text/fmt.js'

/** 自动链徽标种类（四态；与 design/observability §2 的看板口径一一对应）。 */
export type AutoBadgeKind = 'running' | 'paused' | 'breaker' | 'manual'

export interface AutoBadge {
  kind: AutoBadgeKind
  label: string
  title: string
}

/**
 * stageKind → 中文：**复用 domain/task/SubtaskTemplate.ts 的 STAGE_LABELS**（单点，
 * 该处注释即写"单点避免前后端各写一份"）——client 只读这份纯数据，不另抄一份。
 */
export const stageKindLabel = (k: StageKind | undefined): string =>
  k === undefined ? '子卡' : STAGE_LABELS[k] ?? k

/**
 * 自动状态徽标（design/observability §2 口径）：
 *  - autoRun=true → 运行中；
 *  - autoRun=false 且暂停原因为停滞/失败 → 熔断（防无人值守烧 token）；
 *  - autoRun=false 其它 → 已暂停；
 *  - autoRun 缺省 → 手动（存量卡/人工流程）。
 */
export function autoBadgeOf(req: Pick<RequirementRecord, 'autoRun' | 'advance'>): AutoBadge {
  if (req.autoRun === true) {
    return { kind: 'running', label: '运行中', title: '自动链运行中：每完成一步自动触发下一步（点「暂停」可随时停）' }
  }
  if (req.autoRun === false) {
    const reason = req.advance?.pausedReason
    const streak = req.advance?.failureStreak ?? 0
    if (reason === 'stagnation' || reason === 'fail' || streak >= 3) {
      const why = reason === 'stagnation' ? '停滞' : reason === 'fail' ? '失败' : '熔断'
      return {
        kind: 'breaker',
        label: '熔断',
        title: fmt('连续失败/停滞达阈值已自动暂停（{why}），需人工处置后再继续', { why }),
      }
    }
    return { kind: 'paused', label: '已暂停', title: '自动链已暂停：不推下一张牌，已有状态不丢；点「继续」即续跑' }
  }
  return { kind: 'manual', label: '手动', title: '未开启自动链（存量卡/人工流程），外观与推进方式与改造前一致' }
}

/** 徽标 HTML。 */
export function renderAutoBadge(req: RequirementRecord): string {
  const b = autoBadgeOf(req)
  return `<span class="dsh-pm-auto-badge" data-auto="${b.kind}" title="${esc(b.title)}">${esc(b.label)}</span>`
}

/** 需求下某父卡的子卡链（按 stageKind 落库顺序 = 卡片 dependsOn 顺序稳定）。 */
export function subtaskChain(tasks: readonly TaskRecord[], parentId: string): TaskRecord[] {
  return tasks.filter(t => t.parentId === parentId)
}

/** 存在子卡 = 新式父卡（父卡自身只有 parentId 缺省，必须看台账才能判定）。 */
export function isParentTask(tasks: readonly TaskRecord[], t: TaskRecord): boolean {
  return t.parentId === undefined && tasks.some(x => x.parentId === t.id)
}

/** 存量卡（无 parentId 且无名下子卡）——外观与推进方式保持不变。 */
export function isLegacyTask(tasks: readonly TaskRecord[], t: TaskRecord): boolean {
  return t.parentId === undefined && !isParentTask(tasks, t)
}

export interface SubtaskProgress {
  parentsDone: number
  parentsTotal: number
  subtasksDone: number
  subtasksTotal: number
}

/** 进度口径（design/observability §2）：父卡 done/总（不含 canceled）+ 子卡 done/总。 */
export function subtaskProgress(tasks: readonly TaskRecord[]): SubtaskProgress {
  const subs = tasks.filter(t => t.parentId !== undefined)
  const parents = tasks.filter(t => t.parentId === undefined && subs.some(s => s.parentId === t.id))
  const live = <T extends { status: string }>(list: readonly T[]): T[] => list.filter(x => x.status !== 'canceled')
  const done = <T extends { status: string }>(list: readonly T[]) => list.filter(x => x.status === 'done').length
  return {
    parentsDone: done(live(parents)),
    parentsTotal: live(parents).length,
    subtasksDone: done(live(subs)),
    subtasksTotal: live(subs).length,
  }
}

/** 进度文案：无子卡时退回父卡口径（存量需求显示不变）。 */
export function progressText(p: SubtaskProgress): string {
  if (p.subtasksTotal === 0) return `父卡 ${p.parentsDone}/${p.parentsTotal}`
  return `父卡 ${p.parentsDone}/${p.parentsTotal} · 子卡 ${p.subtasksDone}/${p.subtasksTotal}`
}

/** 单张子卡行：stageKind 徽标 + attempt + 状态 + 标题。 */
export function renderSubtaskRow(t: TaskRecord): string {
  const attempt = t.attempt !== undefined && t.attempt > 0
    ? `<span class="dsh-pm-subtask-attempt" title="失败重跑次数">第 ${t.attempt + 1} 次</span>`
    : ''
  return `<div class="dsh-pm-subtask" data-task="${esc(t.id)}" data-action="open-task" data-status="${esc(t.status)}">
      <span class="dsh-pm-stage-badge" data-stage="${esc(t.stageKind ?? 'dev')}">${esc(stageKindLabel(t.stageKind))}</span>
      <span class="dsh-pm-subtask-title">${esc(t.title)}</span>
      ${attempt}
      <span class="dsh-pm-subtask-status" data-status="${esc(t.status)}">${esc(t.status)}</span>
    </div>`
}

/**
 * 父卡的子卡区（原生 <details> 折叠；默认展开——验收口径是"父卡展开显示子卡链与进度"）。
 * 存量卡返回空串（不出现子卡区）。
 */
export function renderSubtaskChain(tasks: readonly TaskRecord[], parent: TaskRecord, open = true): string {
  const chain = subtaskChain(tasks, parent.id)
  if (chain.length === 0) return ''
  const done = chain.filter(t => t.status === 'done').length
  return `<details class="dsh-pm-subtasks"${open ? ' open' : ''}>
      <summary data-action="toggle-subtasks">子卡链 ${done}/${chain.length}（dev→…→test 串行）</summary>
      ${chain.map(renderSubtaskRow).join('')}
    </details>`
}

/** 控制面按钮（暂停 / 继续 / 终止）——只在自动链开过（autoRun 有值）的需求上出现。 */
export function renderAutoControls(req: RequirementRecord): string {
  if (req.autoRun === undefined) return ''
  const id = esc(req.id)
  const btn = (action: string, label: string, title: string): string =>
    `<button type="button" class="dsh-pm-btn sm" data-action="${action}" data-id="${id}" title="${esc(title)}">${label}</button>`
  const running = req.autoRun === true
  return `<div class="dsh-pm-auto-controls">`
    + (running
      ? btn('auto-run-pause', '暂停', '停止推进下一张牌（已在跑的 run 允许跑完），状态不丢')
      : btn('auto-run-resume', '继续', '重新开启自动链并立即触发一次推进事件'))
    + btn('auto-run-stop', '终止', '暂停自动链；在跑/待跑的卡需人工取消（取消是人工闸门）')
    + `</div>`
}
