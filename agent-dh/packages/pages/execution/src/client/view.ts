/**
 * Board view construction + data renderers. Light monitoring theme per design
 * page2-execution-board.html: header, execution summary (今日计划/已完成/失败/待执行),
 * pipeline bands (ENGINE M0-M6 x AUTONOMY L1-L4), today timeline (HH:MM sorted),
 * scheduler tasks grouped into 6 domains (success/failure only, no technical noise).
 *
 * @module dashboard-execution/client/view
 */
import type { BoardData, CheckpointResult, SchedulerTask, TimelineEntry } from './types.ts'

function esc(s: unknown): string {
  if (s === null || s === undefined) return ''
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
function shortDT(s: unknown): string {
  if (!s) return '—'
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
  if (!m) return esc(s).slice(0, 5)
  const now = new Date()
  const pad = (n: number): string => (n < 10 ? '0' : '') + n
  const today = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate())
  const hm = m[4] + ':' + m[5]
  return (m[1] + '-' + m[2] + '-' + m[3] === today ? '' : m[2] + '-' + m[3] + ' ') + hm
}
function hmMin(s: unknown): number {
  const m = String(s ?? '').match(/^(\d{2}):(\d{2})/)
  if (!m) return 9999
  return Number(m[1]) * 60 + Number(m[2])
}
function trunc(s: unknown, n: number): string {
  const t = String(s ?? '').trim()
  return t.length <= n ? t : t.slice(0, n) + '…'
}

/* ---- 文案映射 ---- */
const TL_ZH: Record<string, string> = {
  success: '成功', failed: '失败', pending: '待执行', skipped: '已跳过', unknown: '未知',
}
const TL_IC: Record<string, string> = { success: '✅', failed: '❌', pending: '⏳', skipped: '⏭️', unknown: '❔' }
const TL_TAG: Record<string, string> = { success: 'ok', failed: 'bad', pending: 'wait', skipped: 'wait', unknown: 'unk' }
const CP_ZH: Record<string, string> = { confirmed: '已确认', pending: '等待', off_day: '非执行日', failed: '失败', late: '晚点', degraded: '降级', unknown: '未知' }
const CP_DOT: Record<string, string> = { confirmed: 'ok', pending: 'wait', off_day: 'off', failed: 'bad', late: 'late', degraded: 'deg', unknown: 'unk' }
const H_ZH: Record<string, string> = { ok: '正常', degraded: '降级', failed: '故障', unknown: '未知' }
const H_DOT: Record<string, string> = { ok: 'ok', degraded: 'deg', failed: 'bad', unknown: 'unk' }
const HEALTH_NAME: Record<string, string> = {
  'quantsys-v2': '量化后端 quantsys-v2',
  'agent-os': 'Agent OS',
  postgres: '数据库 PostgreSQL',
  'agent-dh': 'Agent-DH 宿主',
}
const TASK_ZH: Record<string, string> = {
  market_daily_snapshot: '每日市场快照', chan_scan_daily: '产业链链扫', 'chan-scan-daily': '产业链链扫',
  v13_risk_check: '风控熔断检查', 'v13-risk-check': '风控熔断检查',
  daily_trade_verify: '交易对账', signal_perf_backfill_daily: '信号表现回填', 'signal-perf-backfill-daily': '信号表现回填',
  v13_weekly_report: '每周报告', 'v13-weekly-report': '每周报告(v13)',
  market_style_update: '市场风格更新', 'market-style-update': '市场风格更新',
  v13_simulation_trading: '模拟交易执行', 'v13-simulation-trading': '模拟交易执行',
  v13_verification: '策略验证裁决', 'v13-verification': '策略验证裁决',
  pre_market_scan: '盘前扫描', 'pre-market-scan': '盘前扫描',
  weekly_strategy_discovery: '周度策略发现', 'weekly-strategy-discovery': '周度策略发现',
  daily_strategy_validation: '策略日验证', 'daily-strategy-validation': '策略日验证',
  daily_pool_refresh: '股票池刷新', 'daily-pool-refresh': '股票池刷新',
  fund_flow_update: '资金流数据更新', chan_knowledge_distill_weekly: '知识蒸馏(周)',
  'chan-knowledge-distill-weekly': '知识蒸馏(周)',
  '每日数据更新': '每日数据更新', '每日数据质量检查': '每日数据质量检查', '每周财务数据更新': '每周财务数据更新',
  '每日财报时效性检查': '每日财报时效性检查', '每日信号生成': '每日信号生成', '每日信号执行': '每日信号执行', '每周报告生成': '每周报告生成',
}
function taskZh(name: unknown): string {
  const n = String(name ?? '')
  return TASK_ZH[n] ?? n
}

