/**
 * 会话顶部需求进度（conversation.session.header.utilities 槽位 occupant）。
 *
 * 解决的真实痛点（用户原话）：「agent 时间长，我总忘记之前都做了什么」——
 * 一个会话跑到一半回过头来，人不知道这个需求做到哪一步、还剩什么、谁在什么时候
 * 推进过。本组件把**该会话绑定的进行中需求**的流程图直接展示在模式选择器后面：
 *   - 显示态：流程图（立项→需求分析→技术设计→拆分→实施→验收→完成）始终可见；
 *   - 详情展开：点击流程图任意位置展开完整详情面板（任务清单 + 状态时间线）。
 *
 * 数据来源：GET /dashboard/api/reqboard/session/:sessionId/progress（host 侧按
 * requirement.sourceSessionId 锚点，回退到任务执行记录的 sessionId 锚点）。
 * 无绑定需求时组件返回 null（零噪音，与 capture/bound section 同哲学）。
 *
 * @module dsh-pmboard/client/conversation-progress
 */
import { createElement as h, useState, useEffect, useRef, type ReactNode } from 'react'
import { OPEN_EVENT } from './footer-action.ts'

const BASE = '/dashboard/api/reqboard'

/** 需求流水线（与 host 状态机同序）——流程图节点。 */
const FLOW: ReadonlyArray<{ key: string; label: string }> = [
  { key: 'draft', label: '立项' },
  { key: 'brainstorming', label: '需求分析' },
  { key: 'planning', label: '技术设计' },
  { key: 'decomposing', label: '拆分' },
  { key: 'implementing', label: '实施' },
  { key: 'accepting', label: '验收' },
  { key: 'done', label: '完成' },
]

const STATUS_LABEL: Record<string, string> = {
  draft: '立项', brainstorming: '需求分析', planning: '技术设计', decomposing: '拆分',
  implementing: '实施中', accepting: '待验收', done: '完成', archived: '归档', canceled: '已取消',
}

const TASK_ICON: Record<string, string> = {
  todo: '○', in_progress: '◐', integrating: '⇄', testing: '⚗', in_review: '👁', done: '✓', canceled: '✕',
}

const TASK_LABEL: Record<string, string> = {
  todo: '待办', in_progress: '开发中', integrating: '联调中', testing: '测试中',
  in_review: '待评审', done: '已完成', canceled: '已取消',
}

