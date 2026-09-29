/**
 * 需求详情 · 队列真 DAG（Canvas）—— demo 交互式视图的看板落地
 * （REQ-260928001915-f978 · FR-1…FR-7）
 *
 * 渲染与交互一行不重写，全部复用 `client/dag/*`（与
 * docs/requirements/REQ-260928001915-f978/demo/dag-card-types-demo.html 同一套模块）。
 * 看板侧另有两处**看板专有**的桥接逻辑（demo 不需要，也不改 demo 的渲染语义）：
 * 卡片层折叠（只画顶层卡）与**传递归约**（只画直接前置边）。本文件只做三件事：
 *
 *   ① 数据桥：TaskRecord[] ──collapseToCardLevel──► 顶层卡 + 重路由依赖
 *                          ├─► CardData（phase/side/status/layer/kids）+ ready
 *                          └─► edges（重路由 → 传递归约）
 *   ② 面板骨架：工具条（纵向·横向 · 关键路径 · 只看主线）/ 画布 / 图例
 *      （2026-09-29 用户裁定 B：标题行与统计条一并删除，需求详情与会话面板两处从简）
 *   ③ 挂载：createDagViewer（布局·卡片·边线·悬停·钉住）+ 工具条 → viewer.patch
 *
 * 为什么只画顶层卡：子卡链是卡的内部流水线，不是平级依赖节点（旧图把两者混画：
 * REQ-260924213231-b1c4 实测 65 节点里 52 个是子卡，末 3 层全是子卡）。子卡折进
 * 父卡卡底进度条（FR-7），依赖仍按 `collapseToCardLevel` 重路由到父卡。
 *
 * 为什么要传递归约（2026-09-29 实测全仓 52 份队列）：队列的 `dependsOn` 是**传递闭包**——
 * 拆分时每张卡列的是「所有前置」而不是「直接前置」，于是同一对卡之间既有直连边、又有绕行边。
 * 实测 637 条卡片层边里 15.1% 是绕行边，最难看的几份（REQ-260928222643-4d34 16 条/8 张卡、
 * REQ-260925172227-2d61 26 条/11 张卡）冗余 40%+，且绕行边**跨层最长**（L0→L3、L2→L5）——
 * 正是让 DAG 变成"面条图"的那批线。归约**只动画线**：`dependsOn`（layers / ready / 关键路径 /
 * 上下游高亮）仍是全量闭包，语义零变化。
 *
 * @module dsh-pmboard/client/views/dag-view
 */
import { esc } from '../html.js'
import { Role, type CardData } from '../dag/card-types.js'
import { collapseToCardLevel } from '../dag/progress-bar.js'
import type { Edge } from '../dag/edge-renderer.js'
import { hitTest, type LayoutDir } from '../dag/dag-layout.js'
import {
  createDagViewer,
  type DagData,
  type DagRenderResult,
  type DagState,
  type DagViewer,
} from '../dag/integration.js'

/** 缺省画布 id（需求详情使用）：构建面板 / 挂载 / 双击打开任务三处共用。 */
const DAG_CANVAS_ID = 'dag-canvas'

/**
 * 会话「流程节点」面板专用 id（REQ-260929010300-dbf9 FR-3）——**单一常量源**，
 * `node-panel.ts` 与 `conversation-progress.ts` 共用；同页可与需求详情的
 * `#dag-canvas` 各挂一块，互不抢占。
 */
export const PANEL_DAG_CONTAINER_ID = 'np-dag-canvas-container'
export const PANEL_DAG_CANVAS_ID = 'np-dag-canvas'

/**
 * DAG 绘制真正用到的任务字段（FR-3 入参收敛）。
 *
 * 需求详情给 `TaskRecord`、会话面板给 `StageTaskRef`——两者都是本结构类型的子集，
 * 绘制不再要求面板侧伪造完整 TaskRecord（缺省行为不变：两处都按同一套字段绘制）。
 */
export interface DagTaskLike {
  id: string
  title: string
  status: string
  phase: string
  side: string
  dependsOn: string[]
  parentId?: string
  stageKind?: string
  /** 自足任务卡文档（当前绘制不消费，保留字段以便两种入参互换） */
  cardDoc?: string
}

// ---------------------------------------------------------------------------
// ① 数据桥
// ---------------------------------------------------------------------------