/* 领域分组：raw name 精确匹配，兜底归入“其他任务” */
const DOMAINS: { title: string; keys: string[] }[] = [
  { title: '数据与行情', keys: ['每日数据更新', '每日数据质量检查', '每日财报时效性检查', '每周财务数据更新', 'fund_flow_update'] },
  { title: '市场感知', keys: ['market_daily_snapshot', 'market-style-update', 'pre-market-scan'] },
  { title: '信号与股票池', keys: ['每日信号生成', '每日信号执行', 'chan-scan-daily', 'daily-pool-refresh'] },
  { title: '风控与交易', keys: ['v13-risk-check', 'daily_trade_verify', 'v13-simulation-trading'] },
  { title: '学习与验证', keys: ['daily-strategy-validation', 'v13-verification', 'chan-knowledge-distill-weekly', 'weekly-strategy-discovery', 'signal-perf-backfill-daily'] },
  { title: '周报与汇总', keys: ['v13-weekly-report', '每周报告生成'] },
]
function domainOf(name: unknown): { title: string; idx: number } | null {
  const n = String(name ?? '')
  for (let i = 0; i < DOMAINS.length; i++) if (DOMAINS[i].keys.includes(n)) return { title: DOMAINS[i].title, idx: i }
  return null
}

/* M0-M6 × L1-L4 模块定义（节点始终展示，状态来自该模块检查点 worst case） */
const ENGINE_MODS: { code: string; zh: string }[] = [
  { code: 'M0', zh: '数据地基' }, { code: 'M1', zh: '市场感知' }, { code: 'M2', zh: '股票池' },
  { code: 'M3', zh: '信号生成' }, { code: 'M4', zh: '风控止损' }, { code: 'M5', zh: '交易对账' }, { code: 'M6', zh: '经验进化' },
]
const AUTO_MODS: { code: string; zh: string }[] = [
  { code: 'L1', zh: '策略验证' }, { code: 'L2', zh: '经验蒸馏' }, { code: 'L3', zh: '验证门裁决' }, { code: 'L4', zh: '周报进化' },
]
const CP_RANK: Record<string, number> = { failed: 5, late: 4, degraded: 3, pending: 2, off_day: 1, unknown: 0, confirmed: 0 }
function worstCps(cps: CheckpointResult[]): { status: string; label: string } {
  if (cps.length === 0) return { status: 'unknown', label: '暂无检查点' }
  let w = 'confirmed'
  for (const c of cps) {
    const s = String(c.status ?? 'unknown')
    if ((CP_RANK[s] ?? 0) > (CP_RANK[w] ?? 0)) w = s
  }
  return { status: w, label: CP_ZH[w] ?? w }
}

