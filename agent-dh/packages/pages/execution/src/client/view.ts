/**
 * Board view construction + data renderers. Pure DOM port of the former
 * execution.html page logic: one container skeleton built once, per-section
 * renderers fill it from a fresh /dashboard/api/board fetch. Class names are
 * all dsh-exec-* (see styles.ts).
 *
 * @module dashboard-execution/client/view
 */
import type { BoardData } from './types.ts'

function esc(s: unknown): string {
  if (s === null || s === undefined) return ''
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
function fmtTs(ts: unknown): string {
  if (!ts) return '—'
  const t = String(ts).includes(' ') ? String(ts).replace(' ', 'T') : String(ts)
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return esc(ts)
  const p = (n: number) => (n < 10 ? '0' : '') + n
  return p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes())
}
function fmtUptime(s: unknown): string {
  const v = Number(s)
  if (!Number.isFinite(v) || v < 0) return s === undefined || s === null ? '—' : String(s)
  const d = Math.floor(v / 86400)
  const h = Math.floor((v % 86400) / 3600)
  const m = Math.floor((v % 3600) / 60)
  if (d > 0) return d + 'd ' + h + 'h'
  if (h > 0) return h + 'h ' + m + 'm'
  return m + 'm'
}
function fmtMetric(key: string, val: unknown): string {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'boolean') return val ? '是' : '否'
  if (typeof val === 'number') {
    if (key === 'uptime_s') return fmtUptime(val)
    if (Math.abs(val) >= 100000) return val.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
    return String(Math.round(val * 100) / 100)
  }
  return esc(val)
}

const CP_ZH: Record<string, string> = { confirmed: '已确认', failed: '失败', late: '晚点', pending: '等待', off_day: '非执行日', unknown: '未知' }
const H_ZH: Record<string, string> = { ok: '正常', degraded: '降级', failed: '故障' }
const RUN_ZH: Record<string, string> = { success: '成功', failed: '失败', pending: '待运行', unknown: '未知' }
const HEALTH_NAME: Record<string, string> = {
  'quantsys-v2': '量化后端 quantsys-v2',
  'agent-os': 'Agent OS (v1 遗留)',
  postgres: 'PostgreSQL (经 v2 代理)',
  'agent-dh': 'Agent-DH 进程(本看板宿主)',
}
const METRIC_ZH: Record<string, string> = {
  api: 'API', db: 'DB', db_connected: 'db_connected', holdings_count: '持仓数',
  model_loaded: '模型加载', balance_date: '结算日', total_assets: '总资产',
  status: 'status', via: 'via', uptime_s: '运行时长', rss_mb: 'RSS(MB)',
  heap_mb: 'Heap(MB)', restarts: '重启次数', probe_ms: '探测耗时',
}
const GROUP_ZH: Record<string, string> = {
  engine_m0: 'ENGINE · M0 数据地基 / M1 市场感知 / M2 股票池 / M3 信号执行',
  engine_m46: 'ENGINE · M4 风控 / M5 交易对账 / M6 经验沉淀',
  autonomy: 'AUTONOMY · L1 策略验证 / L2 蒸馏 / L3 裁决 / L4 周报',
}
const STATUS_DOT: Record<string, string> = { ok: 'ok', confirmed: 'confirmed', failed: 'failed', late: 'late', pending: 'pending', unknown: 'unknown', off_day: 'off_day', degraded: 'degraded', success: 'ok' }