export interface DagPanelData {
  /** 画布节点：顶层卡（子卡不单独成节点） */
  cards: CardData[]
  /** 角色派生用**全量**卡片（含子卡）——只给顶层卡时父卡会被判成 solo，蓝条与卡底进度条一起消失 */
  pool: CardData[]
  /** 画线用的依赖边：已重路由到顶层卡，并做**传递归约**（只留直接前置边） */
  edges: Edge[]
  /** 重路由后、去绕行前的边数——统计条用它说明"折叠掉了多少条绕行边" */
  edgesRaw: number
  /** 可开工的顶层卡 id */
  ready: string[]
  /** ready 的来源：queue=消费队列 ready[]；derived=前端按「依赖全完成」推导（诚实标注，R-013） */
  readySource: 'queue' | 'derived'
}

/**
 * 最长依赖链深度（无依赖 = 0）。
 *
 * layer 只喂布局（同层共线、跨层排序），**正确性由 dependsOn 决定**（findCriticalPath
 * 内部自己跑 Kahn，不读 layer，见 critical-path.ts 头注）。所以这里按折叠后的
 * deps 现算层号，不依赖队列落盘的 layer 是否可信。环按 0 降级（不递归爆栈；V-4 负责报）。
 */
function layerOf(ids: readonly string[], deps: Record<string, readonly string[]>): Map<string, number> {
  const memo = new Map<string, number>()
  const stack = new Set<string>()
  const depth = (id: string): number => {
    const hit = memo.get(id)
    if (hit !== undefined) return hit
    if (stack.has(id)) return 0
    stack.add(id)
    let d = 0
    for (const p of deps[id] ?? []) d = Math.max(d, depth(p) + 1)
    stack.delete(id)
    memo.set(id, d)
    return d
  }
  for (const id of ids) depth(id)
  return memo
}

/**
 * 传递归约（transitive reduction，纯函数）：删掉"绕行边"，只留直接前置边。
 *
 * 判据：边 u→v 若在**不使用这条边**时 v 仍从 u 可达，它就是绕行边（v 已由某条更长的路径
 * 约束），删掉它不改变任何一对节点的可达性，也不改变分层（最长路径只由最短的那条链条决定）。
 *
 * 复杂度 O(E·(V+E))——卡片层 E 是「需求卡片数」量级（实测最大 37），远小于子卡全量，可承受。
 * 输入假定无重边（buildDagData 已按 `from -> to` 去重）；有环时按"能到达即删"处理，不递归爆栈。
 */
export function reduceEdges(nodes: readonly string[], edges: readonly Edge[]): Edge[] {
  const succ = new Map<string, string[]>()
  for (const n of nodes) succ.set(n, [])
  for (const e of edges) {
    const list = succ.get(e.from)
    if (list !== undefined) list.push(e.to)
  }
  /** 绕开 from→to 这条边后，to 是否仍从 from 可达 */
  const stillReachable = (from: string, to: string): boolean => {
    const seen = new Set<string>([from])
    const stack: string[] = [from]
    while (stack.length > 0) {
      const cur = stack.pop() as string
      for (const next of succ.get(cur) ?? []) {
        if (cur === from && next === to) continue // 绕开这条边本身
        if (seen.has(next)) continue
        seen.add(next)
        stack.push(next)
      }
    }
    return seen.has(to)
  }
  return edges.filter(e => !stillReachable(e.from, e.to))
}

/**
 * TaskRecord[] → Canvas DAG 数据（纯函数、零 DOM，Node 里可直接单测）。
 *
 * @param tasks 需求全量任务（含子卡；由看板按 requirementId 过滤后传入）
 * @param ready 队列 `ready[]`（`BoardState.ready[reqId]`）；**不传**才走前端推导。
 *              传空数组 = 队列确实没有可开工卡（与「没拿到数据」必须区分开）。
 */