/** Build the board skeleton once; returns section roots + banner/meta for the mount. */
export interface ViewRefs {
  board: HTMLElement
  meta: HTMLElement
  banner: HTMLElement
  healthBox: HTMLElement
  flowBox: HTMLElement
  timelineBox: HTMLElement
  tasksBox: HTMLElement
  errsSec: HTMLElement
  errsBox: HTMLElement
  blockSec: HTMLElement
  blockBox: HTMLElement
}
export function buildView(): ViewRefs {
  const board = document.createElement('div')
  board.className = 'dsh-exec-board'
  const bd = (inner: string): HTMLElement => {
    const el = document.createElement('div')
    el.innerHTML = inner
    return el.firstElementChild as HTMLElement
  }
  const sec = (title: string, more: string, role: string, bdCls = 'bd'): HTMLElement => {
    const el = bd('<section class="dsh-exec-cardx">' +
      '<div class="hd"><span class="t">' + esc(title) + '</span><span class="more">' + esc(more) + '</span></div>' +
      '<div class="' + bdCls + '" data-role="' + role + '"></div></section>')
    return el
  }
  const wrap = document.createElement('div')
  wrap.className = 'dsh-exec-wrap'
  const head = bd('<div class="dsh-exec-head">' +
    '<h1 class="dsh-exec-title">双线执行确认看板<small>只读监控 · 运行与操作由 agent 自动完成</small></h1>' +
    '<div class="dsh-exec-meta"><span class="dsh-exec-last" data-role="lastFetch">—</span>' +
    '<button type="button" class="dsh-exec-btn" data-role="refresh">↻ 刷新</button></div></div>')
  const banner = bd('<div class="dsh-exec-banner" data-role="banner"></div>')
  const healthSec = sec('今日执行总览', '来自当日 cron 计划与运行结果', 'healthBox')
  const flowSec = sec('执行流水线', 'ENGINE M0–M6 × AUTONOMY L1–L4 检查点状态', 'flowBox')
  const timelineSec = sec('今日时间轴', '按计划时刻排序 · 已完成/失败/待执行', 'timelineBox')
  const tasksSec = sec('调度任务', '分类切换 · 点击任务行查看失败原因', 'tasksBox')
  const errsSec = sec('错误事件', '近 10 条日志异常（系统侧）', 'errsBox')
  errsSec.style.display = 'none'
  const blockSec = sec('流水线阻断', 'failed/late 且声明阻断下游', 'blockBox')
  blockSec.style.display = 'none'
  wrap.append(head, banner, healthSec, flowSec, timelineSec, tasksSec, errsSec, blockSec)
  board.appendChild(wrap)
  const $ = <T extends HTMLElement>(sel: string): T => board.querySelector<T>(sel) as T
  return {
    board,
    meta: $('[data-role="lastFetch"]'),
    banner,
    healthBox: $('[data-role="healthBox"]'),
    flowBox: $('[data-role="flowBox"]'),
    timelineBox: $('[data-role="timelineBox"]'),
    tasksBox: $('[data-role="tasksBox"]'),
    errsSec,
    errsBox: $('[data-role="errsBox"]'),
    blockSec,
    blockBox: $('[data-role="blockBox"]'),
  }
}

function renderHealth(refs: ViewRefs, data: BoardData): void {
  const tl = data.timeline ?? []
  const total = tl.length
  let ok = 0, fail = 0
  for (const t of tl) { if (t.status === 'success') ok++; else if (t.status === 'failed') fail++ }
  const wait = Math.max(0, total - ok - fail)
  const hbItem = (v: string, n: string, cls: string): string =>
    '<div class="hb-item ' + cls + '"><div class="v">' + v + '</div><div class="n">' + n + '</div></div>'
  let html = '<div class="dsh-exec-hb">' +
    hbItem(String(total), '今日计划任务', 't') + hbItem(String(ok), '✅ 已完成', 'ok') +
    hbItem(String(fail), '❌ 失败', fail > 0 ? 'bad' : 'ok') + hbItem(String(wait), '⏳ 待执行', 'wait') + '</div>'
  const hs = data.health ?? []
  if (hs.length > 0) {
    html += '<div class="dsh-exec-pills">' + hs.map((h) => {
      const st = String(h.status ?? 'unknown')
      return '<span class="pill ' + (st === 'ok' ? 'ok' : 'warn') + '" title="' + esc(h.error ?? '') + '">' +
        '<i class="dot ' + (H_DOT[st] ?? 'unk') + '"></i>' + esc(HEALTH_NAME[h.name ?? ''] ?? h.name ?? '') +
        '<b>' + esc(H_ZH[st] ?? st) + '</b></span>'
    }).join('') + '</div>'
  }
  refs.healthBox.innerHTML = html
}

