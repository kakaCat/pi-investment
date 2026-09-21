/**
 * 工具结果人话摘要（REQ-c48f99 t4 / FR-5）——每个工具一句 summarize，
 * 供 renderSmart 输出「首行中文摘要 + JSON 明细」。
 *
 * 契约：输入为工具返回值（unknown，错误时可能是字符串）；输出必须是单行
 * （renderSmart 会再截一次，但作者须保证语义在行首）。所有函数对任何输入
 * 不 throw——失败时降级为通用前缀 + JSON 由明细区兜底。
 * @module dsh-pmboard/tools/render-summaries
 */

import { fmt } from '../domain/text/fmt.js'

type V = Record<string, unknown>
const asObj = (v: unknown): V | undefined =>
  typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as V) : undefined
const s = (v: unknown): string | undefined => (typeof v === 'string' && v !== '' ? v : undefined)
const n = (v: unknown): number | undefined => (typeof v === 'number' && Number.isFinite(v) ? v : undefined)
const err = (v: unknown): string | undefined => (typeof v === 'string' && v !== '' ? '❌ ' + v.slice(0, 80) : undefined)

const MOVE_TO: Readonly<Record<string, string>> = {
  in_progress: '开工', testing: '送测', integrating: '联调', in_review: '送审',
  done: '完工', todo: '退回', canceled: '取消',
}
const SUBMIT_KIND_CN: Readonly<Record<string, string>> = {
  requirement: '需求文档', plan: '拆分计划', verification: '验收材料', archive: '归档材料',
}

/** reqboard_task_move：✅ t-xxx 完工（in_review → done） */
export function taskMoveSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 任务推进（结果形态未知）'
  if (o.success === false) return fmt('❌ 任务推进被拒：{note}', { note: (s(o.note) ?? s(o.warning) ?? '见明细').slice(0, 60) })
  const id = s(o.task_id) ?? '?'
  const from = s(o.from); const to = s(o.to)
  const cn = (k: string | undefined) => (k !== undefined ? MOVE_TO[k] ?? k : '?')
  return `✅ ${id} ${cn(to)}${from !== undefined ? `（${cn(from)} → ${cn(to)}）` : ''}`
}

/** reqboard_submit：📄 REQ-xxx 提交验收材料 → accepting */
export function submitSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 提交产物（结果形态未知）'
  if (o.success === false) return fmt('❌ 提交被拒：{note}', { note: (s(o.note) ?? s(o.warning) ?? '见明细').slice(0, 60) })
  const reqId = s(o.requirement_id) ?? '?'
  const status = s(o.status) ?? s(o.plan_status)
  const kind = s(o.artifact && typeof o.artifact === 'object' ? (o.artifact as V).kind : undefined)
  const tc = n(o.task_count)
  return `📄 ${reqId} 提交${kind !== undefined ? SUBMIT_KIND_CN[kind] ?? kind : '产物'}${status !== undefined ? ` → ${status}` : ''}${tc !== undefined ? `（${tc} 个任务）` : ''}`
}

/** reqboard_status：📊 看板：1 个进行中需求（REQ-x implementing） */
export function statusSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 看板状态（结果形态未知）'
  if (o.bound !== true) return '📊 看板：未绑定需求'
  const count = n(o.open_count) ?? 0
  const reqs = Array.isArray(o.open_requirements) ? (o.open_requirements as V[]) : []
  const first = reqs[0]
  const tag = first !== undefined ? `（${s(first.id) ?? '?'} ${s(first.status) ?? ''}）` : ''
  return `📊 看板：${count} 个进行中需求${tag}`
}

/** reqboard_capture：🌱 立项 REQ-xxx · 需求名（feature/standard） */
export function captureSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 立项（结果形态未知）'
  const reqId = s(o.requirement_id)
  if (reqId === undefined || reqId === '') return fmt('🌱 立项弹框未创建（{note}）', { note: (s(o.note) ?? '见明细').slice(0, 50) })
  const answers = asObj(o.answers)
  const title = s(answers?.title)
  const cat = s(answers?.category); const diff = s(answers?.difficulty)
  return `🌱 立项 ${reqId}${title !== undefined ? ` · ${title}` : ''}${cat !== undefined ? `（${cat}${diff !== undefined ? '/' + diff : ''}）` : ''}`
}

