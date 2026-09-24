/**
 * 会话顶部需求进度（conversation.session.header.utilities 槽位 occupant）。
 *
 * 解决的真实痛点（用户原话）：「agent 时间长，我总忘记之前都做了什么」——
 * 一个会话跑到一半回过头来，人不知道这个需求做到哪一步、还剩什么、谁在什么时候
 * 推进过。本组件把**该会话绑定的进行中需求**的流程图直接展示在模式选择器后面：
 *   - 显示态：流程图（立项→需求分析→设计→拆分→实施→验收→完成）始终可见；
 *   - 详情展开：点击流程图任意位置展开完整详情面板（任务清单 + 状态时间线）。
 *
 * 数据来源：GET /dashboard/api/reqboard/session/:sessionId/progress（host 侧按
 * requirement.sourceSessionId 锚点，回退到任务执行记录的 sessionId 锚点）。
 * 无绑定需求时组件返回 null（零噪音，与 capture/bound section 同哲学）。
 *
 * @module dsh-pmboard/client/conversation-progress
 */
import { createElement as h, useState, useEffect, useRef, type ReactNode } from 'react'
import { openDocInSidebar } from './open-doc.ts'
import { renderNodePanel } from './node-panel.ts'
import { fetchStageOverview, fetchInjectionInfo, fetchIsolationLog } from './api.ts'
import type { StageOverview, StageKey } from '../shared/protocol.ts'
import { CATEGORY_FLOW_PROFILES, fmtTokens } from '../shared/protocol.ts'
import type { InjectionInfoEntry } from './injection-info.ts'
import type { IsolationLogEntry } from './node-panel-process.ts'

const BASE = '/dashboard/api/reqboard'

/** 需求流水线（与 host 状态机同序）——流程图节点。 */
const FLOW: ReadonlyArray<{ key: string; label: string }> = [
  { key: 'draft', label: '立项' },
  { key: 'brainstorming', label: '需求分析' },
  { key: 'design', label: '设计' },
  { key: 'decomposing', label: '拆分' },
  { key: 'implementing', label: '实施' },
  { key: 'accepting', label: '验收' },
  // REQ-9f4a44：done 节点已移除（验收通过 → 直接归档）
  { key: 'archived', label: '归档' },
]

const STATUS_LABEL: Record<string, string> = {
  draft: '立项', brainstorming: '需求分析', design: '设计', decomposing: '拆分',
  implementing: '实施中', accepting: '待验收', done: '完成', archived: '归档', canceled: '已取消',
}

interface ProgressPayload {
  hasRequirement?: boolean
  /** true = 该会话已无进行中需求，展示的是「最近完成」锚点 */
  closed?: boolean
  sessionId?: string
  requirement?: {
    id?: string; title?: string; description?: string; status?: string
    category?: string | null; blocked?: boolean; paused?: boolean
    /** REQ-260923134706-e72f / FR-2：立项四问之一的提示词难度（老记录无字段 → null，面板省略该行） */
    promptDifficulty?: string | null
    sourceSessionId?: string | null; updatedAt?: number
  }
  progress?: { total?: number; done?: number; active?: number; percentage?: number; byStatus?: Record<string, number> }
  /** REQ-a33899：每节点 token（无快照 → 该节点省略 tokens 键，UI 显示「—」） */
  nodes?: Array<{ key?: string; tokens?: { total?: number } }>
  timeline?: Array<{ status?: string; at?: number; by?: { kind?: string; sessionId?: string }; reason?: string | null; inferred?: boolean }>
  tasks?: Array<{
    id?: string; title?: string; status?: string; phase?: string; side?: string
    acceptance?: string; updatedAt?: number; durationMs?: number
  }>
}

/**
 * 解析当前会话 id：优先用槽位注入的 sessionId（session 作用域槽位会传）；
 * 兜底读会话服务的「当前会话」（sessions.list.getSnapshot().current）——
 * 某些宿主版本/时机下 inject 可能拿不到值，兜底保证组件仍能取到数据。
 */
function resolveSessionId(injected?: string): string | undefined {
  if (typeof injected === 'string' && injected.length > 0) return injected
  try {
    const w = window as unknown as {
      __dshPmSessions?: { list?: { getSnapshot?: () => { current?: unknown; currentSessionId?: unknown } } }
      __dshPmCtx?: { sessions?: { list?: { getSnapshot?: () => { current?: unknown; currentSessionId?: unknown } } } }
    }
    const svc = w.__dshPmSessions ?? w.__dshPmCtx?.sessions
    const snap = svc?.list?.getSnapshot?.()
    const cur = snap?.current ?? snap?.currentSessionId
    if (typeof cur === 'string' && cur.length > 0) return cur
  } catch { /* 降级：拿不到就不渲染 */ }
  return undefined
}