function flowNode(code: string, zh: string, cps: CheckpointResult[]): string {
  const w = worstCps(cps)
  const dot = CP_DOT[w.status] ?? 'unk'
  const lines = cps.length === 0
    ? '<li class="cp-empty"><i class="dot unk"></i>暂无检查点</li>'
    : cps.map((c) => {
        const s = String(c.status ?? 'unknown')
        const et = c.expectTime
          ? '<time class="cp-tm" title="计划执行 ' + esc(c.expectTime) + '">' + esc(c.expectTime) + '</time>'
          : ''
        return '<li><i class="dot ' + (CP_DOT[s] ?? 'unk') + '"></i>' + et + esc(c.name ?? '?') +
          '<em>' + esc(CP_ZH[s] ?? s) + '</em></li>'
      }).join('')
  return '<div class="node st-' + dot + '">' +
    '<div class="n-top"><i class="dot ' + dot + '"></i><b>' + code + '</b><span>' + esc(zh) + '</span><em>' + esc(w.label) + '</em></div>' +
    '<ul class="cps">' + lines + '</ul></div>'
}
function renderFlow(refs: ViewRefs, data: BoardData): void {
  const cps = data.checkpoints ?? []
  const byMod: Record<string, CheckpointResult[]> = {}
  for (const c of cps) {
    const line = String(c.line ?? ''), mod = String(c.module ?? '')
    if (line !== 'engine' && line !== 'autonomy') continue
    const k = line + '|' + mod
    ;(byMod[k] = byMod[k] || []).push(c)
  }
  const band = (label: string, badge: string, mods: { code: string; zh: string }[]): string =>
    '<div class="dsh-exec-band"><div class="band-t"><span class="band-badge ' + badge + '">' + label + '</span>    <i></i></div><div class="band-nodes">' +
    mods.map((m) => flowNode(m.code, m.zh, byMod[badge + '|' + m.code] ?? [])).join('') + '</div></div>'
  refs.flowBox.innerHTML = band('ENGINE', 'engine', ENGINE_MODS) + band('AUTONOMY', 'autonomy', AUTO_MODS)
}

function tlStatusLabel(st: string): string { return TL_ZH[st] ?? '未知' }
function renderTimeline(refs: ViewRefs, data: BoardData): void {
  const tl = (data.timeline ?? []).slice().sort((a, b) => hmMin(a.expectedTime) - hmMin(b.expectedTime))
  if (tl.length === 0) { refs.timelineBox.innerHTML = '<div class="dsh-exec-empty">今日暂无计划任务</div>'; return }
  refs.timelineBox.innerHTML = '<div class="dsh-exec-tl-list">' + tl.map((t: TimelineEntry) => {
    const st = String(t.status ?? 'unknown')
    const tm = String(t.expectedTime ?? '')
    const err = st === 'failed' && t.error ? ' title="' + esc(t.error) + '"' : ''
    return '<div class="tl-item ' + (TL_TAG[st] ?? 'unk') + '"' + err + '>' +
      '<span class="tl-tm">' + esc(tm.slice(0, 5)) + '</span>' +
      '<span class="tl-ic">' + (TL_IC[st] ?? '❔') + '</span>' +
      '<div class="tl-bd"><div class="tl-nm">' + esc(taskZh(t.taskName)) + '</div>' +
      '<div class="tl-st ' + (TL_TAG[st] ?? 'unk') + '">' + esc(tlStatusLabel(st)) + '</div></div></div>'
  }).join('') + '</div>'
}

function taskTag(t: SchedulerTask): { cls: string; label: string } {
  const enabled = t.enabled === true || t.enabled === 'true' || t.enabled === 1
  if (!enabled) return { cls: 'off', label: '未启用' }
  const ts = Number(t.todaySuccess) || 0
  const tt = Number(t.todayTriggered) || 0
  if (tt > 0) return ts >= tt ? { cls: 'ok', label: '今日成功' } : { cls: 'bad', label: '今日失败' }
  let lrs = ''
  if (typeof t.lastRun === 'string') lrs = t.lastRun
  else if (t.lastRun && typeof t.lastRun === 'object') lrs = String((t.lastRun as { status?: unknown }).status ?? '')
  if (lrs === 'success') return { cls: 'ok', label: '上次成功' }
  if (lrs === 'failed') return { cls: 'bad', label: '上次失败' }
  if (lrs === 'skipped') return { cls: 'wait', label: '已跳过' }
  return { cls: 'wait', label: '待执行' }
}
function taskLast(t: SchedulerTask): string {
  let trig: unknown = null
  if (typeof t.lastRun === 'string') trig = t.lastRun
  else if (t.lastRun && typeof t.lastRun === 'object') trig = (t.lastRun as { triggeredAt?: unknown }).triggeredAt
  return trig ? shortDT(trig) : '—'
}
/* ---- 调度任务：分类 tab + 任务表格列表（2026-09-04 v2 · 对齐设计稿 pill tab + 任务表） ---- */
let selTaskName: string | null = null
let selDom: string = 'all'
export function setTaskSel(name: string | null): void { selTaskName = name }
export function setDomSel(d: string): void { selDom = d }