/** reqboard_create：🌱 创建需求 REQ-xxx · 标题 */
export function createSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 创建需求（结果形态未知）'
  const reqId = s(o.requirement_id) ?? '?'
  const title = s(o.title)
  const status = s(o.status)
  return `🌱 创建需求 ${reqId}${title !== undefined ? ` · ${title.slice(0, 40)}` : ''}${status !== undefined ? `（${status}）` : ''}`
}

/** reqboard_ask_confirm：🔔 已确认并推进 design → decomposing / 未确认（用户意见） */
export function askConfirmSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 确认弹框（结果形态未知）'
  if (o.confirmed === true) {
    const from = s(o.from); const to = s(o.to)
    return `🔔 已确认${o.advanced === true && from !== undefined && to !== undefined ? `并推进 ${from} → ${to}` : ''}`
  }
  const choice = s(o.user_choice) ?? s(o.user_feedback)
  return `🔔 未确认${choice !== undefined ? `：${choice.slice(0, 50)}` : ''}`
}

/** reqboard_decompose：🧩 拆分落库 7 个任务 */
export function decomposeSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 拆分（结果形态未知）'
  if (o.success === false) return fmt('❌ 拆分被拒：{note}', { note: (s(o.note) ?? '见明细').slice(0, 60) })
  const created = Array.isArray(o.created) ? o.created.length : 0
  return `🧩 拆分落库 ${created} 个任务${s(o.requirement_status) !== undefined ? ` → ${s(o.requirement_status)}` : ''}`
}

/** reqboard_move：🔀 REQ-xxx design → decomposing */
export function moveSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 需求推进（结果形态未知）'
  if (o.success === false) return fmt('❌ 需求推进被拒：{note}', { note: (s(o.note) ?? '见明细').slice(0, 60) })
  const reqId = s(o.requirement_id) ?? '?'
  const from = s(o.from); const to = s(o.to)
  return `🔀 ${reqId}${from !== undefined && to !== undefined ? ` ${from} → ${to}` : ''}`
}

/** reqboard_task_report：📝 t-xxx 完工汇报已登记（第 N 段） */
export function taskReportSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 任务汇报（结果形态未知）'
  const id = s(o.task_id) ?? '?'
  const idx = n(o.report_index)
  return `📝 ${id} 汇报已登记${idx !== undefined ? `（第 ${idx} 段）` : ''}`
}

/** reqboard_accept_sheet：✅ 验收单：本批通过 3/5，剩余 2 项 */
export function acceptSheetSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 验收单（结果形态未知）'
  if (o.archived === true) return '✅ 验收全过，需求已归档'
  const recorded = n(o.recorded) ?? 0
  const passed = n(o.passed) ?? 0
  const pending = n(o.pending) ?? 0
  return `✅ 验收单：本批 ${passed}/${recorded} 通过${pending > 0 ? `，剩余 ${pending} 项` : ''}`
}

/** reqboard_task_status：📋 t-xxx in_progress（进度 60%） */
export function taskStatusSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 任务状态（结果形态未知）'
  const id = s(o.task_id) ?? '?'
  const status = s(o.status) ?? '?'
  const progress = n(o.progress)
  return `📋 ${id} ${status}${progress !== undefined ? `（进度 ${progress}%）` : ''}`
}

/** reqboard_task_run：▶️ 推进 t-xxx：执行子任务 / 停链原因 */
export function taskRunSummary(v: unknown): string {
  const e = err(v); if (e !== undefined) return e
  const o = asObj(v)
  if (o === undefined) return '⚙️ 推进执行链（结果形态未知）'
  if (o.success === false) return fmt('❌ 推进失败：{note}', { note: (s(o.error) ?? s(o.stopped) ?? '见明细').slice(0, 60) })
  const id = s(o.task_id) ?? '?'
  const sub = asObj(o.subtask_executed)
  const subTag = sub !== undefined ? `子卡 ${s(sub.id) ?? '?'}` : '无 ready 子卡'
  return `▶️ ${id}：${subTag}${s(o.parent_status) !== undefined ? `（父卡 ${s(o.parent_status)}）` : ''}`
}

/** reqboard_task_execute（task_run 兼容别名）：同 taskRunSummary。 */
export const taskExecuteSummary = taskRunSummary