export function buildDagData(tasks: DagTaskLike[], ready?: readonly string[]): DagPanelData {
  const { tops, deps } = collapseToCardLevel(tasks)
  const layers = layerOf(tops.map(t => t.id), deps)
  const parentOf = new Map<string, string>()
  for (const t of tasks) {
    if (t.parentId !== undefined) parentOf.set(t.id, t.parentId)
  }

  const toCard = (t: DagTaskLike, isTop: boolean): CardData => {
    const card: CardData = {
      id: t.id,
      title: t.title,
      phase: t.phase as unknown as CardData['phase'],
      side: t.side as unknown as CardData['side'],
      status: t.status as unknown as CardData['status'],
      // role/kids 由 createDagViewer → resolveTasks 按 pool 反查重算，这里只给安全默认值
      role: Role.SOLO,
      dependsOn: isTop ? (deps[t.id] ?? []) : [],
      // 子卡只进 pool（不布局），层号无意义
      layer: isTop ? (layers.get(t.id) ?? 0) : 0,
    }
    if (t.parentId !== undefined) card.parentId = t.parentId
    if (t.stageKind !== undefined) card.stageKind = t.stageKind
    // 2026-09-29 裁定 F：带上 cardDoc，画布才能「单击卡片 → 打开任务卡文档」（旧分层列表的行为）
    if (t.cardDoc !== undefined && t.cardDoc.length > 0) card.cardDoc = t.cardDoc
    return card
  }

  const cards = tops.map(t => toCard(t, true))
  const pool = tasks.map(t => toCard(t, false))
  const topIds = new Set(cards.map(c => c.id))

  const edgesRaw: Edge[] = []
  const seenEdge = new Set<string>()
  for (const t of tops) {
    for (const dep of deps[t.id] ?? []) {
      const key = dep + ' -> ' + t.id
      if (seenEdge.has(key)) continue
      seenEdge.add(key)
      edgesRaw.push({ from: dep, to: t.id })
    }
  }
  // 画线前做传递归约（见文件头「为什么要传递归约」）
  const edges = reduceEdges(cards.map(c => c.id), edgesRaw)

  const fromQueue = ready !== undefined
  const readySet = new Set<string>()
  if (fromQueue) {
    // 队列 ready[] 可能点在子卡上（子卡也可开工）；画的是父卡，故上提到父卡再取交集
    for (const id of ready ?? []) {
      const top = parentOf.get(id) ?? id
      if (topIds.has(top)) readySet.add(top)
    }
  } else {
    const byId = new Map(cards.map(c => [c.id, c]))
    for (const t of tops) {
      if (t.status !== 'todo') continue
      if ((deps[t.id] ?? []).every(p => byId.get(p)?.status === 'done')) readySet.add(t.id)
    }
  }

  return {
    cards,
    pool,
    edges,
    edgesRaw: edgesRaw.length,
    ready: [...readySet],
    readySource: fromQueue ? 'queue' : 'derived',
  }
}

// ---------------------------------------------------------------------------
// ② 面板骨架（demo ⑤ 真 DAG 的看板版：工具条 / 统计 / 画布 / 图例）
// ---------------------------------------------------------------------------

/**
 * 构建面板 HTML（纯字符串）。画布尺寸由 createDagViewer 按容器宽度自适应，
 * 这里不写死宽高。
 */
export function buildDagCanvas(tasks: DagTaskLike[], containerId: string = 'dag-canvas-container', canvasId: string = DAG_CANVAS_ID): string {
  if (tasks.length === 0) return '<div class="dsh-pm-empty">暂无任务</div>'
  return '<div class="dsh-pm-dag-panel" id="' + esc(containerId) + '">' +
    '<div class="dsh-pm-dag-head">' +
      '<span class="dsh-pm-dag-sub">节点 = 顶层卡 · 连线 = 依赖边 · 箭头只标每卡一条入边（所有依赖边照画） · 悬停看上下游 · 单击打开任务卡文档 · 双击打开任务详情</span>' +
      '<span class="dsh-pm-dag-seg">' +
        '<button type="button" class="dsh-pm-dag-btn is-on" data-dag-dir="vertical">纵向</button>' +
        '<button type="button" class="dsh-pm-dag-btn" data-dag-dir="horizontal">横向</button>' +
      '</span>' +
      '<span class="dsh-pm-dag-seg">' +
        '<button type="button" class="dsh-pm-dag-btn" data-dag-toggle="crit">关键路径</button>' +
        '<button type="button" class="dsh-pm-dag-btn" data-dag-toggle="focus">只看主线</button>' +
      '</span>' +
    '</div>' +
    '<div class="dsh-pm-dag-canvas-wrap" data-dag-wrap>' +
      '<canvas id="' + esc(canvasId) + '" class="dsh-pm-dag-canvas"></canvas>' +
    '</div>' +
    '<div class="dsh-pm-dag-legend">' +
      '<span><i style="background:rgba(52,199,89,.5)"></i>已完成链路</span>' +
      '<span><i style="background:rgba(0,0,0,.17)"></i>入边箭头（每卡一条）</span>' +
      '<span><i style="background:rgba(0,0,0,.09)"></i>冗余前置（浅色无箭头）</span>' +
      '<span><i style="background:rgba(0,0,0,.09);height:1px"></i>跨层绕行（虚线）</span>' +
      '<span><i style="background:rgba(0,113,227,.75);height:2px"></i>关键路径</span>' +
      '<span>🟠 上游（它依赖谁）</span>' +
      '<span>🔵 下游（谁依赖它）</span>' +
      '<span>🟢 呼吸点 = 可开工</span>' +
    '</div>' +
  '</div>'
}

