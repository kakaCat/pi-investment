/**
 * 真 DAG 数据桥单测（REQ-260928001915-f978 · FR-1 / FR-3 / FR-7）· serves: FR-3, FR-4
 *
 * 覆盖 `buildDagData` 桥：卡片层折叠（只画顶层卡）、依赖重路由、最长层号、
 * 父卡 kids 的全量池、ready 的两种来源（队列 / 前端推导 + 子卡上提父卡）。
 *
 * 为什么不在本文件断言像素：画布绘制与交互本身就是 `client/dag/*`（与
 * docs/requirements/REQ-260928001915-f978/demo 同一套模块；看板侧只多了
 * 卡片层折叠与传递归约两处桥接），那些模块自带 selftest 与单测；
 * 这里只钉「TaskRecord → DagData」这段看板特有逻辑。
 */
import { describe, it, expect, vi } from 'vitest'
import { buildDagData, buildDagCanvas, reduceEdges, mountDagCanvas, PANEL_DAG_CONTAINER_ID, PANEL_DAG_CANVAS_ID } from '../src/client/views/dag-view.js'
import { resolveTasks, createDagViewer, type DagData, type DagState } from '../src/client/dag/integration.js'
import { edgeTiers, renderEdges } from '../src/client/dag/edge-renderer.js'
import type { LayoutResult } from '../src/client/dag/dag-layout.js'
import { Role } from '../src/client/dag/card-types.js'
import type { TaskRecord } from '../src/client/types.ts'

let seq = 0
function task(over: Partial<TaskRecord> = {}): TaskRecord {
  return {
    id: 't-' + String(++seq).padStart(6, '0'),
    requirementId: 'REQ-000001', title: '任务', description: '',
    phase: 'implement', side: 'fullstack', dependsOn: [],
    scope: { apis: [], tables: [], files: [] },
    acceptance: '', context: '',
    status: 'todo', blocked: false, executions: [], comments: [], version: 1,
    createdAt: 1700000000000, updatedAt: 1700000000000,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...over,
  }
}

describe('buildDagData：卡片层折叠', () => {
  it('只画顶层卡；子卡进池子供父卡派生链（FR-7）', () => {
    const parent = task({ id: 't-p1', title: '父卡' })
    const dev = task({ id: 't-k1', parentId: 't-p1', stageKind: 'dev', status: 'done', title: '研发' })
    const tst = task({ id: 't-k2', parentId: 't-p1', stageKind: 'test', status: 'in_progress', title: '测试' })
    const solo = task({ id: 't-s1', title: '独立卡' })
    const data = buildDagData([parent, dev, tst, solo])

    expect(data.cards.map(c => c.id)).toEqual(['t-p1', 't-s1'])
    expect(data.pool.map(c => c.id)).toEqual(['t-p1', 't-k1', 't-k2', 't-s1'])

    // 卡底进度条靠 resolveTasks 按**全量池**派生（父卡左侧蓝条已按 2026-09-29 裁定 D 删除）
    const resolved = resolveTasks(data.cards, data.pool)
    const p = resolved.find(c => c.id === 't-p1')!
    expect(p.role).toBe(Role.PARENT)
    expect((p.kids ?? []).map(k => k.id)).toEqual(['t-k1', 't-k2']) // dev → test 固定序
    expect(resolved.find(c => c.id === 't-s1')!.role).toBe(Role.SOLO)

    // 反证：只给顶层卡（不传 pool）时父卡退化成 solo —— 这正是 DagData.pool 存在的理由
    expect(resolveTasks(data.cards).find(c => c.id === 't-p1')!.role).toBe(Role.SOLO)
  })

  it('依赖重路由：指向子卡的依赖上提父卡，子卡跨卡依赖也上提；不残留指向子卡的边', () => {
    const p1 = task({ id: 't-p1' })
    const p2 = task({ id: 't-p2', dependsOn: ['t-k1'] })
    const p3 = task({ id: 't-p3' })
    const k1 = task({ id: 't-k1', parentId: 't-p1', stageKind: 'dev', dependsOn: ['t-p3'] })
    const data = buildDagData([p1, p2, p3, k1])

    expect(data.edges).toHaveLength(2)
    expect(data.edges).toEqual(expect.arrayContaining([
      { from: 't-p1', to: 't-p2' }, // 指向子卡 t-k1 的依赖 → 上提到父卡 t-p1
      { from: 't-p3', to: 't-p1' }, // 子卡的跨卡依赖 → 上提到父卡 t-p1
    ]))
    expect(data.edges.some(e => e.from === 't-k1' || e.to === 't-k1')).toBe(false)
  })

  it('层号 = 最长依赖链深度（与旧 buildDag 的 L0/L1/L2 口径一致）', () => {
    const a = task({ id: 't-a' })
    const b = task({ id: 't-b', dependsOn: ['t-a'] })
    const c = task({ id: 't-c', dependsOn: ['t-b'] })
    const d = task({ id: 't-d', dependsOn: ['t-a'] })
    const data = buildDagData([a, b, c, d])
    const layer = (id: string): number | undefined => data.cards.find(x => x.id === id)?.layer
    expect(layer('t-a')).toBe(0)
    expect(layer('t-b')).toBe(1)
    expect(layer('t-c')).toBe(2)
    expect(layer('t-d')).toBe(1)
  })
})