/** Build the board skeleton once; returns section root elements. */
export interface ViewRefs {
  board: HTMLElement
  meta: HTMLElement
  banner: HTMLElement
  healthGrid: HTMLElement
  alertsSec: HTMLElement
  alertsBox: HTMLElement
  gridM0M3: HTMLElement
  gridM4M6: HTMLElement
  gridL: HTMLElement
  errList: HTMLElement
  timelineBox: HTMLElement
  taskTable: HTMLTableElement
}
export function buildView(): ViewRefs {
  const board = document.createElement('div')
  board.className = 'dsh-exec-board'
  board.dataset.dshExecView = ''
  board.innerHTML = `
<div class="dsh-exec-wrap">
  <div class="dsh-exec-head">
    <h1 class="dsh-exec-title">双线执行确认看板<small>engine(M0–M6) × autonomy(L1–L4)</small></h1>
    <div class="dsh-exec-meta">
      <span class="dsh-exec-legend">
        <span class="dsh-exec-lg"><i class="dsh-exec-dot confirmed"></i>已确认</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot pending"></i>等待</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot late"></i>晚点</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot failed"></i>失败</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot unknown"></i>未知</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot off_day"></i>非执行日</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot degraded"></i>降级</span>
      </span>
      <span class="dsh-exec-last" data-role="lastFetch">—</span>
      <button class="dsh-exec-btn" data-role="refresh">立即刷新</button>
    </div>
  </div>
  <div class="dsh-exec-banner" data-role="banner"></div>
  <div class="dsh-exec-sec"><h2>系统健康</h2><div class="dsh-exec-grid4" data-role="health"></div></div>
  <div class="dsh-exec-sec" data-role="alertsSec" style="display:none"><h2>阻断告警<span class="sub">failed/late 且声明阻断下游</span></h2><div data-role="alerts"></div></div>
  <div class="dsh-exec-sec"><h2>执行检查点<span class="sub">状态语义：expectTime + 宽限(默认30min) 窗口内展示等待，绝不误报失败</span></h2>
    <div class="dsh-exec-group-title">${GROUP_ZH.engine_m0}</div><div class="dsh-exec-cp-grid" data-role="cpM0M3"></div>
    <div class="dsh-exec-group-title">${GROUP_ZH.engine_m46}</div><div class="dsh-exec-cp-grid" data-role="cpM4M6"></div>
    <div class="dsh-exec-group-title">${GROUP_ZH.autonomy}</div><div class="dsh-exec-cp-grid" data-role="cpL"></div>
  </div>
  <div class="dsh-exec-sec"><h2>错误事件流<span class="sub">v2/os/dsh 日志尾部近 10 条（ERROR/CRITICAL/Traceback）</span></h2>
    <ol class="dsh-exec-errs" data-role="errors"></ol></div>
  <div class="dsh-exec-sec"><h2>今日时间轴<span class="sub">真实 cron 计划 × 当日运行结果</span></h2>
    <div class="dsh-exec-timeline" data-role="timeline"></div></div>
  <div class="dsh-exec-sec"><h2>调度任务明细<span class="sub">全部任务</span></h2>
    <table class="dsh-exec-table"><thead><tr>
      <th>ID</th><th>任务</th><th>启用</th><th>计划(cron)</th><th>下次运行</th><th>今日</th><th>最近一次运行</th><th>错误详情</th>
    </tr></thead><tbody data-role="tasks"></tbody></table>
  </div>
</div>`
  const $ = <T extends HTMLElement>(sel: string) => board.querySelector<T>(sel) as T
  return {
    board,
    meta: $('[data-role="lastFetch"]'),
    banner: $('[data-role="banner"]'),
    healthGrid: $('[data-role="health"]'),
    alertsSec: $('[data-role="alertsSec"]'),
    alertsBox: $('[data-role="alerts"]'),
    gridM0M3: $('[data-role="cpM0M3"]'),
    gridM4M6: $('[data-role="cpM4M6"]'),
    gridL: $('[data-role="cpL"]'),
    errList: $('[data-role="errors"]'),
    timelineBox: $('[data-role="timeline"]'),
    taskTable: $('table'),
  }
}

export function renderHealth(refs: ViewRefs, data: BoardData): void {
  const rows = data.health ?? []
  refs.healthGrid.innerHTML = rows.map((h) => {
    const nm = HEALTH_NAME[h.name ?? ''] ?? h.name ?? '?'
    const st = H_ZH[h.status ?? ''] ?? h.status ?? '?'
    const port = h.port ? '<span class="port">:' + h.port + '</span>' : ''
    const kv = (h.metrics ? Object.keys(h.metrics) : []).filter((k) => k !== 'probe_ms')
      .map((k) => '<div><span>' + esc(METRIC_ZH[k] ?? k) + '</span><b>' + fmtMetric(k, h.metrics![k]) + '</b></div>').join('')
    const err = h.error ? '<div class="dsh-exec-errline">' + esc(h.error) + '</div>' : ''
    const rt = h.responseTimeMs !== undefined ? '<div class="dsh-exec-time">探测 ' + h.responseTimeMs + 'ms</div>' : ''
    return '<div class="dsh-exec-card"><h3><i class="dsh-exec-dot ' + esc(h.status) + '"></i>' + esc(nm) + port +
      '<span class="' + esc(h.status) + '" style="margin-left:auto">' + esc(st) + '</span></h3>' +
      '<div class="dsh-exec-kv">' + kv + '</div>' + err + rt + '</div>'
  }).join('')
  if (rows.length === 0) refs.healthGrid.innerHTML = '<div class="dsh-exec-card dsh-exec-dim">无健康数据</div>'
}

export function renderAlerts(refs: ViewRefs, data: BoardData): void {
  const list = data.blockedFlows ?? []
  if (list.length === 0) { refs.alertsSec.style.display = 'none'; return }
  refs.alertsSec.style.display = ''
  const zh: Record<string, string> = { failed: '失败', late: '晚点' }
  refs.alertsBox.innerHTML = '<div class="dsh-exec-alert-card">' + list.map((b) =>
    '<div class="dsh-exec-alert-item"><span class="' + esc(b.status) + '">' + esc(b.checkpointName) +
    '（' + esc(zh[b.status ?? ''] ?? b.status) + '）</span>' +
    '<span class="dsh-exec-dim">阻断下游：</span><span class="flow">' + (b.blocks ?? []).map(esc).join(' · ') + '</span></div>'
  ).join('') + '</div>'
}

