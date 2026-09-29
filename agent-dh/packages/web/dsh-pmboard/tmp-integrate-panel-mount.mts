/**
 * 联调 harness（integrate 阶段 · 一次性脚本，非交付物）
 *
 * 验证「会话面板挂载钩子（DOM 就绪后挂载）」的接口链：
 *   请求样例：会话面板展开（detailOpen=true）+ 所选阶段 ∈ {implementing, decomposing}（body.tasks 非空）
 *   期望响应：np-dag-canvas 被**真实挂载**（getContext 调用 / dblclick 绑定 / ResizeObserver observe /
 *             统计条标「（推导）」——因为不传 ready，对齐 FR-7）
 *
 * 被验的代码全部是真实模块，无替身业务逻辑：
 *   - src/client/conversation-progress.ts 的真实 useEffect（经 mini React dispatcher 驱动**真实组件函数**）
 *   - src/client/node-panel.ts 的 renderNodePanel（面板 HTML 生产端）
 *   - src/client/dag-mount.ts 的 tryMountDagCanvas
 *   - src/client/views/dag-view.ts 的 mountDagCanvas
 *
 * 环境说明（诚实标注）：本仓未装 jsdom/happy-dom（node_modules 实测只有 react/react-dom），
 * 故 DOM 用「按 id 注册表」最小替身；Node 无 requestAnimationFrame，用同步桩（回调立即执行）。
 * 这两点只影响"怎么把 DOM 摆出来"，不影响被验的接口链本身。
 */
import React from 'react'
import { PANEL_DAG_CANVAS_ID } from './src/client/views/dag-view.js'

// ---------------------------------------------------------------------------
// 最小 DOM 替身
// ---------------------------------------------------------------------------
interface Stub { canvas: any; removed: number; getContexts: number; dblclicks: number; dismissResize: number; stat: { innerHTML: string } }

const noop = (): void => { /* 替身不该有真实行为 */ }
const registry = new Map<string, Stub>()
const observers: { connected: number; disconnected: number }[] = []

function mkStub(): Stub {
  const st: Stub = { canvas: undefined, removed: 0, getContexts: 0, dblclicks: 0, dismissResize: 0, stat: { innerHTML: '' } }
  const ctx: any = {
    save: noop, restore: noop, beginPath: noop, closePath: noop, moveTo: noop, lineTo: noop,
    quadraticCurveTo: noop, bezierCurveTo: noop, clip: noop, fill: noop, stroke: noop,
    clearRect: noop, setLineDash: noop, setTransform: noop, arc: noop,
    measureText: (s: string) => ({ width: String(s).length * 6 }), fillRect: noop, fillText: noop,
  }
  for (const k of ['font', 'fillStyle', 'strokeStyle', 'lineWidth', 'globalAlpha', 'textAlign', 'textBaseline', 'lineCap', 'shadowColor', 'shadowBlur'])
    Object.defineProperty(ctx, k, { set: noop, get: () => undefined })
  const panel: any = {
    addEventListener: noop, removeEventListener: noop,
    querySelector: (sel: string) => (sel === '[data-dag-stat]' ? st.stat : (sel === '[data-dag-wrap]' ? { clientWidth: 690 } : null)),
    querySelectorAll: () => [], contains: () => true,
  }
  const handlers: Record<string, (ev: any) => void> = {}
  const canvas: any = {
    width: 0, height: 0, style: {}, dataset: {}, classList: { toggle: noop, add: noop, remove: noop },
    parentElement: { clientWidth: 690, appendChild: () => {} },
    getContext: () => { st.getContexts++; return ctx },
    closest: () => panel,
    addEventListener: (t: string, fn: (ev: any) => void) => { if (t === 'dblclick') { st.dblclicks++; handlers[t] = fn } },
    removeEventListener: (t: string) => { if (t === 'dblclick') { st.removed++; delete handlers[t] } },
    getBoundingClientRect: () => ({ left: 0, top: 0 }),
    __handlers: handlers,
  }
  st.canvas = canvas
  return st
}

;(globalThis as any).document = {
  getElementById: (id: string) => registry.get(id)?.canvas ?? null,
  createElement: () => ({ dataset: {}, appendChild() {}, click() {}, remove() {} }),
  addEventListener: noop,
  removeEventListener: noop,
}
;(globalThis as any).window = {
  setInterval: () => 0, clearInterval: noop, addEventListener: noop, removeEventListener: noop,
  setTimeout: (fn: any, ms: number) => setTimeout(fn, ms),
}
;(globalThis as any).ResizeObserver = class {
  private rec = { connected: 0, disconnected: 0 }
  constructor(_cb: any) { observers.push(this.rec) }
  observe() { this.rec.connected++ }
  disconnect() { this.rec.disconnected++ }
}
;(globalThis as any).requestAnimationFrame = (cb: any) => { cb(0); return 1 }
;(globalThis as any).EventSource = class { onmessage: any; close() { /* stub */ } }