describe('buildDagData：ready 的两种来源', () => {
  it('队列 ready[]：子卡 id 上提到父卡，悬空 id 丢弃', () => {
    const parent = task({ id: 't-p1' })
    const kid = task({ id: 't-k1', parentId: 't-p1', stageKind: 'dev' })
    const other = task({ id: 't-s1' })
    const data = buildDagData([parent, kid, other], ['t-k1', 't-not-exist'])
    expect(data.readySource).toBe('queue')
    expect(data.ready).toEqual(['t-p1'])
  })

  it('不传 ready → 前端推导（todo 且依赖全 done），并如实标注 derived', () => {
    const a = task({ id: 't-a', status: 'done' })
    const b = task({ id: 't-b', dependsOn: ['t-a'], status: 'todo' })
    const c = task({ id: 't-c', dependsOn: ['t-b'], status: 'todo' })
    const data = buildDagData([a, b, c])
    expect(data.readySource).toBe('derived')
    expect(data.ready).toEqual(['t-b'])
  })
})

describe('reduceEdges：传递归约（只画直接前置边）', () => {
  it('删掉绕行边，保留直连边（A→B→C 且 A→C）', () => {
    const edges = [
      { from: 't-a', to: 't-b' },
      { from: 't-b', to: 't-c' },
      { from: 't-a', to: 't-c' },
    ]
    expect(reduceEdges(['t-a', 't-b', 't-c'], edges)).toEqual([
      { from: 't-a', to: 't-b' },
      { from: 't-b', to: 't-c' },
    ])
  })

  it('并行分支不被误删（A→B、A→C、B→D、C→D 全部必要）', () => {
    const edges = [
      { from: 't-a', to: 't-b' },
      { from: 't-a', to: 't-c' },
      { from: 't-b', to: 't-d' },
      { from: 't-c', to: 't-d' },
    ]
    expect(reduceEdges(['t-a', 't-b', 't-c', 't-d'], edges)).toHaveLength(4)
  })

  it('只动画线：buildDagData 的 edges 归约，卡上 dependsOn / 层号仍是全量闭包', () => {
    const a = task({ id: 't-a' })
    const b = task({ id: 't-b', dependsOn: ['t-a'] })
    const c = task({ id: 't-c', dependsOn: ['t-a', 't-b'] }) // t-a 是绕行前置（经 t-b 可达）
    const data = buildDagData([a, b, c])
    expect(data.edgesRaw).toBe(3)
    expect(data.edges).toEqual([
      { from: 't-a', to: 't-b' },
      { from: 't-b', to: 't-c' },
    ])
    // 层号（最长链）不受归约影响；dependsOn 保持全量，供关键路径/上下游高亮使用
    expect(data.cards.find(x => x.id === 't-c')?.layer).toBe(2)
    expect(data.cards.find(x => x.id === 't-c')?.dependsOn).toEqual(['t-a', 't-b'])
  })
})