/** 统计条已按 2026-09-29 用户裁定 B 删除（连同标题行）——面板只留工具条 / 画布 / 图例。 */

// ---------------------------------------------------------------------------
// ③ 挂载
// ---------------------------------------------------------------------------

/**
 * 挂载实例表（FR-3 / FR-4）：canvasId → 释放函数。
 *
 * 看板 SSE 每次重绘都换掉整段 DOM，故必须先释放**同名**实例再挂新的（避免 observer 泄漏）；
 * 用 Map 而不是单槽：同一页可同时存在两块 DAG 画布（需求详情 #dag-canvas 与会话面板
 * #np-dag-canvas）——释放其一时不得动到另一块（FR-3 判据「两实例互不释放」）。
 */
const disposers = new Map<string, () => void>()

/** 释放指定画布 id 的实例；不存在即无操作，**不触碰其它画布**。 */
function disposeDagCanvas(canvasId: string): void {
  const fn = disposers.get(canvasId)
  if (fn === undefined) return
  disposers.delete(canvasId)
  fn()
}

/**
 * 打开任务详情：复用看板的 `data-action="open-task"` 事件委托（board-mount 唯一入口），
 * 不另开一条导航链路。
 */
function openTaskDetail(taskId: string, canvasId: string): void {
  const anchor = document.getElementById(canvasId)?.parentElement
  if (anchor === null || anchor === undefined) return
  const el = document.createElement('div')
  el.dataset.action = 'open-task'
  el.dataset.task = taskId
  anchor.appendChild(el)
  el.click()
  el.remove()
}

/**
 * 打开任务卡文档：复用既有 `data-action="open-doc"` 事件委托（会话面板走 conversation-progress，
 * 看板走 board-mount），不另开一条导航链路。与 `openTaskDetail` 同构。
 */
function openCardDoc(docPath: string, canvasId: string): void {
  const anchor = document.getElementById(canvasId)?.parentElement
  if (anchor === null || anchor === undefined) return
  const el = document.createElement('button')
  el.dataset.action = 'open-doc'
  el.dataset.path = docPath
  anchor.appendChild(el)
  el.click()
  el.remove()
}

/**
 * 挂载 Canvas DAG（在面板 HTML 进 DOM 之后调用）。
 *
 * @param tasks 需求全量任务（含子卡）
 * @param ready 队列 `ready[]`（只用于画布上的可开工绿点；不传 = 前端按「依赖全完成」推导）
 * @returns viewer（无画布或无顶层卡时 undefined）
 */
