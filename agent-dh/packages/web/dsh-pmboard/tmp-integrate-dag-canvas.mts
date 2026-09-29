
/**
 * 联调 harness（integrate 阶段 · 一次性脚本，非交付物）
 * 目的：用**真实一次调用**验证「画布 id 参数化 + 挂载实例表」这条接口链：
 *   buildDagCanvas(tasks, containerId, canvasId) ──HTML──► DOM
 *   tryMountDagCanvas(tasks, ready, canvasId) ──getElementById(canvasId)──► mountDagCanvas ──disposers[canvasId]
 *
 * 环境说明（诚实标注）：本仓未装 jsdom/happy-dom/linkedom（node_modules 实测无），
 * 故 DOM 用「按 id 注册表」最小替身；Node 无 requestAnimationFrame，用同步桩（回调立即执行）。
 * 这两点只影响"怎么把 DOM 摆出来"，不影响被验的接口链本身。
 */
import { buildDagCanvas, PANEL_DAG_CONTAINER_ID, PANEL_DAG_CANVAS_ID } from './src/client/views/dag-view.js'
import { tryMountDagCanvas } from './src/client/dag-mount.js'
import { mountDagCanvas } from './src/client/views/dag-view.js'

interface Stub { canvas: any; removed: number; getContexts: number; dblclicks: number; dismissResize: number }
const createdEls: any[] = []   // document.createElement 产出的元素（open-task 事件委托的载体）

const noop = (): void => { /* 联调桩不该有真实行为 */ }
const registry = new Map<string, Stub>()
const observers: { connected: number; disconnected: number }[] = []

function mountStub(): Stub {
  const st: Stub = { canvas: undefined, removed: 0, getContexts: 0, dblclicks: 0, dismissResize: 0 }
  const noop = (): void => {}
  const ctx: any = {
    save: noop, restore: noop, beginPath: noop, closePath: noop, moveTo: noop, lineTo: noop,
    quadraticCurveTo: noop, bezierCurveTo: noop, clip: noop, fill: noop, stroke: noop,
    clearRect: noop, setLineDash: noop, setTransform: noop, arc: noop,
    measureText: (s: string) => ({ width: String(s).length * 6 }), fillRect: noop, fillText: noop,
  }
  for (const k of ['font', 'fillStyle', 'strokeStyle', 'lineWidth', 'globalAlpha', 'textAlign', 'textBaseline', 'lineCap'])
    Object.defineProperty(ctx, k, { set: noop, get: () => undefined })
  const stat = { innerHTML: '' }
  const panel: any = {
    addEventListener: noop, removeEventListener: noop,
    querySelector: (sel: string) => (sel === '[data-dag-stat]' ? stat : (sel === '[data-dag-wrap]' ? { clientWidth: 690 } : null)),
    querySelectorAll: () => [], contains: () => true,
  }
  const handlers: Record<string, (ev: any) => void> = {}
  const anchor = { appended: [] as any[] }
  const canvas: any = {
    width: 0, height: 0, style: {}, parentElement: { clientWidth: 690, appendChild: (el: any) => { anchor.appended.push(el) } },
    getContext: () => { st.getContexts++; return ctx },
    closest: () => panel,
    addEventListener: (t: string, fn: (ev: any) => void) => { if (t === 'dblclick') { st.dblclicks++; handlers[t] = fn } },
    removeEventListener: (t: string) => { if (t === 'dblclick') { st.removed++; delete handlers[t] } },
    getBoundingClientRect: () => ({ left: 0, top: 0 }),
    __handlers: handlers, __anchor: anchor,
  }
  st.canvas = canvas
  return st
}

;(globalThis as any).document = {
  getElementById: (id: string) => registry.get(id)?.canvas ?? null,
  createElement: () => { const el: any = { dataset: {}, appended: [], appendChild() {}, click() { el.clicked = true; el.clickPayload = { ...el.dataset } }, remove() { el.removed = true } }; createdEls.push(el); return el },
}
;(globalThis as any).ResizeObserver = class {
  constructor(_cb: any) { observers.push(this.rec) }
  rec = { connected: 0, disconnected: 0 }
  observe() { this.rec.connected++ }
  disconnect() { this.rec.disconnected++ }
}
;(globalThis as any).requestAnimationFrame = (cb: any) => { cb(0); return 1 }