describe('buildDagCanvas：面板骨架', () => {
  it('空任务 → 空态占位', () => {
    expect(buildDagCanvas([])).toContain('暂无任务')
  })

  it('含画布 / 工具条位（2026-09-29 裁定 B 后不再有标题行与统计条）', () => {
    const html = buildDagCanvas([task({ id: 't-a' })])
    expect(html).toContain('dsh-pm-dag-panel')
    expect(html).toContain('id="dag-canvas"')
    expect(html).toContain('data-dag-dir="vertical"')
    expect(html).toContain('data-dag-dir="horizontal"')
    expect(html).toContain('data-dag-toggle="crit"')
    expect(html).toContain('data-dag-toggle="focus"')
    expect(html).toContain('data-dag-wrap')
  })

  it('面板不再有标题行与统计条（2026-09-29 用户裁定 B：两处从简）', () => {
    const html = buildDagCanvas([task({ id: 't-a' })])
    expect(html).not.toContain('dsh-pm-dag-title')
    expect(html).not.toContain('父卡依赖关系')
    expect(html).not.toContain('dsh-pm-dag-flowstat')
    expect(html).not.toContain('data-dag-stat')
  })
})

// REQ-260928001915-f978 · 2026-09-29 用户裁定 A：「dag 只渲染父卡片 不用管子卡片」
describe('DAG 只渲染父卡本身（showKidChains=false）', () => {
  const PARENT = {
    id: 't-p1', title: '父卡', phase: 'implement', side: 'fullstack', status: 'in_progress',
    role: Role.PARENT, dependsOn: [], layer: 0,
  }
  const KID = {
    id: 't-k1', title: '研发', phase: 'implement', side: 'fullstack', status: 'done',
    role: Role.CHILD, dependsOn: [], layer: 0, parentId: 't-p1', stageKind: 'dev',
  }
  const state: DagState = { dir: 'vertical', crit: false, focus: false, pinned: null }
  const data = (showKidChains: boolean): DagData => ({
    tasks: [PARENT],
    edges: [],
    ready: [],
    pool: [PARENT, KID],
    showKidChains,
  } as unknown as DagData)

  it('true（demo 行为）：父卡卡底画出子卡链进度（色块 + n/N）', () => {
    const c = fakeCanvas()
    createDagViewer(c.canvas as unknown as HTMLCanvasElement, data(true), state)
    expect(c.texts.join('|')).toContain('1/1')
    expect(c.stats.fillRects).toBe(1) // 只有进度段 1 块（父卡左侧蓝条已按裁定 D 删除）
  })

  it('false（看板）：卡底不再画子卡链，且父卡左侧蓝条已删（外观与泳道卡片一致）', () => {
    const c = fakeCanvas()
    createDagViewer(c.canvas as unknown as HTMLCanvasElement, data(false), state)
    expect(c.texts.join('|')).not.toContain('1/1') // 进度文案消失
    expect(c.stats.fillRects).toBe(0) // 无进度段、无蓝条
    expect(c.texts.join('|')).toContain('t-p1') // 父卡本身照画
  })
})