// ---------------------------------------------------------------------------
// fetch 替身（按 URL 路由；返回体形状与 host 接口一致：{success, data}）
// ---------------------------------------------------------------------------
let progressPayload: any = null
let overviewPayload: any = null
const mkRes = (json: any) => ({ ok: json.success === true, status: json.success === true ? 200 : 500, json: async () => json })
;(globalThis as any).fetch = async (url: any) => {
  const u = String(url)
  if (u.includes('/progress')) return mkRes(progressPayload)
  if (u.includes('/stages')) return mkRes(overviewPayload)
  return mkRes({ success: false, error: 'unexpected url: ' + u })
}

// ---------------------------------------------------------------------------
// mini React dispatcher：执行**真实组件函数**的 hooks（useState/useRef/useEffect）
// ---------------------------------------------------------------------------
const Comp = (await import('./src/client/conversation-progress.ts')).RequirementProgressAction as any
const internals: any = (React as any).__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED

let hookStates: any[] = []
let hookIndex = 0
let pendingEffects: { slot: number; fn: any }[] = []
let cleanups = new Map<number, any>()
let dirty = false

const dispatcher = {
  useState(init: any) {
    const i = hookIndex++
    if (!(i in hookStates)) hookStates[i] = typeof init === 'function' ? init() : init
    const set = (v: any) => {
      const next = typeof v === 'function' ? v(hookStates[i]) : v
      if (Object.is(hookStates[i], next)) return
      hookStates[i] = next
      dirty = true
    }
    return [hookStates[i], set]
  },
  useRef(init: any) {
    const i = hookIndex++
    if (!(i in hookStates) || hookStates[i] === undefined) hookStates[i] = { current: init }
    return hookStates[i]
  },
  useEffect(fn: any, deps: any) {
    const i = hookIndex++
    const prev = hookStates[i] as { deps?: any[] } | undefined
    const same = prev !== undefined && deps !== undefined && prev.deps !== undefined &&
      deps.length === prev.deps.length && deps.every((d: any, k: number) => Object.is(d, prev.deps![k]))
    if (!same) pendingEffects.push({ slot: i, fn })
    hookStates[i] = { deps }
  },
  useMemo(fn: any) { return fn() },
  useCallback(fn: any) { return fn },
}

// ---------------------------------------------------------------------------
// 渲染驱动（commit 面板 HTML → DOM 注册表 → flush effects）
// ---------------------------------------------------------------------------
function walk(node: any, fn: (el: any) => void): void {
  if (node === null || node === undefined || typeof node === 'boolean' || typeof node === 'string' || typeof node === 'number') return
  if (Array.isArray(node)) { for (const c of node) walk(c, fn); return }
  if (typeof node === 'object' && node.props !== undefined) { fn(node); walk(node.props.children, fn) }
}

function commit(tree: any): void {
  walk(tree, (el) => {
    const html = el?.props?.dangerouslySetInnerHTML?.__html
    if (typeof html !== 'string') return
    const m = /<canvas id="([^"]+)"/.exec(html)
    if (m === null) return
    if (!registry.has(m[1])) registry.set(m[1], mkStub())   // 模拟 React commit：面板 HTML 进 DOM
  })
}

async function flushEffects(): Promise<void> {
  const list = pendingEffects
  pendingEffects = []
  for (const it of list) {
    const prev = cleanups.get(it.slot)
    if (typeof prev === 'function') prev()
    cleanups.set(it.slot, it.fn())
  }
  await new Promise((r) => setTimeout(r, 0))
}

async function cycle(props: any): Promise<any> {
  for (let k = 0; k < 40; k++) {
    dirty = false
    hookIndex = 0
    pendingEffects = []
    ;(internals.ReactCurrentDispatcher as any).current = dispatcher
    let tree: any
    try { tree = Comp(props) } finally { (internals.ReactCurrentDispatcher as any).current = null }
    commit(tree)
    await flushEffects()
    if (!dirty) return tree
  }
  throw new Error('component did not converge in 40 cycles')
}

function clickFlowNode(tree: any, key: string): boolean {
  let found = false
  walk(tree, (el) => {
    if (el.key === key && typeof el.props?.onClick === 'function') {
      el.props.onClick({ stopPropagation() {}, preventDefault() {} })
      found = true
    }
  })
  return found
}

// ---------------------------------------------------------------------------
// 样例数据（StageOverview，与 shared/protocol.ts 契约一致）
// ---------------------------------------------------------------------------
function taskRef(id: string, title: string, dependsOn: string[] = []): any {
  return { id, title, status: 'todo', phase: 'implement', side: 'fullstack', dependsOn, acceptance: '跑通即过' }
}
const TASKS = [taskRef('t-p1', '父卡'), taskRef('t-s1', '独立卡', ['t-p1'])]

