/**
 * View layer: renders /dashboard/api/genome payload into five regions —
 *   ① overview head (genome version / 4 sections / consistency badge + recheck)
 *   ② section state matrix (4 cards)
 *   ③ consistency diagnostics panel (C1/C2/C3)
 *   ④ candidate lifecycle pipeline (status tabs + progress)
 *   ⑤ evolution lineage timeline (history, newest first)
 * Pure DOM string assembly with esc() on every data field (data is local
 * genome files, but defense-in-depth). Filter state lives module-local.
 *
 * @module dashboard-genome/client/view
 */

import type { CandidateInfo, GenomeData, GenomeSectionInfo } from './types.ts'

export interface ViewRefs {
  root: HTMLElement
  refreshBtn?: HTMLButtonElement
  meta: HTMLElement
  /** 头部行容器（board-mount 注入「收起」按钮用） */
  head?: HTMLElement
}

const REFRESH_LABEL = '⟳ 重检'
const REFRESH_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>`

function esc(s: unknown): string {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

function fmtDT(iso: string | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number): string => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function fmtDate(iso: string | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const SEC_ZH: Record<string, string> = {
  constitution: '宪法', principles: '决策原则', rules: '操作规则', lessons: '经验教训',
}
const SEC_FULL: Record<string, string> = {
  constitution: '交易宪法（不可修改）', principles: '决策原则', rules: '操作规则', lessons: '经验教训',
}
const SEC_CLASS: Record<string, string> = { constitution: 'constitution', principles: 'evolvable', rules: 'evolvable', lessons: 'evolvable' }

const TYPE_ZH: Record<string, string> = { update: '更新', promote: '转正', rollback: '回滚' }
const TYPE_CLS: Record<string, string> = { update: 'up', promote: 'ok', rollback: 'bad' }

const ST_ZH: Record<string, string> = {
  watching: '观察中', promoted: '已转正', rejected: '已拒绝', extended: '观察延期', unknown: '未知',
}
const ST_CLS: Record<string, string> = {
  watching: 'wait', promoted: 'ok', rejected: 'bad', extended: 'wait', unknown: 'unk',
}

/** 候选 tab 过滤 */
type CandFilter = 'all' | 'watching' | 'due' | 'promoted' | 'rejected' | 'extended'
const FILTERS: { key: CandFilter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'watching', label: '观察中' },
  { key: 'due', label: '待裁决' },
  { key: 'promoted', label: '已转正' },
  { key: 'rejected', label: '已回滚/拒绝' },
]

let lastData: GenomeData | undefined
let candFilter: CandFilter = 'all'

function matchesFilter(c: CandidateInfo, f: CandFilter): boolean {
  switch (f) {
    case 'all': return true
    case 'watching': return c.status === 'watching' && !c.due
    case 'due': return c.due === true
    case 'promoted': return c.status === 'promoted'
    case 'rejected': return c.status === 'rejected'
    case 'extended': return c.status === 'extended'
    default: return true
  }
}

function badge(text: string, cls: string): string {
  return `<span class="dsh-gen-badge ${cls}">${esc(text)}</span>`
}

// ---------- ① 概览头 ----------
function ovHtml(d: GenomeData): string {
  const cons = d.consistency
  const badgeHtml = cons.healthy
    ? badge('🟢 一致性健康', 'ok')
    : badge(`⚠️ ${cons.issues.filter((i) => i.items.length > 0).length} 项异常`, 'bad')
  const candCount = d.candidates.length
  const watching = d.candidates.filter((c) => c.status === 'watching').length
  const due = d.candidates.filter((c) => c.due).length
  return `
  <div class="dsh-gen-ov">
    <div class="dsh-gen-ov-title">
      <span class="dsh-gen-ov-big">自主进化</span>
      <span class="dsh-gen-ov-sub">Autonomy 线 · 能力设计层可观测 — 回答「改了什么规则 / 什么在试运行何时出结果 / 进化链路有无卡住」</span>
    </div>
    <div class="dsh-gen-ov-stats">
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">基因组版本</span><span class="dsh-gen-stat-v dsh-gen-gv">${esc(d.genomeVersion)}</span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">段</span><span class="dsh-gen-stat-v">${d.sections.length}<small>/4</small></span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">谱系事件</span><span class="dsh-gen-stat-v">${d.history.length}</span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">候选</span><span class="dsh-gen-stat-v">${candCount}<small> · 观察中 ${watching}${due ? ` · <b class="dsh-gen-warn-txt">待裁决 ${due}</b>` : ''}</small></span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">一致性</span><span class="dsh-gen-stat-v">${badgeHtml}</span></div>
    </div>
    <div class="dsh-gen-ov-meta">创建 ${fmtDate(d.createdAt)} · 最近更新 ${fmtDT(d.updatedAt)} · 核验 ${fmtDT(cons.checkedAt)}</div>
  </div>`
}

// ---------- ② 段状态矩阵（含段全文阅读：summary 展开整段条文，宪法层默认展开） ----------
function sectionCardHtml(s: GenomeSectionInfo): string {
  const isConst = s.id === 'constitution'
  const clsTag = isConst
    ? badge('🔒 宪法层 · 锁定', 'lock')
    : badge('可进化', 'ev')
  const full = (s.content ?? '').trim()
  const sizeZh = full.length > 0 ? `${full.length} 字 · ` : ''
  const bodyHtml = full.length > 0
    ? `<details class="dsh-gen-sec-body"${isConst ? ' open' : ''}><summary>${sizeZh}查看全文 v${s.version ?? 0}</summary><pre class="dsh-gen-sec-content">${esc(full)}</pre></details>`
    : `<div class="dsh-gen-sec-empty">（sections/${String(s.id)}.md 缺失——genome 工具写入异常）</div>`
  const lc = s.lastChange
  const lcHtml = lc
    ? `<details class="dsh-gen-exp"><summary><span class="dsh-gen-lc-head">最近：<b>${TYPE_ZH[lc.type ?? ''] ?? esc(lc.type ?? '')}</b> @ ${esc(lc.genomeVersion ?? '')} · ${fmtDT(lc.ts)}</span></summary><div class="dsh-gen-exp-body">${esc(lc.reason ?? '—')}</div></details>`
    : `<div class="dsh-gen-lc-empty">无变更记录</div>`
  return `
  <div class="dsh-gen-sec-card">
    <div class="dsh-gen-sec-head">
      <span class="dsh-gen-sec-name">${esc(SEC_FULL[s.id] ?? s.id)}</span>
      <span class="dsh-gen-sec-ver">v${s.version ?? 0}</span>
      ${clsTag}
    </div>
    ${bodyHtml}
    ${lcHtml}
  </div>`
}

function sectionsHtml(d: GenomeData): string {
  return `
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">② 段状态矩阵</span><span class="dsh-gen-block-s">4 个基因组段 · 版本与最近变更</span></div>
    <div class="dsh-gen-sec-grid">
      ${d.sections.map(sectionCardHtml).join('')}
    </div>
  </div>`
}

// ---------- ③ 一致性诊断 ----------
function issueHtml(iss: { id: string; label: string; description: string; items: unknown[] }): string {
  if (iss.items.length === 0) {
    return `<div class="dsh-gen-iss ok"><span class="dsh-gen-iss-id">${esc(iss.id)}</span><span class="dsh-gen-iss-t">${esc(iss.label)}</span><span class="dsh-gen-iss-r">✅ 通过</span></div>`
  }
  const itemRows = iss.items.map((it) => {
    const o = it as Record<string, unknown>
    const parts: string[] = []
    if (o.genomeVersion) parts.push(`g<code>${esc(o.genomeVersion)}</code>`)
    if (o.section) parts.push(esc(SEC_ZH[String(o.section)] ?? String(o.section)))
    if (o.sectionVersion) parts.push(`v${String(o.sectionVersion)}`)
    if (o.id) parts.push(`<code>${esc(o.id)}</code>`)
    if (o.file) parts.push(`<code>${esc(o.file)}</code>`)
    if (o.ts) parts.push(fmtDT(String(o.ts)))
    const reason = o.reason ? `<div class="dsh-gen-iss-reason">${esc(o.reason)}</div>` : ''
    return `<div class="dsh-gen-iss-item">${parts.join(' · ')}${reason}</div>`
  }).join('')
  return `
  <div class="dsh-gen-iss bad">
    <span class="dsh-gen-iss-id">${esc(iss.id)}</span>
    <span class="dsh-gen-iss-t">${esc(iss.label)}</span>
    <span class="dsh-gen-iss-r">❌ ${iss.items.length} 项</span>
  </div>
  <div class="dsh-gen-iss-desc">${esc(iss.description)}</div>
  ${itemRows}`
}

function consistencyHtml(d: GenomeData): string {
  const cons = d.consistency
  const headCls = cons.healthy ? 'ok' : 'bad'
  const headText = cons.healthy
    ? 'C1/C2/C3 全部通过 — 登记与落库一致，gate 有案可裁'
    : `检测到 ${cons.issues.filter((i) => i.items.length > 0).length} 类异常（F1 哨兵规则，与 gate runConsistencyCheck 同源）`
  return `
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">③ 一致性诊断</span><span class="dsh-gen-block-s">F1 哨兵可视化仪表 · 状态一致性核验（genome.json ↔ candidates.json）</span></div>
    <div class="dsh-gen-cons-head ${headCls}">${headText}</div>
    <div class="dsh-gen-iss-list">
      ${d.consistency.issues.map(issueHtml).join('')}
    </div>
  </div>`
}

// ---------- ④ 候选生命周期 ----------
function candidateCardHtml(c: CandidateInfo): string {
  const sec = SEC_ZH[c.section] ?? c.section
  const status = c.due ? '⏰ 已过观察期 · 待 gate 裁决' : (ST_ZH[c.status] ?? c.status)
  const statusCls = c.due ? 'due' : (ST_CLS[c.status] ?? 'unk')
  let progressHtml = ''
  if ((c.status === 'watching' || c.due) && c.progress !== undefined) {
    const pct = Math.round((c.progress ?? 0) * 100)
    progressHtml = `
    <div class="dsh-gen-cand-bar">
      <div class="dsh-gen-cand-bar-in" style="width:${pct}%"></div>
    </div>
    <div class="dsh-gen-cand-bar-meta">${fmtDate(c.createdAt)} → ${fmtDate(c.observeUntil)} · ${c.due ? '已到期' : `余 ${c.remainingDays ?? 0} 天`}</div>`
  } else {
    progressHtml = `<div class="dsh-gen-cand-bar-meta">${fmtDate(c.createdAt)}${c.observeUntil ? ` → ${fmtDate(c.observeUntil)}` : ''}</div>`
  }
  let hc = ''
  if (c.healthCheck) {
    const passed = c.healthCheck.passed ? '✅ 结构健康' : '❌ 结构异常'
    const extra: string[] = []
    if (c.healthCheck.sizeDelta !== undefined) extra.push(`diff ${c.healthCheck.sizeDelta} 字符`)
    if (c.healthCheck.issues && c.healthCheck.issues.length > 0) extra.push(...c.healthCheck.issues)
    const extraHtml = extra.length > 0 ? `<div class="dsh-gen-cand-hc-extra">${extra.map((e) => esc(e)).join('；')}</div>` : ''
    hc = `<div class="dsh-gen-cand-hc">${passed}${c.healthCheck.checkedAt ? ` · ${fmtDT(c.healthCheck.checkedAt)} 核` : ''}${extraHtml}</div>`
  }
  const note = c.note ? `<div class="dsh-gen-cand-note">${esc(c.note)}</div>` : ''
  const mut = c.mutationType ? `<span class="dsh-gen-cand-mut">${esc(c.mutationType)}</span>` : ''
  return `
  <div class="dsh-gen-cand">
    <div class="dsh-gen-cand-head">
      <span class="dsh-gen-cand-sec">${esc(sec)}</span>
      <span class="dsh-gen-cand-gv">${esc(c.genomeVersion)} · v${c.sectionVersion}</span>
      <span class="dsh-gen-cand-id"><code>${esc(c.id)}</code></span>
      ${mut}
      ${badge(status, statusCls)}
    </div>
    ${progressHtml}
    ${hc}
    ${note}
  </div>`
}

function candTabsHtml(): string {
  const tabs = FILTERS.map((f) => {
    const active = f.key === candFilter ? ' on' : ''
    return `<button type="button" class="dsh-gen-tab${active}" data-cand-filter="${f.key}">${esc(f.label)}</button>`
  }).join('')
  return `<div class="dsh-gen-tabs">${tabs}</div>`
}

function candListHtml(d: GenomeData): string {
  const list = d.candidates.filter((c) => matchesFilter(c, candFilter))
  const empty = list.length === 0
    ? `<div class="dsh-gen-cand-empty">此筛选下无候选${d.candidates.length === 0 ? '（candidates.json 暂无记录）' : ''}</div>`
    : list.map(candidateCardHtml).join('')
  return `<div class="dsh-gen-cand-list">${empty}</div>`
}

function candidatesHtml(d: GenomeData): string {
  return `
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">④ 候选生命周期流水线</span><span class="dsh-gen-block-s">genome_update(candidate) → 观察期 → validation_gate 裁决（转正 / 回滚）</span></div>
    ${candTabsHtml()}
    <div class="dsh-gen-cand-list-root">${candListHtml(d)}</div>
  </div>`
}

// ---------- ⑤ 谱系时间线 ----------
function timelineHtml(d: GenomeData): string {
  if (d.history.length === 0) return `<div class="dsh-gen-tl-empty">无谱系记录</div>`
  const rows = d.history.map((h) => {
    const typeZh = TYPE_ZH[h.type] ?? esc(h.type)
    const typeCls = TYPE_CLS[h.type] ?? 'unk'
    const sec = SEC_ZH[h.section] ?? h.section
    const stage = h.stage ? badge(h.stage === 'candidate' ? '观察版' : '正式版', h.stage === 'candidate' ? 'wait' : 'ev') : ''
    const commit = h.gitCommit ? ` <code>${esc(h.gitCommit)}</code>` : ''
    const reasonHtml = h.reason
      ? `<details class="dsh-gen-exp"><summary>理由</summary><div class="dsh-gen-exp-body">${esc(h.reason)}</div></details>`
      : ''
    return `
    <div class="dsh-gen-tl-item">
      <div class="dsh-gen-tl-dot ${typeCls}"></div>
      <div class="dsh-gen-tl-main">
        <div class="dsh-gen-tl-head">
          <span class="dsh-gen-tl-gv">${esc(h.genomeVersion)}</span>
          ${badge(typeZh, typeCls)}
          <span class="dsh-gen-tl-sec">${esc(sec)} v${h.sectionVersion}</span>
          ${stage}
          <span class="dsh-gen-tl-ts">${fmtDT(h.ts)}</span>
          ${commit}
        </div>
        ${reasonHtml}
      </div>
    </div>`
  }).join('')
  return `<div class="dsh-gen-tl">${rows}</div>`
}

// ---------- 组装 ----------
function bodyHtml(d: GenomeData): string {
  return `${ovHtml(d)}${sectionsHtml(d)}${consistencyHtml(d)}${candidatesHtml(d)}${timelineHtml(d)}`
}

export function buildView(): ViewRefs {
  const root = document.createElement('div')
  root.className = 'dsh-gen-board'

  const head = document.createElement('div')
  head.className = 'dsh-gen-head'

  const refreshBtn = document.createElement('button')
  refreshBtn.type = 'button'
  refreshBtn.className = 'dsh-gen-recheck'
  refreshBtn.title = '重新读取 genome.json / candidates.json 并重跑 C1/C2/C3 一致性核验'
  refreshBtn.innerHTML = `${REFRESH_SVG}<span>${REFRESH_LABEL}</span>`

  const meta = document.createElement('div')
  meta.className = 'dsh-gen-meta'
  meta.textContent = '加载中…'

  head.appendChild(meta)
  head.appendChild(refreshBtn)

  const body = document.createElement('div')
  body.className = 'dsh-gen-body'

  root.appendChild(head)
  root.appendChild(body)

  return { root, refreshBtn, meta, head }
}

export function renderAll(refs: ViewRefs, data: GenomeData): void {
  lastData = data
  const body = refs.root.querySelector<HTMLElement>('.dsh-gen-body')
  if (body === null) return
  body.innerHTML = bodyHtml(data)
  // 候选 tab：事件委托到 body（innerHTML 重建不丢监听；无叠加重绑）
  body.addEventListener('click', (ev) => {
    const btn = (ev.target as HTMLElement | null)?.closest<HTMLButtonElement>('[data-cand-filter]')
    if (btn === null || btn === undefined || lastData === undefined) return
    candFilter = (btn.dataset.candFilter as CandFilter) ?? 'all'
    const tabs = body.querySelector<HTMLElement>('.dsh-gen-tabs')
    const listRoot = body.querySelector<HTMLElement>('.dsh-gen-cand-list-root')
    if (tabs !== null) tabs.outerHTML = candTabsHtml()
    if (listRoot !== null) listRoot.innerHTML = candListHtml(lastData)
  })
}