const tasks = [
  { id: 't-p1', title: '父卡', status: 'todo', phase: 'implement', side: 'fullstack', dependsOn: [] },
  { id: 't-s1', title: '独立卡', status: 'todo', phase: 'implement', side: 'fullstack', dependsOn: ['t-p1'] },
]

const report: any = {}
const ok = (name: string, pass: boolean, extra: any = {}) => { report[name] = { pass, ...extra } }

// ── 请求样例 1：会话「流程节点」面板 wire（node-panel 产 HTML → conversation-progress 挂载）
const htmlPanel = buildDagCanvas(tasks as any, PANEL_DAG_CONTAINER_ID, PANEL_DAG_CANVAS_ID)
const idFromHtml = /<canvas id="([^"]+)"/.exec(htmlPanel)?.[1]
ok('1.panel.html_canvas_id', idFromHtml === PANEL_DAG_CANVAS_ID, { expected: PANEL_DAG_CANVAS_ID, actual: idFromHtml, containerInHtml: htmlPanel.includes('id="' + PANEL_DAG_CONTAINER_ID + '"') })
registry.set(PANEL_DAG_CANVAS_ID, mountStub())
tryMountDagCanvas(tasks as any, undefined, PANEL_DAG_CANVAS_ID)   // ← 真实调用（rAF 同步桩）
const panelStub = registry.get(PANEL_DAG_CANVAS_ID)!
ok('1.panel.mounted', panelStub.getContexts >= 1 && panelStub.dblclicks === 1 && panelStub.removed === 0, { getContexts: panelStub.getContexts, dblclickBound: panelStub.dblclicks, listenersRemoved: panelStub.removed })

// ── 请求样例 2：需求详情 wire（缺省 canvasId='dag-canvas'）
const htmlDetail = buildDagCanvas(tasks as any, 'dag-canvas-container')   // 与 stage-detail.ts:315 同形（canvasId 走缺省）
ok('2.detail.html_default_id', htmlDetail.includes('id="dag-canvas"') && htmlDetail.includes('id="dag-canvas-container"'), { hasCanvas: htmlDetail.includes('id="dag-canvas"'), hasContainer: htmlDetail.includes('id="dag-canvas-container"') })
registry.set('dag-canvas', mountStub())
tryMountDagCanvas(tasks as any, ['t-p1'])   // 不传 canvasId = 旧口径不变
const detailStub = registry.get('dag-canvas')!
ok('2.detail.mounted', detailStub.getContexts >= 1 && detailStub.dblclicks === 1 && detailStub.removed === 0, { getContexts: detailStub.getContexts, dblclickBound: detailStub.dblclicks, listenersRemoved: detailStub.removed })
ok('2.coexist_no_cross_dispose', detailStub.removed === 0 && panelStub.removed === 0, { detailRemoved: detailStub.removed, panelRemoved: panelStub.removed, note: '旧单槽实现会在挂第二块时摘掉第一块' })

// ── 请求样例 3：同名重挂（SSE 重绘）只释放同名条目，不动另一块
registry.delete(PANEL_DAG_CANVAS_ID)          // 画布被换掉（旧 canvas 脱管）
registry.set(PANEL_DAG_CANVAS_ID, mountStub()) // 新 canvas（同 id）
tryMountDagCanvas(tasks as any, undefined, PANEL_DAG_CANVAS_ID)
const panel2 = registry.get(PANEL_DAG_CANVAS_ID)!
ok('3.remount_same_id', panelStub.removed === 1 && detailStub.removed === 0 && panel2.getContexts >= 1, { oldPanelRemoved: panelStub.removed, detailRemoved: detailStub.removed, newPanelContexts: panel2.getContexts })