function stageDetail(stage: string, body: any, enabled = true): any {
  return { stage, enabled, artifacts: [], pendingConfirmation: false, timeline: [], ...(body === null ? {} : { body }) }
}

function overview(currentStage: string, stages: any[]): any {
  return { requirementId: 'REQ-intg', category: 'feature', currentStage, stages }
}

const ERRORS: string[] = []
process.on('uncaughtException', (e) => { ERRORS.push('uncaught: ' + String((e as Error)?.message ?? e)) })

interface CaseResult { pass: boolean; expected: string; actual: any }
const report: Record<string, CaseResult> = {}
const ok = (name: string, pass: boolean, extra: any = {}, expected = ''): void => {
  report[name] = { pass, expected, actual: extra }
}

async function runCase(opts: {
  name: string
  status: string
  overviewCurrent?: string
  stages: any[]
  openStage: string | null
  preRegisterCanvas?: boolean
  overviewFails?: boolean
  canvasId?: string
}): Promise<{ tree: any; stub: Stub | undefined }> {
  // 每例重置 hooks/effects/DOM 注册表（模块级 disposers 表刻意不重置：同名重挂必须能释放旧条目）
  for (const c of cleanups.values()) if (typeof c === 'function') c()
  cleanups = new Map()
  hookStates = []
  dirty = false
  registry.clear()
  progressPayload = {
    success: true,
    data: {
      hasRequirement: true, closed: false, sessionId: 'session-intg',
      requirement: { id: 'REQ-intg', title: '联调样例', status: opts.status, category: 'feature' },
      progress: { done: 1, total: 3, active: 1, percentage: 33, byStatus: {} },
      nodes: [], timeline: [], tasks: [],
    },
  }
  overviewPayload = opts.overviewFails === true
    ? { success: false, error: 'stage overview unavailable' }
    : { success: true, data: overview(opts.overviewCurrent ?? opts.status, opts.stages) }

  const canvasId = opts.canvasId ?? PANEL_DAG_CANVAS_ID
  if (opts.preRegisterCanvas === true) registry.set(canvasId, mkStub())

  let tree = await cycle({ sessionId: 'session-intg' })
  if (opts.openStage !== null) {
    const clicked = clickFlowNode(tree, 'n-' + opts.openStage)
    if (!clicked) throw new Error(opts.name + ': 未找到流程节点 n-' + opts.openStage)
    tree = await cycle({ sessionId: 'session-intg' })
  }
  return { tree, stub: registry.get(canvasId) }
}

// ---------------------------------------------------------------------------
// 用例
// ---------------------------------------------------------------------------
const implDetail = stageDetail('implementing', { tasks: TASKS, byWindow: { 'w-intg': ['t-p1'] } })
const decDetail = stageDetail('decomposing', { tasks: TASKS, planTasks: [], decompositionDoc: 'docs/requirements/REQ-intg/decomposition.md' })
const designDetail = stageDetail('design', { plan: undefined, designDocs: [] })

// 1. implementing（请求样例 ①：会话面板展开 + 所选阶段=implementing）
{
  const { stub } = await runCase({ name: '1.impl', status: 'implementing', stages: [designDetail, decDetail, implDetail], openStage: 'implementing' })
  ok('1.implementing_mounts_panel_canvas',
    stub !== undefined && stub.getContexts >= 1 && stub.dblclicks === 1 && stub.removed === 0 &&
      observers.some(o => o.connected >= 1),
    { canvasId: PANEL_DAG_CANVAS_ID, getContexts: stub?.getContexts, dblclickBound: stub?.dblclicks, listenersRemoved: stub?.removed, observersConnected: observers.filter(o => o.connected > 0).length, statHasDerived: /推导/.test(stub?.stat.innerHTML ?? ''), statSample: (stub?.stat.innerHTML ?? '').replace(/<[^>]+>/g, ' ').trim().slice(0, 120) },
    '真实调用 tryMountDagCanvas(tasks, undefined, PANEL_DAG_CANVAS_ID) → np-dag-canvas 挂载（getContext≥1 / dblclick=1 / ResizeObserver observe / 统计条含「推导」）')
}

// 2. decomposing（请求样例 ②：另一允许阶段）
{
  const { stub } = await runCase({ name: '2.dec', status: 'decomposing', stages: [designDetail, decDetail, implDetail], openStage: 'decomposing' })
  ok('2.decomposing_mounts_panel_canvas',
    stub !== undefined && stub.getContexts >= 1 && stub.dblclicks === 1 && /推导/.test(stub.stat.innerHTML),
    { getContexts: stub?.getContexts, dblclickBound: stub?.dblclicks, statHasDerived: /推导/.test(stub?.stat.innerHTML ?? '') },
    'decomposing 同样挂载 np-dag-canvas 且统计条标「推导」（未传 ready）')
}