export function mountDagCanvas(tasks: DagTaskLike[], ready?: readonly string[], canvasId: string = DAG_CANVAS_ID): DagViewer | undefined {
  // 先释放同名旧条目（design/data-model.md 不变量：每个 canvasId 至多一条、「重复挂载先释放旧条目」）。
  // 必须放在**提前返回之前**：画布被 SSE 重绘摘掉、或顶层卡为空（如只剩子卡）时也要回收旧实例，
  // 否则它的 ResizeObserver 与 dblclick 监听会一直挂在一个已脱管的 canvas 上（即文件头说的 observer 泄漏）。
  disposeDagCanvas(canvasId)

  const canvas = document.getElementById(canvasId) as HTMLCanvasElement | null
  if (canvas === null) return undefined
  const data = buildDagData(tasks, ready)
  if (data.cards.length === 0) return undefined

  const panel = canvas.closest<HTMLElement>('.dsh-pm-dag-panel')
  const dagData: DagData = {
    tasks: data.cards,
    edges: data.edges,
    ready: data.ready,
    pool: data.pool,
    // 用户 2026-09-29 裁定 A：DAG 只渲染父卡本身 —— 卡底不再画子卡链进度；
    // 用户 2026-09-29 裁定 D：父卡左侧蓝条也已删除（卡片外观与泳道卡片一致）。
    showKidChains: false,
  }
  const initial: DagState = { dir: 'vertical', crit: false, focus: false, pinned: null }
  const viewer = createDagViewer(canvas, dagData, initial)

  // 2026-09-29 用户裁定 B：面板不再有标题行与统计条（一切从简），挂载侧不再回填统计位。
  const paint = (patch: Partial<DagState>): DagRenderResult => viewer.patch(patch)
  paint({})

  // 工具条：纵向/横向 + 关键路径 + 只看主线（与 demo 的 seg 同语义）
  const onClick = (ev: Event): void => {
    const target = ev.target as Element | null
    if (target === null || typeof target.closest !== 'function') return
    const btn = target.closest<HTMLButtonElement>('button.dsh-pm-dag-btn')
    if (btn === null || panel === null || !panel.contains(btn)) return
    const dir = btn.dataset.dagDir
    if (dir === 'vertical' || dir === 'horizontal') {
      const next: LayoutDir = dir
      paint({ dir: next })
      panel.querySelectorAll<HTMLButtonElement>('[data-dag-dir]').forEach(b => {
        b.classList.toggle('is-on', b === btn)
      })
      return
    }
    const toggle = btn.dataset.dagToggle
    if (toggle === 'crit') {
      const next = !viewer.state().crit
      paint({ crit: next })
      btn.classList.toggle('is-on', next)
    } else if (toggle === 'focus') {
      const next = !viewer.state().focus
      paint({ focus: next })
      btn.classList.toggle('is-on', next)
    }
  }
  if (panel !== null) panel.addEventListener('click', onClick)

  // 卡片单击 = 打开该卡**任务卡文档**（2026-09-29 裁定 F：恢复旧分层列表 data-action="open-doc" 的行为）；
  // 卡片双击 = 打开任务详情。单击延迟一拍、双击时取消——否则双击会先触发两次"开文档"。
  const docById = new Map<string, string | undefined>(data.cards.map(c => [c.id, c.cardDoc]))
  const hitCard = (ev: MouseEvent): string | null => {
    const layout = viewer.layout()
    if (layout === null) return null
    const rect = canvas.getBoundingClientRect()
    return hitTest(layout, ev.clientX - rect.left, ev.clientY - rect.top, 0)
  }
  let clickTimer: ReturnType<typeof setTimeout> | undefined
  const onCardClick = (ev: MouseEvent): void => {
    const id = hitCard(ev)
    if (id === null) return
    const doc = docById.get(id)
    if (doc === undefined || doc.length === 0) return
    if (clickTimer !== undefined) clearTimeout(clickTimer)
    clickTimer = setTimeout(() => {
      clickTimer = undefined
      openCardDoc(doc, canvasId)
    }, 220)
  }
  const onDblClick = (ev: MouseEvent): void => {
    if (clickTimer !== undefined) { clearTimeout(clickTimer); clickTimer = undefined }
    const id = hitCard(ev)
    if (id !== null) openTaskDetail(id, canvasId)
  }
  canvas.addEventListener('click', onCardClick)
  canvas.addEventListener('dblclick', onDblClick)

  // 画布自适应：面板从 display:none 切到可见（执行 Tab）、或容器宽度变化时按新宽度重排。
  // 只在**宽度真的变了**时重画，避免 canvas 尺寸变化反过来触发 observer 形成回路。
  const wrap = panel === null ? null : panel.querySelector<HTMLElement>('[data-dag-wrap]')
  let observer: ResizeObserver | undefined
  if (typeof ResizeObserver !== 'undefined' && wrap !== null) {
    let lastW = -1
    const onResize = (): void => {
      const w = wrap.clientWidth
      if (w === lastW) return
      lastW = w
      paint({})
    }
    observer = new ResizeObserver(onResize)
    observer.observe(wrap)
  }

  disposers.set(canvasId, (): void => {
    panel?.removeEventListener('click', onClick)
    if (clickTimer !== undefined) { clearTimeout(clickTimer); clickTimer = undefined }
    canvas.removeEventListener('click', onCardClick)
    canvas.removeEventListener('dblclick', onDblClick)
    if (observer !== undefined) observer.disconnect()
    viewer.destroy()
  })
  return viewer
}