export function renderCheckpoints(refs: ViewRefs, data: BoardData): void {
  const list = data.checkpoints ?? []
  const groups: Record<string, typeof list> = { m0m3: [], m46: [], l: [] }
  for (const cp of list) {
    const isEngine = cp.line === 'engine'
    const mod = cp.module ?? ''
    if (isEngine && /^M[0-3]/.test(mod)) groups.m0m3.push(cp)
    else if (isEngine && /^M[4-6]/.test(mod)) groups.m46.push(cp)
    else groups.l.push(cp)
  }
  const cardCp = (cp: (typeof list)[number]) => {
    const zh = CP_ZH[cp.status ?? ''] ?? cp.status ?? '?'
    const dot = STATUS_DOT[cp.status ?? ''] ?? cp.status
    const msg = cp.message ? '<div class="msg">' + esc(cp.message) + '</div>' : ''
    return '<div class="dsh-exec-cp" title="' + esc(cp.id) + '"><div class="top">' +
      '<i class="dsh-exec-dot ' + esc(dot) + '"></i><span class="mod">' + esc(cp.module ?? '') + '</span>' +
      '<span class="' + esc(dot) + '">' + esc(zh) + '</span></div>' +
      '<div class="nm">' + esc(cp.name ?? '') + '</div>' + msg + '</div>'
  }
  refs.gridM0M3.innerHTML = groups.m0m3.map(cardCp).join('') || '<div class="dsh-exec-empty">无</div>'
  refs.gridM4M6.innerHTML = groups.m46.map(cardCp).join('') || '<div class="dsh-exec-empty">无</div>'
  refs.gridL.innerHTML = groups.l.map(cardCp).join('') || '<div class="dsh-exec-empty">无</div>'
}

export function renderErrors(refs: ViewRefs, data: BoardData): void {
  const list = data.errors ?? []
  refs.errList.innerHTML = list.map((e) =>
    '<li><span class="src ' + esc(e.source ?? '') + '">' + esc(e.source ?? '?') + '</span>' +
    '<span class="file">' + esc(e.file ?? '') + '</span>' +
    '<span class="line" title="' + esc(e.line) + '">' + esc(e.line ?? '') + '</span></li>'
  ).join('') || '<li class="dsh-exec-empty">近 300 行日志内无错误事件</li>'
}

export function renderTimeline(refs: ViewRefs, data: BoardData): void {
  const list = data.timeline ?? []
  const dotFor = (st: string) => (st === 'success' ? 'ok' : st === 'failed' ? 'failed' : st === 'unknown' ? 'unknown' : 'pending')
  refs.timelineBox.innerHTML = list.map((t) => {
    const zh = RUN_ZH[t.status ?? ''] ?? t.status ?? '?'
    return '<div class="dsh-exec-tl"><i class="dsh-exec-dot ' + dotFor(t.status ?? '') + '"></i>' +
      '<span class="t">' + esc(t.expectedTime ?? '') + '</span>' +
      '<span class="e">' + esc(t.taskName ?? '') + '</span>' +
      '<span class="' + dotFor(t.status ?? '') + '">' + esc(zh) + '</span></div>'
  }).join('') || '<div class="dsh-exec-empty">无</div>'
}

export function renderTasks(refs: ViewRefs, data: BoardData): void {
  const list = data.tasks ?? []
  refs.taskTable.tBodies[0].innerHTML = list.map((t) => {
    const enabled = t.enabled === true || t.enabled === 'true'
    const on = enabled ? '<span class="dsh-exec-on">是</span>' : '<span class="dsh-exec-off">否</span>'
    const today = (t.todaySuccess !== undefined && t.todayTriggered !== undefined)
      ? String(t.todaySuccess ?? 0) + '/' + String(t.todayTriggered ?? 0)
      : '—'
    const lastRun = typeof t.lastRun === 'string' ? t.lastRun : t.lastRun ? JSON.stringify(t.lastRun) : '—'
    const nextRun = t.nextRunAt && t.nextRunAt !== 'None' ? fmtTs(t.nextRunAt) : '—'
    const err = t.error ? '<td class="err">' + esc(t.error) + '</td>' : '<td class="dim">—</td>'
    return '<tr><td class="id">' + esc(t.id) + '</td><td>' + esc(t.name ?? '') + '</td>' +
      '<td>' + on + '</td><td class="mono">' + esc(t.scheduleExpr ?? '') + '</td>' +
      '<td class="num">' + nextRun + '</td><td class="num">' + today + '</td>' +
      '<td class="num">' + fmtTs(lastRun) + '</td>' + err + '</tr>'
  }).join('') || '<tr><td colspan="8" class="dsh-exec-empty">无</td></tr>'
}

export function renderAll(refs: ViewRefs, data: BoardData): void {
  renderHealth(refs, data)
  renderAlerts(refs, data)
  renderCheckpoints(refs, data)
  renderErrors(refs, data)
  renderTimeline(refs, data)
  renderTasks(refs, data)
}
export { esc, fmtTs }