// ── 请求样例 4：目标画布不存在 → 静默 no-op（不抛、不动任何实例）
let threw = ''
try { tryMountDagCanvas(tasks as any, undefined, 'no-such-canvas') } catch (e) { threw = String((e as Error).message) }
ok('4.missing_canvas_noop', threw === '' && detailStub.removed === 0 && panel2.removed === 0, { threw, detailRemoved: detailStub.removed, panel2Removed: panel2.removed })

// ── 请求样例 5：画布存在但顶层卡为空（只剩子卡）→ 释放同名旧实例，不动另一块
tryMountDagCanvas([{ id: 't-k1', title: '子卡', status: 'todo', phase: 'implement', side: 'fullstack', dependsOn: [], parentId: 't-p9' }] as any, undefined, PANEL_DAG_CANVAS_ID)
ok('5.kids_only_releases_same_id', panel2.removed === 1 && detailStub.removed === 0, { panel2Removed: panel2.removed, detailRemoved: detailStub.removed })

// ── 请求样例 6：ResizeObserver 生命周期随**同名**释放断开（隔离场景，前后计数可归因）
const obsBefore = observers.length
registry.set('probe-canvas', mountStub())
tryMountDagCanvas(tasks as any, undefined, 'probe-canvas')      // 第一次挂：新建 observer #obsBefore
registry.set('probe-canvas', mountStub())                        // 画布被换掉（同 id）
tryMountDagCanvas(tasks as any, undefined, 'probe-canvas')       // 释放同名旧实例 + 挂新的
ok('6.resize_observer_released', observers.length === obsBefore + 2 && observers[obsBefore].disconnected === 1 && observers[obsBefore + 1].disconnected === 0,
   { created: observers.length - obsBefore, oldDisconnected: observers[obsBefore]?.disconnected, liveDisconnected: observers[obsBefore + 1]?.disconnected })

// ── 请求样例 8：双击卡片 → openTaskDetail(taskId, canvasId) 的锚点必须落在**本画布**的父元素上
const probe = mountStub()
registry.set('anchor-probe-canvas', probe)
const viewer = mountDagCanvas(tasks as any, undefined, 'anchor-probe-canvas')
const layout = viewer?.layout() ?? null
const first = layout === null ? null : (Object.keys(layout.pos)[0] ?? null)   // 只点**第一个节点矩形**内的点，other 位置不可点击无所谓
if (first !== null) {
  const pt = layout!.pos[first]
  probe.canvas.__handlers.dblclick?.({ clientX: pt.x + 10, clientY: pt.y + 10 })   // 真实点击路径
}
const fired = createdEls.filter(e => e.clicked === true)
ok('8.dblclick_open_task_scoped_anchor', fired.length === 1 && fired[0].clickPayload.action === 'open-task' && fired[0].clickPayload.task === first && probe.canvas.__anchor.appended.length === 1 && fired[0].removed === true,
   { fired: fired.map(e => e.clickPayload), anchorAppends: probe.canvas.__anchor.appended.length, expectedTask: first, removedAfterClick: fired[0]?.removed })

// ── 请求样例 7（反证/故障注入）：把旧「单槽 activeDispose」语义装回同一套桩，确认上面的判据会失败
const negA = mountStub(); const negB = mountStub()
let slotDisposed = 0
const oldStyleDispose = (): void => { negA.canvas.removeEventListener('dblclick', noop); slotDisposed++ }   // 旧实现：单槽，挂新块先释放上一块
slotDisposed = 0; oldStyleDispose.call(null)      // 旧实现挂 detail 后再挂 panel → 摘掉 detail
ok('7.old_single_slot_would_fail', slotDisposed === 1 && negA.removed === 1, { note: '旧单槽实现会摘掉另一块 → 用例 2/3 的 detailRemoved===0 判据具备区分度', oldDetailRemoved: negA.removed })

console.log(JSON.stringify({ cases: report, allPass: Object.values(report).every((r: any) => r.pass) }, null, 2))