/** 归一 lastRun：字符串可能是 ISO 时间或状态词；对象含 triggeredAt/status/error */
function runLast(t: SchedulerTask): { at: string; st: string; err: string } {
  const lr = t.lastRun
  if (lr === null || lr === undefined) return { at: '—', st: '', err: '' }
  let at = '', st = '', err = ''
  if (typeof lr === 'string') {
    if (/^(success|failed|skipped|running|pending|unknown)$/.test(lr)) st = lr
    else at = shortDT(lr)
  } else if (typeof lr === 'object') {
    const o = lr as { triggeredAt?: unknown; status?: unknown; error?: unknown; message?: unknown }
    at = shortDT(o.triggeredAt)
    st = String(o.status ?? '')
    err = String(o.error ?? o.message ?? '')
  }
  return { at: at || '—', st, err }
}
function fullDT(s: unknown): string {
  const m = String(s ?? '').match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
  if (!m) { const v = String(s ?? '').trim(); return v || '—' }
  return m[1] + '-' + m[2] + '-' + m[3] + ' ' + m[4] + ':' + m[5]
}
function taskDetailHtml(t: SchedulerTask): string {
  const d = domainOf(t.name)
  const tag = taskTag(t)
  const last = runLast(t)
  const trig = Number(t.todayTriggered) || 0
  const succ = Number(t.todaySuccess) || 0
  const raw = String(t.name ?? '')
  const zh = esc(taskZh(raw))
  const row = (label: string, value: string): string =>
    '<div class="tkd-i"><b>' + label + '</b><span>' + value + '</span></div>'
  let html = row('名称', zh + (taskZh(raw) === raw ? '' : '<em class="tkd-code">' + esc(raw) + '</em>'))
  html += row('状态', '<span class="tag ' + tag.cls + '">' + esc(tag.label) + '</span>')
  html += row('领域', esc(d ? d.title : '其他任务'))
  html += row('计划', esc(String(t.scheduleExpr ?? '').trim() || '—'))
  html += row('上次运行', esc(last.at))
  html += row('上次结果', last.st ? esc(TL_ZH[last.st] ?? last.st) : '—')
  html += row('今日', esc(trig + ' 次触发 / ' + succ + ' 成功'))
  html += row('下次运行', esc(fullDT(t.nextRunAt)))
  const errMsg = last.err || String(t.error ?? '')
  if (errMsg) html += '<div class="tkd-i tkd-err"><b>失败原因</b><span>' + esc(errMsg) + '</span></div>'
  return html
}