/** 流程图节点状态：已完成 / 当前 / 未到。 */
function flowState(index: number, currentIndex: number): 'done' | 'current' | 'pending' {
  if (currentIndex < 0) return 'pending'
  if (index < currentIndex) return 'done'
  if (index === currentIndex) return 'current'
  return 'pending'
}

export interface RequirementProgressProps {
  /** 由槽位 inject(sessionId) 注入（session 作用域槽位）。 */
  sessionId?: string
}



/**
 * 会话标题栏的需求进度流程图。无绑定需求 → 渲染 null（槽位不占位）。
 */
export function RequirementProgressAction(props: RequirementProgressProps): ReactNode {
  const injectedId = props?.sessionId
  const [data, setData] = useState<ProgressPayload | null>(null)
  const [detailOpen, setDetailOpen] = useState<boolean>(false)
  const [selectedStage, setSelectedStage] = useState<string | null>(null)
  // REQ-31e11f 重设计：全流程一览（一次加载全部节点，监控时间线一眼看全）
  const [stageOverview, setStageOverview] = useState<StageOverview | null>(null)
  const [stageOverviewLoading, setStageOverviewLoading] = useState<boolean>(false)
  const [stageOverviewErr, setStageOverviewErr] = useState<string>('')
  // REQ-260923134706-e72f t6：执行流程折叠的注入/隔离留痕（随面板打开拉取，失败静默空态）
  const [injection, setInjection] = useState<InjectionInfoEntry[]>([])
  const [isolation, setIsolation] = useState<IsolationLogEntry[]>([])
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const lastSid = useRef<string | undefined>(undefined)


  // 数据：挂载即拉一次，之后 15s 轮询（进度是辅助信息，失败静默不打扰）。
  // 会话 id 每次求值都走 resolveSessionId —— 槽位注入拿不到时用「当前会话」兜底，
  // 切换会话也能在下一个 tick 跟上。
  useEffect(() => {
    let alive = true
    const load = async (): Promise<void> => {
      const sid = resolveSessionId(injectedId)
      if (sid === undefined) {
        if (alive) { lastSid.current = undefined; setData(null) }
        return
      }
      if (sid !== lastSid.current) {
        // 会话变了：先清空旧数据，避免显示上一个会话的需求
        lastSid.current = sid
        if (alive) setData(null)
      }
      try {
        const res = await fetch(`${BASE}/session/${encodeURIComponent(sid)}/progress`, {
          signal: AbortSignal.timeout(8000),
        })
        if (!res.ok) return
        const json = (await res.json()) as { success?: boolean; data?: ProgressPayload }
        if (!alive) return
        setData(json.success === true ? (json.data ?? null) : null)
      } catch { /* 静默：进度条不可用不影响会话 */ }
    }
    void load()
    const timer = window.setInterval(() => { void load() }, 15000)
    return () => { alive = false; window.clearInterval(timer) }
  }, [injectedId])

  // 展开详情时点外部关闭
  useEffect(() => {
    if (!detailOpen) return
    const onDoc = (ev: MouseEvent): void => {
      const el = wrapRef.current
      if (el !== null && !el.contains(ev.target as Node)) setDetailOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [detailOpen])

  // REQ-31e11f 重设计：展开即加载全流程一览（StageOverview，与看板同源）。
  // 依赖 req.updatedAt —— 需求有任何推进（状态/任务/评论变化）自动刷新，
  // 刷新时经 openStagesRef 保留用户手动展开态（真监控，不打断阅读）。
  const reqIdForStage = data?.requirement?.id
  const reqUpdatedAt = data?.requirement?.updatedAt
  useEffect(() => {
    if (!detailOpen || reqIdForStage === undefined) {
      setStageOverview(null)
      return
    }
    let alive = true
    setStageOverviewLoading(true)
    setStageOverviewErr('')
    fetchStageOverview(reqIdForStage)
      .then((d) => { if (alive) setStageOverview(d) })
      .catch((e) => { if (alive) setStageOverviewErr((e as Error).message) })
      .finally(() => { if (alive) setStageOverviewLoading(false) })
    return () => { alive = false }
  }, [detailOpen, reqIdForStage, reqUpdatedAt])

  // REQ-260923134706-e72f t6：面板打开时拉取该需求来源窗口的注入/隔离留痕，
  // 供「执行流程」折叠做 规定 vs 实际 对照（无留痕 → 空态，不红不打扰）。
  const reqSourceSid = data?.requirement?.sourceSessionId
  useEffect(() => {
    if (!detailOpen || reqIdForStage === undefined) { setInjection([]); setIsolation([]); return }
    let alive = true
    // 注入/隔离留痕的 windowKey = 完整会话 id（实测 injection-log/isolation-log 均存 session-xxx 全码），
    // 不是 w- 短码——直接用 sourceSessionId 过滤，windowCodeFromSessionId 会失配返回空。
    const windowKey = typeof reqSourceSid === 'string' && reqSourceSid.length > 0 ? reqSourceSid : undefined
    fetchInjectionInfo(windowKey, 20)
      .then((r) => { if (alive) setInjection(r.available === false ? [] : r.entries) })
      .catch(() => { if (alive) setInjection([]) })
    fetchIsolationLog(windowKey, 20)
      .then((r) => { if (alive) setIsolation(r.available === false ? [] : r.entries) })
      .catch(() => { if (alive) setIsolation([]) })
    return () => { alive = false }
  }, [detailOpen, reqIdForStage, reqSourceSid])

  // REQ-260923134706-e72f t6：实施节点 [流程图][泳道] tab 切换（注入 HTML 内的委托监听）。
  useEffect(() => {
    const onClick = (ev: MouseEvent): void => {
      const t = (ev.target as HTMLElement).closest('[data-action="np-switch-view"]') as HTMLElement | null
      if (t === null) return
      ev.preventDefault()
      ev.stopPropagation()
      const panel = t.closest('.dsh-pm-np')
      if (panel === null) return
      const view = t.getAttribute('data-view')
      for (const tab of Array.from(panel.querySelectorAll<HTMLElement>('.dsh-pm-np-tab'))) {
        tab.classList.toggle('is-active', tab.getAttribute('data-view') === view)
      }
      for (const pane of Array.from(panel.querySelectorAll<HTMLElement>('.dsh-pm-np-pane'))) {
        pane.hidden = pane.getAttribute('data-pane') !== view
      }
    }
    document.addEventListener('click', onClick)
    return () => document.removeEventListener('click', onClick)
  }, [])

  // 产物文档链接（注入 HTML 里的 data-action="open-doc"）→ 官方右侧栏打开全文（REQ-ff20ca t5）。
  // 挂 document 级（wrapRef 在 detailOpen 切换时被 React 重建，挂它上面 listener 会丢）。
  // 弹窗已按 G2 移除：不再有降级分支，sidebarRight 不可用时由 openDocInSidebar 打印诊断。
  useEffect(() => {
    const onClick = (ev: MouseEvent): void => {
      const t = (ev.target as HTMLElement).closest('[data-action="open-doc"]') as HTMLElement | null
      if (t === null) return
      ev.preventDefault()
      ev.stopPropagation()
      const path = t.getAttribute('data-path')
      if (path === null || path.length === 0) return
      openDocInSidebar(window.__dshPmCtx, path, resolveSessionId(injectedId))
    }
    document.addEventListener('click', onClick)
    return () => document.removeEventListener('click', onClick)
  }, [injectedId])

  const req = data?.requirement
  if (data === null || data.hasRequirement !== true || req === undefined || req === null) return null

  const done = data.progress?.done ?? 0
  const total = data.progress?.total ?? 0
  const status = req.status ?? 'draft'
  const currentIndex = FLOW.findIndex(f => f.key === status)
  const title = req.title ?? '（未命名需求）'
  const closed = data.closed === true

  // ---- 流程图节点（始终可见，可点击）----
  // 分类差异化流程（REQ-31e11f）：该分类跳过的节点标灰，与缺产物标红区分。
  const category = (req.category ?? 'feature') as keyof typeof CATEGORY_FLOW_PROFILES
  const profile = CATEGORY_FLOW_PROFILES[category] ?? CATEGORY_FLOW_PROFILES.feature
  const skippedStages = new Set(FLOW.filter(f => !(profile.stages as readonly string[]).includes(f.key)).map(f => f.key))
  // REQ-a33899：每节点 token。**与节点名同一行水平放置**（既有样式不变：圆点在上、名称在下）
  const nodeTokens = new Map<string, number>()
  for (const n of data.nodes ?? []) {
    if (typeof n.key === 'string' && typeof n.tokens?.total === 'number') nodeTokens.set(n.key, n.tokens.total)
  }
  const flowNodes: ReactNode[] = []
  FLOW.forEach((stage, idx) => {
    const st = flowState(idx, currentIndex)
    const isSelected = selectedStage === stage.key
    const skipped = skippedStages.has(stage.key)
    flowNodes.push(
      h('div', {
        key: `n-${stage.key}`,
        className: 'dsh-pm-flow-node',
        'data-state': skipped ? 'skipped' : st,
        'data-selected': isSelected ? 'true' : undefined,
        title: skipped ? `本分类（${category}）跳过「${stage.label}」` : undefined,
        onClick: (e: MouseEvent) => {
          e.stopPropagation()
          setSelectedStage(stage.key)
          setDetailOpen(true)
        },
      }, [
        h('span', { key: 'd', className: 'dsh-pm-flow-dot' }, skipped ? '—' : st === 'done' ? '✓' : st === 'current' ? '●' : idx + 1),
        h('div', { key: 'm', className: 'dsh-pm-flow-meta' }, [
          h('span', { key: 'l', className: 'dsh-pm-flow-label' }, stage.label),
          ...(nodeTokens.has(stage.key)
            ? [h('span', { key: 't', className: 'dsh-pm-flow-token' }, fmtTokens(nodeTokens.get(stage.key)!))]
            : []),
        ]),
      ]),
    )
    if (idx < FLOW.length - 1) {
      flowNodes.push(
        h('div', { key: `l-${stage.key}`, className: 'dsh-pm-flow-link', 'data-state': idx < currentIndex ? 'done' : 'pending' }),
      )
    }
  })

  // 流程图容器
  const flowChart = h(
    'div',
    {
      key: 'flow',
      className: `dsh-pm-cprog-inline${closed ? ' is-closed' : ''}`,
      title: `${req.id ?? ''}《${title}》${STATUS_LABEL[status] ?? status}${closed ? '（本会话最近完成）' : ''} · 点击节点查看详情`,
      'aria-expanded': detailOpen,
    },
    [
      h('div', { key: 'f', className: 'dsh-pm-flow' }, flowNodes),
      h('span', { key: 'c', className: 'dsh-pm-cprog-inline-count' },
        total > 0 ? `${done}/${total}` : (STATUS_LABEL[status] ?? status)),
    ],
  )

  if (!detailOpen) return h('div', { className: 'dsh-pm-cprog', ref: wrapRef }, flowChart)

  // ---- 详情面板（REQ-260923134706-e72f t6：node-panel 渲染器，苹果风，无遮罩/无底部按钮）----
  const closePanel = (): void => { setDetailOpen(false); setSelectedStage(null) }
  const panelChildren: ReactNode[] = [
    // × 关闭按钮（右上角，取代原「收起」）
    h('button', { key: 'x', type: 'button', className: 'dsh-pm-np-close', 'aria-label': '关闭', onClick: closePanel }, '×'),
  ]
  if (closed) {
    panelChildren.push(
      h('div', { key: 'closed', className: 'dsh-pm-cprog-panel-note' },
        '本会话已无进行中需求 —— 以上是最近关联的需求（已完成/已归档），可作为「这个会话做了什么」的回顾。'),
    )
  }
  if (stageOverviewLoading && stageOverview === null) {
    panelChildren.push(h('div', { key: 'ld', className: 'dsh-pm-cprog-empty' }, '详情加载中…'))
  } else if (stageOverviewErr.length > 0 && stageOverview === null) {
    panelChildren.push(h('div', { key: 'er', className: 'dsh-pm-cprog-empty' }, `详情暂不可用：${stageOverviewErr}`))
  } else if (stageOverview !== null) {
    panelChildren.push(h('div', {
      key: 'ovr',
      className: 'dsh-pm-cprog-stage-detail',
      dangerouslySetInnerHTML: {
        __html: renderNodePanel({
          overview: stageOverview,
          stage: (selectedStage ?? stageOverview.currentStage) as StageKey,
          requirement: { id: req.id ?? '', title, promptDifficulty: req.promptDifficulty ?? null, category: req.category ?? undefined },
          injection,
          isolation,
        }),
      },
    }))
  } else {
    panelChildren.push(h('div', { key: 'ne', className: 'dsh-pm-cprog-empty' }, '暂无详情'))
  }
  const panel = h('div', { key: 'panel', className: 'dsh-pm-cprog-detail-panel' }, panelChildren)

  return h('div', { className: 'dsh-pm-cprog', ref: wrapRef }, [flowChart, panel])
}