interface ProgressPayload {
  hasRequirement?: boolean
  /** true = 该会话已无进行中需求，展示的是「最近完成」锚点 */
  closed?: boolean
  sessionId?: string
  requirement?: {
    id?: string; title?: string; description?: string; status?: string
    category?: string | null; blocked?: boolean; paused?: boolean
    sourceSessionId?: string | null; updatedAt?: number
  }
  progress?: { total?: number; done?: number; active?: number; percentage?: number; byStatus?: Record<string, number> }
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

/** 毫秒 → 人类可读时长（用于任务已投入时间）。 */
function fmtDur(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return ''
  const m = Math.floor(ms / 60000)
  if (m < 60) return `${m}m`
  const hours = Math.floor(m / 60)
  return `${hours}h${m % 60 > 0 ? String(m % 60).padStart(2, '0') : ''}`
}

/** 时间戳 → MM-DD HH:mm。 */
function fmtWhen(ts: number | undefined): string {
  if (typeof ts !== 'number' || !Number.isFinite(ts)) return ''
  const d = new Date(ts)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 操作者 → 短标识（人/窗口/系统）。 */
function actorLabel(by: { kind?: string; sessionId?: string } | undefined): string {
  if (by === undefined) return ''
  if (by.kind === 'human') return '人'
  if (by.kind === 'system') return '系统'
  const sid = by.sessionId
  return typeof sid === 'string' && sid.length > 0 ? `w-${sid.replace(/^session-/, '').slice(0, 8)}` : '窗口'
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

  const req = data?.requirement
  if (data === null || data.hasRequirement !== true || req === undefined || req === null) return null

  const pct = data.progress?.percentage ?? 0
  const done = data.progress?.done ?? 0
  const total = data.progress?.total ?? 0
  const status = req.status ?? 'draft'
  const currentIndex = FLOW.findIndex(f => f.key === status)
  const title = req.title ?? '（未命名需求）'
  const closed = data.closed === true

  // ---- 流程图节点（始终可见，可点击）----
  const flowNodes: ReactNode[] = []
  FLOW.forEach((stage, idx) => {
    const st = flowState(idx, currentIndex)
    const isSelected = selectedStage === stage.key
    flowNodes.push(
      h('div', {
        key: `n-${stage.key}`,
        className: 'dsh-pm-flow-node',
        'data-state': st,
        'data-selected': isSelected ? 'true' : undefined,
        onClick: (e: MouseEvent) => {
          e.stopPropagation()
          setSelectedStage(stage.key)
          setDetailOpen(true)
        },
      }, [
        h('span', { key: 'd', className: 'dsh-pm-flow-dot' }, st === 'done' ? '✓' : st === 'current' ? '●' : idx + 1),
        h('span', { key: 'l', className: 'dsh-pm-flow-label' }, stage.label),
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

  // ---- 详情面板：根据选中阶段显示对应内容 ----
  const tasks = data.tasks ?? []
  const selectedStageInfo = FLOW.find(f => f.key === selectedStage)
  const selectedStageLabel = selectedStageInfo?.label ?? '详情'

  // 筛选属于当前选中阶段的任务和时间线
  const stageTasksMap: Record<string, typeof tasks> = {
    draft: tasks.filter(t => t.phase === 'draft' || t.status === 'todo'),
    brainstorming: tasks.filter(t => t.phase === 'brainstorming' || t.phase === 'analysis'),
    planning: tasks.filter(t => t.phase === 'planning' || t.phase === 'design'),
    decomposing: tasks.filter(t => t.phase === 'decomposing' || t.phase === 'breakdown'),
    implementing: tasks.filter(t => t.status === 'in_progress' || t.status === 'integrating' || t.phase === 'implement'),
    accepting: tasks.filter(t => t.status === 'testing' || t.status === 'in_review' || t.phase === 'review' || t.phase === 'test'),
    done: tasks.filter(t => t.status === 'done'),
  }

  const stageTasks = selectedStage ? (stageTasksMap[selectedStage] ?? tasks) : tasks
  const taskRows = stageTasks.length === 0
    ? [h('div', { key: 'empty', className: 'dsh-pm-cprog-empty' },
        selectedStage ? `${selectedStageLabel}阶段暂无任务` : '尚未拆分任务')]
    : stageTasks.map((t, i) =>
        h('div', { key: t.id ?? `t${i}`, className: 'dsh-pm-cprog-task', 'data-status': t.status ?? 'todo' }, [
          h('span', { key: 'i', className: 'dsh-pm-cprog-task-ico' }, TASK_ICON[t.status ?? 'todo'] ?? '○'),
          h('div', { key: 'b', className: 'dsh-pm-cprog-task-body' }, [
            h('div', { key: 't', className: 'dsh-pm-cprog-task-title' }, t.title ?? t.id ?? ''),
            h('div', { key: 'm', className: 'dsh-pm-cprog-task-meta' },
              [
                TASK_LABEL[t.status ?? ''] ?? t.status ?? '',
                t.side !== undefined && t.side.length > 0 ? `· ${t.side}` : '',
                (() => { const d = fmtDur(t.durationMs ?? 0); return d.length > 0 ? `· 已投入 ${d}` : '' })(),
              ].filter(s => s.length > 0).join(' ')),
          ]),
        ]),
      )

  const tl = (data.timeline ?? []).slice(-8).reverse()
  const stageTl = selectedStage
    ? tl.filter(e => e.status === selectedStage)
    : tl
  const timelineRows = stageTl.length === 0
    ? [h('div', { key: 'empty', className: 'dsh-pm-cprog-empty' },
        selectedStage ? `${selectedStageLabel}阶段暂无状态记录` : '暂无状态记录')]
    : stageTl.map((e, i) =>
        h('div', { key: `tl${i}`, className: 'dsh-pm-cprog-tl-row' }, [
          h('span', { key: 't', className: 'dsh-pm-cprog-tl-time' }, fmtWhen(e.at)),
          h('span', { key: 'x', className: 'dsh-pm-cprog-tl-text' },
            `${STATUS_LABEL[e.status ?? ''] ?? e.status ?? ''}${actorLabel(e.by).length > 0 ? ` by ${actorLabel(e.by)}` : ''}${typeof e.reason === 'string' && e.reason.length > 0 ? ` — ${e.reason}` : ''}${e.inferred === true ? '（回填）' : ''}`),
        ]),
      )

  const panel = h('div', { key: 'panel', className: 'dsh-pm-cprog-detail-panel' }, [
    h('div', { key: 'h', className: 'dsh-pm-cprog-panel-head' }, [
      h('span', { key: 't', className: 'dsh-pm-cprog-panel-title' },
        selectedStage ? `${selectedStageLabel} · ${req.id ?? ''}` : `${req.id ?? ''} · ${title}`),
      h('span', { key: 's', className: 'dsh-pm-status-badge', 'data-status': selectedStage ?? status },
        selectedStage ? selectedStageLabel : (STATUS_LABEL[status] ?? status)),
    ]),
    closed
      ? h('div', { key: 'closed', className: 'dsh-pm-cprog-panel-note' },
          '本会话已无进行中需求 —— 以上是最近关联的需求（已完成/已归档），可作为「这个会话做了什么」的回顾。')
      : null,
    typeof req.description === 'string' && req.description.length > 0 && !selectedStage
      ? h('div', { key: 'd', className: 'dsh-pm-cprog-panel-sub' }, req.description)
      : null,
    h('div', { key: 'p', className: 'dsh-pm-cprog-sec' }, [
      h('b', { key: 'b' }, selectedStage
        ? `${selectedStageLabel}阶段任务（${stageTasks.filter(t => t.status === 'done').length}/${stageTasks.length} 完成）`
        : `任务（${done}/${total} 完成，${data.progress?.active ?? 0} 进行中）`),
      ...taskRows,
    ]),
    h('div', { key: 'tl', className: 'dsh-pm-cprog-sec' }, [
      h('b', { key: 'b' }, selectedStage ? `${selectedStageLabel}阶段时间线` : '状态时间线（最近 8 条）'),
      ...timelineRows,
    ]),
    h('div', { key: 'ft', className: 'dsh-pm-cprog-foot' }, [
      selectedStage
        ? h('button', {
            key: 'back', type: 'button', className: 'dsh-pm-btn sm',
            onClick: () => { setSelectedStage(null) },
          }, '← 返回全部')
        : null,
      h('button', {
        key: 'open', type: 'button', className: 'dsh-pm-btn sm',
        onClick: () => { window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { open: true } })) },
      }, '打开项目看板'),
      h('button', {
        key: 'rf', type: 'button', className: 'dsh-pm-btn sm',
        onClick: () => { setDetailOpen(false); setSelectedStage(null) },
      }, '收起'),
    ]),
  ])

  return h('div', { className: 'dsh-pm-cprog', ref: wrapRef }, [flowChart, panel])
}