export function renderTasks(refs: ViewRefs, data: BoardData): void {
  const tasks = data.tasks ?? []
  if (tasks.length === 0) { selTaskName = null; selDom = 'all'; refs.tasksBox.innerHTML = '<div class="dsh-exec-empty">暂无调度任务</div>'; return }
  const domCount = DOMAINS.map(() => 0)
  let otherCount = 0
  for (const t of tasks) { const d = domainOf(t.name); if (d) domCount[d.idx]++; else otherCount++ }
  // 当前 tab 分类合法性：该分类下已无任务则回退到「全部」
  const domOk = selDom === 'all' || (selDom === 'x' ? otherCount > 0 : domCount[Number(selDom)] > 0)
  if (!domOk) selDom = 'all'
  const inDom = (raw: string): boolean => {
    if (selDom === 'all') return true
    const d = domainOf(raw)
    if (selDom === 'x') return d === null
    return d !== null && String(d.idx) === selDom
  }
  const view = tasks.filter((t) => inDom(String(t.name ?? '')))
  // 选中任务持久化（30s 轮询重绘仍保留）；不在当前分类内则取消选中（表格下方详情随行）
  if (selTaskName !== null && !view.some((t) => String(t.name) === selTaskName)) selTaskName = null
  const cnt = (v: number): string => '<b class="c">' + v + '</b>'
  const tab = (dom: string, label: string, count: number): string =>
    '<button type="button" class="dsh-exec-tab' + (selDom === dom ? ' act' : '') + '" data-dom="' + dom + '">' + label + cnt(count) + '</button>'
  const tabs: string[] = [tab('all', '全部', tasks.length)]
  DOMAINS.forEach((dm, i) => { if (domCount[i] > 0) tabs.push(tab(String(i), '<i class="dk d' + i + '"></i>' + esc(dm.title), domCount[i])) })
  if (otherCount > 0) tabs.push(tab('x', '其他任务', otherCount))
  const trow = (t: SchedulerTask): string => {
    const raw = String(t.name ?? '')
    const tag = taskTag(t)
    const last = runLast(t)
    const trig = Number(t.todayTriggered) || 0
    const succ = Number(t.todaySuccess) || 0
    const err = last.err || String(t.error ?? '')
    const sel = raw === selTaskName ? ' sel' : ''
    const zh = taskZh(raw)
    return '<tr class="dsh-exec-tr' + sel + '" data-tk="' + esc(raw) + '"' + (err ? ' title="失败原因：' + esc(err.slice(0, 300)) + '"' : '') + '>' +
      '<td class="nm"><span class="zh">' + esc(zh) + '</span>' + (zh === raw ? '' : '<span class="code">' + esc(raw) + '</span>') + '</td>' +
      '<td class="cr">' + esc(String(t.scheduleExpr ?? '').trim() || '—') + '</td>' +
      '<td class="st"><span class="tag ' + tag.cls + '">' + esc(tag.label) + '</span></td>' +
      '<td class="tm">' + esc(last.at) + (last.st ? '<em class="ls ' + (TL_TAG[last.st] ?? 'unk') + '">' + esc(TL_ZH[last.st] ?? last.st) + '</em>' : '') + '</td>' +
      '<td class="td">' + esc(trig + ' 触发 / ' + succ + ' 成功') + '</td>' +
      '<td class="nx">' + esc(shortDT(t.nextRunAt)) + '</td></tr>'
  }
  const hint = '<div class="dsh-exec-legend dsh-exec-legend2"><span class="dsh-exec-hint">点击 tab 切换分类 · 点击任务行查看失败原因 · <i class="dot ok"></i>成功 <i class="dot bad"></i>失败 <i class="dot wait"></i>待执行 <i class="dot off"></i>未启用</span></div>'
  const rows = view.map(trow).join('')
  const selTask = selTaskName === null ? null : view.find((t) => String(t.name) === selTaskName)
  refs.tasksBox.innerHTML = hint +
    '<div class="dsh-exec-tabs">' + tabs.join('') + '</div>' +
    '<div class="dsh-exec-tbwrap"><table class="dsh-exec-tb"><thead><tr>' +
    '<th>任务</th><th>cron 计划</th><th>状态</th><th>上次运行</th><th>今日</th><th>下次运行</th></tr></thead>' +
    '<tbody>' + (rows || '<tr class="empty"><td colspan="6">该分类下暂无任务</td></tr>') + '</tbody></table></div>' +
    (selTask ? '<div class="dsh-exec-tkdetail">' + taskDetailHtml(selTask) + '</div>' : '')
}

function renderErrors(refs: ViewRefs, data: BoardData): void {
  const errs = data.errors ?? []
  refs.errsSec.style.display = errs.length > 0 ? '' : 'none'
  if (errs.length === 0) return
  refs.errsBox.innerHTML = '<ol class="dsh-exec-errs">' + errs.slice(0, 10).map((e) => {
    const src = String(e.source ?? '').toLowerCase()
    const cls = src.includes('os') ? 'os' : src.includes('dsh') ? 'dsh' : 'v2'
    const first = trunc((e.line ?? e.file ?? '').replace(/\\n/g, ' '), 120)
    return '<li><span class="src ' + cls + '">' + esc(e.source ?? '?') + '</span>' +
      '<time>' + esc(shortDT(e.timestamp)) + '</time>' +
      '<span class="line" title="' + esc(e.line ?? '') + '">' + esc(first) + '</span></li>'
  }).join('') + '</ol>'
}
function renderBlocked(refs: ViewRefs, data: BoardData): void {
  const bl = data.blockedFlows ?? []
  refs.blockSec.style.display = bl.length > 0 ? '' : 'none'
  if (bl.length === 0) return
  refs.blockBox.innerHTML = bl.map((b) =>
    '<div class="dsh-exec-block"><b>' + esc(b.checkpointName ?? b.checkpointId ?? '?') + '</b>' +
    '<span class="tag bad">' + esc(CP_ZH[String(b.status ?? '')] ?? esc(b.status ?? '')) + '</span>' +
    (b.blocks && b.blocks.length > 0 ? '<span class="blocks">阻断: ' + esc(b.blocks.join(', ')) + '</span>' : '') + '</div>').join('')
}

export function renderAll(refs: ViewRefs, data: BoardData): void {
  renderHealth(refs, data)
  renderFlow(refs, data)
  renderTimeline(refs, data)
  renderTasks(refs, data)
  renderErrors(refs, data)
  renderBlocked(refs, data)
}
