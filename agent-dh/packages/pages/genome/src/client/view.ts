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
import { esc, fmtClock as _fmtClock, fmtDate as _fmtDate } from '@pi-investment/page-kit/client'

export interface ViewRefs {
  root: HTMLElement
  refreshBtn?: HTMLButtonElement
  meta: HTMLElement
  /** 头部行容器（board-mount 注入「收起」按钮用） */
  head?: HTMLElement
}

const REFRESH_LABEL = '⟳ 重检'
const REFRESH_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>`

const EXPLAIN_API = '/dashboard/api/genome/explain'
/**
 * 「🤖 讲解」按钮：条目级（item）时显示小图标按钮，点击后 host 把「讲解这一条」投递给在线
 * investor agent，讲解回复出现在会话（同步只返回投递结果）。item 为空视为无条目（host 将 400 引导）。
 */
function explainBtn(moduleId: string, item?: string, hint?: string): string {
  const itemAttr = item !== undefined ? ` data-explain-item="${esc(item)}"` : ''
  const title = hint !== undefined
    ? `AI 讲解：${esc(hint)}（讲解将出现在下方会话）`
    : 'AI 讲解：请当前 AI 介绍这是什么（讲解将出现在下方会话）'
  const cls = item !== undefined ? 'dsh-gen-explain sm' : 'dsh-gen-explain'
  const label = item !== undefined ? '🤖' : '🤖 讲解'
  return `<button type="button" class="${cls}" data-explain-module="${moduleId}"${itemAttr} title="${title}">${label}</button>`
}

function fmtDT(iso: string | undefined): string { return _fmtClock(iso) }
function fmtDate(iso: string | undefined): string { return _fmtDate(iso) }

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

// ---------- ② 段状态矩阵（段全文/变更理由默认折叠，点 summary 展开阅读） ----------
function sectionCardHtml(s: GenomeSectionInfo): string {
  const isConst = s.id === 'constitution'
  const clsTag = isConst
    ? badge('🔒 宪法层 · 锁定', 'lock')
    : badge('可进化', 'ev')
  const full = (s.content ?? '').trim()
  const sizeZh = full.length > 0 ? `${full.length} 字 · ` : ''
  const bodyHtml = full.length > 0
    ? `<details class="dsh-gen-sec-body"><summary>${sizeZh}全文 v${s.version ?? 0}（点击展开）</summary><pre class="dsh-gen-sec-content">${esc(full)}</pre></details>`
    : `<div class="dsh-gen-sec-empty">（sections/${String(s.id)}.md 缺失——genome 工具写入异常）</div>`
  const lc = s.lastChange
  const lcHtml = lc
    ? `<details class="dsh-gen-exp"><summary><span class="dsh-gen-lc-head">最近：<b>${TYPE_ZH[lc.type ?? ''] ?? esc(lc.type ?? '')}</b> @ ${esc(lc.genomeVersion ?? '')} · ${fmtDT(lc.ts)}（点击展开理由）</span></summary><div class="dsh-gen-exp-body">${esc(lc.reason ?? '—')}</div></details>`
    : `<div class="dsh-gen-lc-empty">无变更记录</div>`
  return `
  <div class="dsh-gen-sec-card">
    <div class="dsh-gen-sec-head">
      <span class="dsh-gen-sec-name">${esc(SEC_FULL[s.id] ?? s.id)}</span>
      <span class="dsh-gen-sec-ver">v${s.version ?? 0}</span>
      ${clsTag}
      ${explainBtn('sections', s.id, `${SEC_FULL[s.id] ?? s.id} 段是什么、当前版本要点与最近变更`)}
    </div>
    ${bodyHtml}
    ${lcHtml}
  </div>`
}

function sectionsHtml(d: GenomeData): string {
  return `
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">② 段状态矩阵</span><span class="dsh-gen-block-s">4 个基因组段 · 版本与最近变更 · 点各段 🤖 可逐段讲解</span></div>
    <div class="dsh-gen-sec-grid">
      ${d.sections.map(sectionCardHtml).join('')}
    </div>
  </div>`
}

// ---------- ③ 一致性诊断 ----------
function issueHtml(iss: { id: string; label: string; description: string; items: unknown[] }): string {
  if (iss.items.length === 0) {
    return `<div class="dsh-gen-iss ok"><span class="dsh-gen-iss-id">${esc(iss.id)}</span><span class="dsh-gen-iss-t">${esc(iss.label)}</span><span class="dsh-gen-iss-r">✅ 通过</span>${explainBtn('consistency', iss.id, `${iss.label} 检查什么、为什么设计这道哨兵`)}</div>`
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
    ${explainBtn('consistency', iss.id, `${iss.label} 当前 ${iss.items.length} 项异常是什么、该怎么处置`)}
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
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">③ 一致性诊断</span><span class="dsh-gen-block-s">F1 哨兵可视化仪表 · 状态一致性核验（genome.json ↔ candidates.json）· 每条哨兵 🤖 可讲</span></div>
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
  // 具体改动：这条候选改了什么（health_check.rule_changes added/removed）
  let changes = ''
  const rc = c.healthCheck?.ruleChanges
  const hasRc = rc && ((rc.added?.length ?? 0) + (rc.removed?.length ?? 0)) > 0
  if (hasRc) {
    const rows: string[] = []
    for (const r of rc.added ?? []) rows.push(`<span class="dsh-gen-chg add">🆕 新增规则 ${esc(r)}</span>`)
    for (const r of rc.removed ?? []) rows.push(`<span class="dsh-gen-chg rm">🗑 移除规则 ${esc(r)}</span>`)
    changes = `<div class="dsh-gen-cand-chg">${rows.join('')}</div>`
  } else if (c.healthCheck?.ruleChanges) {
    // 有 health_check 但无规则增删（文本修正型候选，如 R-006）——点明是修正不是新增
    changes = `<div class="dsh-gen-cand-chg"><span class="dsh-gen-chg mod">✏️ 文本修正（无规则增删，见下方理由）</span></div>`
  }
  // 状态解读：这条候选现在在哪一步、下一步自动发生什么
  const hint = c.due
    ? '观察期已满 · 下一步：validation_gate 凭观察期表现裁决 → 转正为正式版 / 回滚'
    : c.status === 'watching'
      ? `试运行观察中 · ${c.remainingDays ?? '?'} 天后到期自动进入 gate 裁决（转正 / 回滚），此间正式版未被改动`
      : c.status === 'promoted'
        ? '已转正 · 此版本内容为正式版，持续生效中'
        : c.status === 'rejected'
          ? '已拒绝 · 内容未转正（如需可 genome_rollback 复原）'
          : ''
  const step = hint ? `<div class="dsh-gen-cand-step">${esc(hint)}</div>` : ''
  return `
  <div class="dsh-gen-cand">
    <div class="dsh-gen-cand-head">
      <span class="dsh-gen-cand-sec">${esc(sec)}</span>
      <span class="dsh-gen-cand-gv">${esc(c.genomeVersion)} · v${c.sectionVersion}</span>
      <span class="dsh-gen-cand-id"><code>${esc(c.id)}</code></span>
      ${mut}
      ${badge(status, statusCls)}
      ${explainBtn('candidates', c.id, `这条候选（${sec} ${c.genomeVersion}）改了什么、解决什么问题、观察进度与下一步`)}
    </div>
    ${changes}
    ${step}
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
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">④ 候选生命周期流水线</span><span class="dsh-gen-block-s">genome_update(candidate) → 观察期 → validation_gate 裁决（转正 / 回滚）· 每个候选卡 🤖 可讲</span></div>
    ${candTabsHtml()}
    <div class="dsh-gen-cand-list-root">${candListHtml(d)}</div>
  </div>`
}

// ---------- ⑤ 谱系时间线 ----------
function timelineHtml(d: GenomeData): string {
  const inner = d.history.length === 0
    ? `<div class="dsh-gen-tl-empty">无谱系记录</div>`
    : `<div class="dsh-gen-tl">${d.history.map((h) => {
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
    }).join('')}</div>`
  return `
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">⑤ 谱系时间线</span><span class="dsh-gen-block-s">规则进化历史 · 谁在何时改了什么（genome_version 倒序）</span></div>
    ${inner}
  </div>`
}

// ---------- AI 讲解请求 ----------
/** 点击「🤖 讲解」：请求 host 把「讲解这一条」投递给在线 investor agent（回复出现在会话，不在页面）。 */
async function requestExplain(btn: HTMLButtonElement): Promise<void> {
  if (btn.disabled) return
  const moduleId = btn.dataset.explainModule ?? ''
  const item = btn.dataset.explainItem ?? ''
  const original = btn.textContent ?? '🤖 讲解'
  btn.disabled = true
  btn.classList.add('loading')
  btn.textContent = '⏳…'
  try {
    const qs = `module=${encodeURIComponent(moduleId)}${item ? `&item=${encodeURIComponent(item)}` : ''}`
    const res = await fetch(`${EXPLAIN_API}?${qs}`, { headers: { Accept: 'application/json' } })
    const json = (await res.json()) as { success?: boolean; error?: string; data?: { delivered?: boolean; target?: string } }
    if (!res.ok || json.success === false) throw new Error(json.error ?? `HTTP ${res.status}`)
    btn.classList.remove('loading')
    btn.classList.add('done')
    btn.textContent = '✓'
    btn.title = '讲解任务已投递给 AI 会话：收起看板后 AI 将介绍这一条是什么、有什么作用'
  } catch (err) {
    btn.classList.remove('loading')
    btn.classList.add('err')
    btn.textContent = '✗'
    btn.title = '失败：' + (err instanceof Error ? err.message : String(err))
  } finally {
    window.setTimeout(() => {
      btn.disabled = false
      btn.classList.remove('done', 'err', 'loading')
      btn.textContent = original
    }, 3500)
  }
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

  // 事件委托：body 常驻，innerHTML 重建不丢监听；一次性绑定避免 renderAll 每轮叠加
  body.addEventListener('click', (ev) => {
    const target = (ev.target as HTMLElement | null)
    if (target === null) return
    const tab = target.closest<HTMLButtonElement>('[data-cand-filter]')
    if (tab !== null) {
      if (lastData === undefined) return
      candFilter = (tab.dataset.candFilter as CandFilter) ?? 'all'
      const tabs = body.querySelector<HTMLElement>('.dsh-gen-tabs')
      const listRoot = body.querySelector<HTMLElement>('.dsh-gen-cand-list-root')
      if (tabs !== null) tabs.outerHTML = candTabsHtml()
      if (listRoot !== null) listRoot.innerHTML = candListHtml(lastData)
      return
    }
    const explain = target.closest<HTMLButtonElement>('[data-explain-module]')
    if (explain !== null) {
      void requestExplain(explain)
      return
    }
  })

  root.appendChild(head)
  root.appendChild(body)

  return { root, refreshBtn, meta, head }
}

export function renderAll(refs: ViewRefs, data: GenomeData): void {
  lastData = data
  const body = refs.root.querySelector<HTMLElement>('.dsh-gen-body')
  if (body === null) return
  body.innerHTML = bodyHtml(data)
}