// 2026-09-29 用户：「可以简化现在dag的箭头吗太多了」——箭头降噪的行为钉（不是样式钉）
describe('箭头降噪：每张卡只留一条主干入边画箭头（edgeTiers）', () => {
  const L = (pos: Record<string, { x: number; y: number }>): LayoutResult =>
    ({ pos, bands: [], width: 900, height: 600, dir: 'vertical' }) as unknown as LayoutResult
  /** L0 = a b c（并列）· L1 = d · L2 = e（隔层） */
  const G = L({
    a: { x: 0, y: 0 }, b: { x: 300, y: 0 }, c: { x: 600, y: 0 },
    d: { x: 0, y: 200 }, e: { x: 0, y: 400 },
  })

  it('同一张卡的三条并列入边 → 只 1 条主干（A），其余 2 条降级为 B', () => {
    const edges = [{ from: 'a', to: 'd' }, { from: 'b', to: 'd' }, { from: 'c', to: 'd' }]
    const tiers = edgeTiers(edges, G)
    expect(tiers.filter(t => t === 'A')).toHaveLength(1)
    expect(tiers.filter(t => t === 'B')).toHaveLength(2)
  })

  it('隔层入边归 C（虚线）、相邻层冗余归 B，唯一入边恒为主干', () => {
    const edges = [
      { from: 'a', to: 'd' }, { from: 'b', to: 'd' }, { from: 'c', to: 'd' },
      { from: 'a', to: 'e' }, { from: 'd', to: 'e' },
    ]
    const tiers = edgeTiers(edges, G)
    expect(tiers[0]).toBe('B')  // 同层并列里的冗余边
    expect(tiers[3]).toBe('C')  // a(L0) → e(L2)：跨层绕行
    expect(tiers[4]).toBe('A')  // d(L1) → e(L2)：e 的最近前置
  })

  it('关键路径边恒为主干，哪怕它是并列冗余入边', () => {
    const edges = [{ from: 'a', to: 'd' }, { from: 'b', to: 'd' }]
    expect(edgeTiers(edges, G, new Set(['a', 'b', 'd']))).toEqual(['A', 'A'])
  })

  it('箭头总数 = 有入边的卡数（每卡最多一个箭头）', () => {
    const edges = [
      { from: 'a', to: 'd' }, { from: 'b', to: 'd' }, { from: 'c', to: 'd' },
      { from: 'a', to: 'e' }, { from: 'b', to: 'e' },
    ]
    const tiers = edgeTiers(edges, G)
    const arrows = edges.filter((_e, i) => tiers[i] === 'A')
    expect(arrows).toHaveLength(2)
    expect(new Set(arrows.map(e => e.to)).size).toBe(arrows.length)
  })
})

describe('箭头降噪：Canvas 后端真的少画了箭头', () => {
  const two = { pos: { a: { x: 0, y: 0 }, b: { x: 300, y: 0 }, c: { x: 0, y: 200 } }, bands: [], width: 900, height: 600, dir: 'vertical' } as unknown as LayoutResult
  const chain = { pos: { a: { x: 0, y: 0 }, b: { x: 0, y: 200 }, c: { x: 0, y: 400 } }, bands: [], width: 900, height: 600, dir: 'vertical' } as unknown as LayoutResult

  it('两条并列入边 → 2 次线 + 1 次箭头，且不带短划', () => {
    const c = countCtx()
    const n = renderEdges(c.ctx as unknown as CanvasRenderingContext2D,
      [{ from: 'a', to: 'c' }, { from: 'b', to: 'c' }], two, [], { critSet: new Set<string>() })
    expect(n).toBe(2)
    expect(c.st.strokes).toBe(3)
    expect(c.st.dashes).toBe(0)
  })

  it('跨层绕行边改虚线（tier C 才 setLineDash）', () => {
    const c = countCtx()
    renderEdges(c.ctx as unknown as CanvasRenderingContext2D,
      [{ from: 'b', to: 'c' }, { from: 'a', to: 'c' }], chain, [], { critSet: new Set<string>() })
    expect(c.st.strokes).toBe(3)  // 2 条线 + 1 个箭头（只有主干 b→c 带箭头）
    expect(c.st.dashes).toBe(1)   // a→c 跨层 → 虚线
  })
})

describe('buildDagCanvas：画布 id 参数化（REQ-260929010300-dbf9 FR-3）', () => {
  it('缺省 = 需求详情口径（container=dag-canvas-container · canvas=dag-canvas）', () => {
    const html = buildDagCanvas([task({ id: 't-a' })])
    expect(html).toContain('id="dag-canvas-container"')
    expect(html).toContain('id="dag-canvas"')
  })

  it('显式传入面板常量 → 独立 id，且不再出现需求详情的缺省 id', () => {
    const html = buildDagCanvas([task({ id: 't-a' })], PANEL_DAG_CONTAINER_ID, PANEL_DAG_CANVAS_ID)
    expect(html).toContain('id="np-dag-canvas-container"')
    expect(html).toContain('id="np-dag-canvas"')
    expect(html).not.toContain('id="dag-canvas"')
  })
})