// 3. 阶段不在 {implementing, decomposing}：画布预置也存在，但不调用（阶段缺失/非任务阶段都不调用）
{
  const { stub } = await runCase({
    name: '3.other-stage', status: 'accepting', overviewCurrent: 'accepting',
    stages: [designDetail, decDetail, implDetail, stageDetail('accepting', { verification: undefined })],
    openStage: 'accepting', preRegisterCanvas: true,
  })
  ok('3.other_stage_no_call', stub !== undefined && stub.getContexts === 0 && stub.dblclicks === 0,
    { getContexts: stub?.getContexts, dblclickBound: stub?.dblclicks },
    '所选阶段=accepting → 不调用（画布预置仍 0 次 getContext）')
}

// 4. body.tasks 为空：不调用
{
  const emptyImpl = stageDetail('implementing', { tasks: [], byWindow: {} })
  const { stub } = await runCase({
    name: '4.empty-tasks', status: 'implementing',
    stages: [designDetail, decDetail, emptyImpl], openStage: 'implementing', preRegisterCanvas: true,
  })
  ok('4.empty_tasks_no_call', stub !== undefined && stub.getContexts === 0,
    { getContexts: stub?.getContexts },
    'implementing 但 body.tasks=[] → 不调用')
}

// 5. stageOverview 缺该阶段（find 返回 undefined）：不调用
{
  const { stub } = await runCase({
    name: '5.stage-missing', status: 'implementing',
    stages: [designDetail, decDetail], openStage: 'implementing', preRegisterCanvas: true,
  })
  ok('5.stage_missing_no_call', stub !== undefined && stub.getContexts === 0,
    { getContexts: stub?.getContexts },
    'stages 中无 implementing 条目 → 不调用')
}

// 6. stageOverview 拉取失败（面板展开但数据缺失）：不调用、不抛
{
  const { stub } = await runCase({
    name: '6.overview-fail', status: 'implementing',
    stages: [implDetail], openStage: 'implementing', preRegisterCanvas: true, overviewFails: true,
  })
  ok('6.overview_degraded_no_call', stub !== undefined && stub.getContexts === 0 && ERRORS.length === 0,
    { getContexts: stub?.getContexts, uncaughtErrors: ERRORS },
    'GET /stages 失败 → stageOverview=null → 不调用、不抛异常')
}

// 7. 面板未展开：DOM 里没有画布，effect 早退（不抛）
{
  const { stub } = await runCase({ name: '7.panel-closed', status: 'implementing', stages: [implDetail], openStage: null })
  ok('7.panel_closed_no_dom_no_throw',
    registry.get(PANEL_DAG_CANVAS_ID) === undefined && stub === undefined && ERRORS.length === 0,
    { canvasInDom: registry.has(PANEL_DAG_CANVAS_ID), uncaughtErrors: ERRORS },
    'detailOpen=false → 面板 HTML 未进 DOM（无 np-dag-canvas）→ 无调用、无异常')
}

// 8. 两块画布并存 + 同名重挂（SSE 重绘）：只释放同名，不动另一块
{
  const { stub } = await runCase({ name: '8.remount', status: 'implementing', stages: [designDetail, decDetail, implDetail], openStage: 'implementing' })
  const detailStub = mkStub()
  registry.set('dag-canvas', detailStub)
  const { tryMountDagCanvas } = await import('./src/client/dag-mount.ts')
  tryMountDagCanvas(TASKS as any, ['t-p1'])                       // 需求详情画布（不传 canvasId = 旧口径）
  registry.set(PANEL_DAG_CANVAS_ID, mkStub())                     // 面板 HTML 被重绘（换 canvas）
  tryMountDagCanvas(TASKS as any, undefined, PANEL_DAG_CANVAS_ID) // 同名重挂
  const oldPanelRemoved = stub!.removed                           // 重挂后才可观察旧实例被释放
  const newPanel = registry.get(PANEL_DAG_CANVAS_ID)!
  ok('8.coexist_and_remount_same_id',
    oldPanelRemoved === 1 && detailStub.removed === 0 && detailStub.getContexts >= 1 && newPanel.getContexts >= 1,
    { oldPanelListenersRemoved: oldPanelRemoved, detailRemoved: detailStub.removed, detailGetContexts: detailStub.getContexts, newPanelGetContexts: newPanel.getContexts, uncaughtErrors: ERRORS },
    '同名重挂释放旧面板实例（removed=1）、需求详情画布不受影响（removed=0）、新实例已挂载')
}

console.log(JSON.stringify({ cases: report, uncaughtErrors: ERRORS, allPass: Object.values(report).every(r => r.pass) && ERRORS.length === 0 }, null, 2))