describe('mountDagCanvas：实例表按 canvasId 隔离（FR-3 / FR-4）', () => {
  it('两处各挂一次：挂第二块不动第一块；同 id 二次挂载先释放旧实例（幂等）', () => {
    withFakeDom((dom) => {
      const a = dom.add('dag-canvas')
      const b = dom.add('canvas-2')
      const tasks = [task({ id: 't-a' })]

      expect(mountDagCanvas(tasks, undefined, 'dag-canvas')).toBeDefined()
      expect(mountDagCanvas(tasks, undefined, 'canvas-2')).toBeDefined()
      // 挂 canvas-2 不得摘掉 canvas-1 的监听（旧单槽实现会 dispose 掉上一块）
      expect(a.removed).toBe(0)
      expect(b.removed).toBe(0)

      // 同 id 二次挂载：先释放同名旧实例（监听被摘），仍不动 canvas-1（不产生两块画布）
      expect(mountDagCanvas(tasks, undefined, 'canvas-2')).toBeDefined()
      expect(b.removed).toBeGreaterThan(0)
      expect(a.removed).toBe(0)
    })
  })

  it('目标画布不存在 → 返回 undefined（不抛）', () => {
    withFakeDom((dom) => {
      dom.add('dag-canvas')
      expect(mountDagCanvas([task({ id: 't-a' })], undefined, 'not-there')).toBeUndefined()
    })
  })

  // 释放必须**早于**提前返回：canvasId 的旧条目不能因为「这次没画布可挂」而留在表里——
  // 它的 ResizeObserver / dblclick 监听会挂在一个已脱离 DOM 的 canvas 上（数据模型不变量
  // 「每个 canvasId 至多一条、重复挂载先释放旧条目」）。
  it('画布被 SSE 重绘摘掉后重复挂载：先释放同名旧实例，另一实例不受影响', () => {
    withFakeDom((dom) => {
      const a = dom.add('dag-canvas')
      const b = dom.add('canvas-2')
      const tasks = [task({ id: 't-a' })]
      expect(mountDagCanvas(tasks, undefined, 'dag-canvas')).toBeDefined()
      expect(mountDagCanvas(tasks, undefined, 'canvas-2')).toBeDefined()

      dom.remove('canvas-2')                       // 整块面板被换掉：canvas-2 不在 DOM 里了
      expect(mountDagCanvas(tasks, undefined, 'canvas-2')).toBeUndefined()
      expect(b.removed).toBeGreaterThan(0)         // 旧实例已回收（不因提前返回而泄漏）
      expect(a.removed).toBe(0)                    // 需求详情那块仍在 DOM，监听未被摘
    })
  })

  it('顶层卡为空（只剩子卡）也先释放同名旧实例，且不动其它画布', () => {
    withFakeDom((dom) => {
      const a = dom.add('dag-canvas')
      const b = dom.add('canvas-2')
      const tasks = [task({ id: 't-a' })]
      expect(mountDagCanvas(tasks, undefined, 'dag-canvas')).toBeDefined()
      expect(mountDagCanvas(tasks, undefined, 'canvas-2')).toBeDefined()

      const kidsOnly = [task({ id: 't-k1', parentId: 't-p1', stageKind: 'dev' })]
      expect(mountDagCanvas(kidsOnly, undefined, 'dag-canvas')).toBeUndefined()
      expect(a.removed).toBeGreaterThan(0)
      expect(b.removed).toBe(0)
    })
  })
})

// 2026-09-29 用户裁定 F：「点击卡片应该打开对应文档这个 dag 功能丢失了」——旧分层列表的节点是
// data-action="open-doc"，换成 Canvas 后 CardData 没带 cardDoc、单击又被"钉住"占用 → 本组用例钉住新口径。
describe('卡片点击：单击开任务卡文档 / 双击开任务详情（裁定 F）', () => {
  const DOC = 'docs/requirements/REQ-000001/tasks/t-a.md'
  it('buildDagData：cardDoc 透传到卡片（单击开文档靠它）', () => {
    const d = buildDagData([task({ id: 't-a', cardDoc: DOC })])
    expect(d.cards[0]?.cardDoc).toBe(DOC)
  })

  it('单击带 cardDoc 的卡片 → 延迟一拍后派发 data-action="open-doc" + data-path', () => {
    vi.useFakeTimers()
    try {
      withFakeDom((dom) => {
        const s = dom.add('dag-canvas')
        expect(mountDagCanvas([task({ id: 't-a', cardDoc: DOC })], undefined, 'dag-canvas')).toBeDefined()
        s.fire('click', { clientX: 60, clientY: 20 })
        expect(dom.created.some((e) => e.dataset.action === 'open-doc')).toBe(false) // 单击延迟一拍
        vi.advanceTimersByTime(300)
        const el = dom.created.find((e) => e.dataset.action === 'open-doc')
        expect(el?.dataset.path).toBe(DOC)
        expect(el?.clicked).toBe(true)
      })
    } finally { vi.useRealTimers() }
  })

  it('双击 → 取消待触发的单击，只派发 open-task（不会先开两次文档）', () => {
    vi.useFakeTimers()
    try {
      withFakeDom((dom) => {
        const s = dom.add('dag-canvas')
        expect(mountDagCanvas([task({ id: 't-a', cardDoc: DOC })], undefined, 'dag-canvas')).toBeDefined()
        s.fire('click', { clientX: 60, clientY: 20 })
        s.fire('dblclick', { clientX: 60, clientY: 20 })
        vi.advanceTimersByTime(300)
        expect(dom.created.some((e) => e.dataset.action === 'open-doc')).toBe(false)
        expect(dom.created.some((e) => e.dataset.action === 'open-task')).toBe(true)
      })
    } finally { vi.useRealTimers() }
  })

  it('卡片没有 cardDoc → 单击不派发任何导航（不编造文档路径）', () => {
    vi.useFakeTimers()
    try {
      withFakeDom((dom) => {
        const s = dom.add('dag-canvas')
        expect(mountDagCanvas([task({ id: 't-a' })], undefined, 'dag-canvas')).toBeDefined()
        s.fire('click', { clientX: 60, clientY: 20 })
        vi.advanceTimersByTime(300)
        expect(dom.created).toEqual([])
      })
    } finally { vi.useRealTimers() }
  })
})

/** 极简全局 document + 画布桩（Node 环境没有 DOM）：给挂载路径用。 */
interface CreatedEl { dataset: Record<string, string>; clicked: boolean; removed: boolean }
interface FakeDom { add: (id: string) => MountStub; remove: (id: string) => void; created: CreatedEl[] }

function withFakeDom(fn: (dom: FakeDom) => void): void {
  const g = globalThis as unknown as { document?: unknown }
  const prev = g.document
  const registry = new Map<string, MountStub>()
  const created: CreatedEl[] = []
  g.document = {
    getElementById: (id: string) => registry.get(id)?.canvas ?? null,
    // 记录派发出去的元素（open-doc / open-task 事件委托的载体），供"点卡片开文档"断言
    createElement: () => {
      const el = { dataset: {} as Record<string, string>, clicked: false, removed: false, appendChild: () => {}, click: () => { el.clicked = true }, remove: () => { el.removed = true } }
      created.push(el)
      return el
    },
  }
  try {
    fn({
      add: (id: string) => { const s = mountStub(); registry.set(id, s); return s },
      remove: (id: string) => { registry.delete(id) },
      created,
    })
  } finally {
    if (prev === undefined) delete g.document
    else g.document = prev
  }
}

interface MountStub {
  canvas: Record<string, unknown>
  removed: number
  /** 触发 canvas 上注册的监听（模拟浏览器点击），用于"点卡片开文档"断言。 */
  fire: (type: string, ev: unknown) => void
}

/** 可挂载的画布桩：够 createDagViewer 跑通，并数「监听被摘次数」以观测是否被 dispose。 */
function mountStub(): MountStub {
  const noop = (): void => { /* 绘制动作不参与断言 */ }
  const ctx: Record<string, unknown> = {
    save: noop, restore: noop, beginPath: noop, closePath: noop, moveTo: noop, lineTo: noop,
    quadraticCurveTo: noop, bezierCurveTo: noop, clip: noop, fill: noop, stroke: noop,
    clearRect: noop, setLineDash: noop, setTransform: noop, arc: noop,
    measureText: (s: string) => ({ width: String(s).length * 6 }),
    fillRect: noop, fillText: noop,
  }
  for (const k of ['font', 'fillStyle', 'strokeStyle', 'lineWidth', 'globalAlpha', 'textAlign', 'textBaseline', 'lineCap']) {
    Object.defineProperty(ctx, k, { set: noop, get: () => undefined })
  }
  const panel: Record<string, unknown> = {
    addEventListener: noop, removeEventListener: noop,
    querySelector: () => null,
    querySelectorAll: () => [],
    contains: () => true,
  }
  const handlers: Record<string, (ev: unknown) => void> = {}
  const stub = {
    canvas: undefined as unknown as Record<string, unknown>,
    removed: 0,
    fire: (type: string, ev: unknown) => { handlers[type]?.(ev) },
  }
  const canvas: Record<string, unknown> = {
    width: 0, height: 0, style: {},
    parentElement: { clientWidth: 690, appendChild: () => {} },
    getContext: () => ctx,
    closest: () => panel,
    addEventListener: (type: string, fn: (ev: unknown) => void) => { handlers[type] = fn },
    removeEventListener: (type: string) => { delete handlers[type]; stub.removed += 1 },
    getBoundingClientRect: () => ({ left: 0, top: 0 }),
  }
  stub.canvas = canvas
  return stub
}
/** 只数笔画/短划的 ctx 替身（箭头 = 一次额外 stroke）。 */
function countCtx(): { ctx: Record<string, unknown>; st: { strokes: number; dashes: number } } {
  const st = { strokes: 0, dashes: 0 }
  const noop = (): void => { /* 不入断言 */ }
  const ctx: Record<string, unknown> = {
    save: noop, restore: noop, beginPath: noop, moveTo: noop, lineTo: noop,
    bezierCurveTo: noop, clip: noop, fill: noop,
    stroke: () => { st.strokes++ },
    setLineDash: (d?: number[]) => { if (d !== undefined && d.length > 0) st.dashes++ },
  }
  for (const k of ['strokeStyle', 'lineWidth', 'globalAlpha', 'lineCap', 'fillStyle']) {
    Object.defineProperty(ctx, k, { set: noop, get: () => undefined })
  }
  return { ctx, st }
}

/** 极简 canvas 替身：只记「画了什么文字 / 填了几个实心块」，让 canvas 渲染能在 Node 里断言。 */
function fakeCanvas(): { canvas: Record<string, unknown>; texts: string[]; stats: { fillRects: number } } {
  const texts: string[] = []
  const stats = { fillRects: 0 }
  const noop = (): void => { /* 绘制动作不参与断言 */ }
  const ctx: Record<string, unknown> = {
    save: noop, restore: noop, beginPath: noop, closePath: noop, moveTo: noop, lineTo: noop,
    quadraticCurveTo: noop, bezierCurveTo: noop, clip: noop, fill: noop, stroke: noop,
    clearRect: noop, setLineDash: noop, setTransform: noop, arc: noop,
    measureText: (s: string) => ({ width: String(s).length * 6 }),
    fillRect: () => { stats.fillRects++ },
    fillText: (s: string) => { texts.push(String(s)) },
  }
  for (const k of ['font', 'fillStyle', 'strokeStyle', 'lineWidth', 'globalAlpha', 'textAlign', 'textBaseline', 'lineCap']) {
    Object.defineProperty(ctx, k, { set: noop, get: () => undefined })
  }
  const canvas: Record<string, unknown> = {
    width: 0, height: 0, style: {},
    parentElement: { clientWidth: 690 },
    getContext: () => ctx,
    addEventListener: noop, removeEventListener: noop,
    getBoundingClientRect: () => ({ left: 0, top: 0 }),
  }
  return { canvas, texts, stats }
}
