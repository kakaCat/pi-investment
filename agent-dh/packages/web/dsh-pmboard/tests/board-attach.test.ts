/**
 * attachBoard 生命周期单测（REQ-260928185112-e20d FR-2 / 任务卡 t-48d9a4）。
 *
 * 覆盖：attachBoard(container) 返回 disposer；dispose 后定时器计数归零（clearInterval 已清）、
 * 容器上的 click/change 监听已移除、SSE 订阅已关闭；isActive()=false 时轮询跳过刷新；
 * poll:false（旧 board-shell 路径）不自建定时器。
 *
 * 环境：vitest 默认 node（本包不含 jsdom）——只注入本用例需要的最小 document/window/EventSource
 * 桩，不做真实 DOM 断言；渲染结果（innerHTML）不是本用例的观测对象。
 *
 * serves: FR-2（REQ-260928222643-4d34：看板挂载时消费一次性定位意图，TC-7/TC-8）。
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { attachBoard } from '../src/client/board-mount.ts'
import { requestBoardFocus, clearBoardFocus, peekBoardFocus } from '../src/client/board-focus.ts'

const origFetch = globalThis.fetch

/** 最小容器：只记录监听器增删，不参与渲染。 */
function fakeContainer(): { el: HTMLElement; added: string[]; removed: string[] } {
  const added: string[] = []
  const removed: string[] = []
  const el = {
    innerHTML: '',
    addEventListener: (t: string) => { added.push(t) },
    removeEventListener: (t: string) => { removed.push(t) },
  } as unknown as HTMLElement
  return { el, added, removed }
}

/** 空的看板状态（render 会走 buildBoard 的零需求分支）。 */
const EMPTY_STATE = { revision: 1, requirements: [], tasks: [], ready: {} }

function okResponse(): Promise<Response> {
  return Promise.resolve(new Response(
    JSON.stringify({ success: true, data: EMPTY_STATE }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  ))
}

/** 记录 close 调用的 EventSource 桩（SSE 订阅的释放证据）。 */
const sseClosed: string[] = []
class FakeEventSource {
  onmessage: ((ev: MessageEvent) => void) | null = null
  constructor(readonly url: string) { /* 记录 URL 即可 */ }
  close(): void { sseClosed.push(this.url) }
}

beforeEach(() => {
  vi.useFakeTimers()
  sseClosed.length = 0
  vi.stubGlobal('fetch', vi.fn(() => okResponse()))
  vi.stubGlobal('EventSource', FakeEventSource)
  vi.stubGlobal('window', globalThis)
  vi.stubGlobal('document', {
    hidden: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  if (origFetch) globalThis.fetch = origFetch
})

describe('attachBoard（宿主挂载：挂上即收集，dispose 即释放）', () => {
  it('返回 disposer；dispose 后定时器归零、容器监听移除、SSE 关闭', () => {
    const { el, added, removed } = fakeContainer()
    const dispose = attachBoard(el)

    expect(typeof dispose).toBe('function')
    expect(added).toEqual(['click', 'change'])
    expect(vi.getTimerCount()).toBe(1) // 轮询 interval

    dispose()

    expect(removed).toEqual(['click', 'change'])
    expect(vi.getTimerCount()).toBe(0) // clearInterval 已生效
    expect(sseClosed).toEqual(['/dashboard/api/reqboard/events'])
  })

  it('dispose 幂等：重复调用不重复清理、不抛', () => {
    const { el, removed } = fakeContainer()
    const dispose = attachBoard(el)

    dispose()
    dispose()

    expect(removed).toEqual(['click', 'change'])
    expect(sseClosed).toHaveLength(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('isActive()=false → 到点跳过刷新；恢复可见 → 到点刷新', async () => {
    const fetchMock = vi.fn(() => okResponse())
    vi.stubGlobal('fetch', fetchMock)

    let visible = false
    const { el } = fakeContainer()
    const dispose = attachBoard(el, { isActive: () => visible })

    // 挂载即拉一次（与面板可见性无关）
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(1) // 3 个 tick 全被门闩跳过

    visible = true
    await vi.advanceTimersByTimeAsync(20_000)
    expect(fetchMock.mock.calls.length).toBeGreaterThan(1)

    dispose()
  })

  it('poll:false → 不自建定时器（轮询交回 board-shell）', () => {
    const { el, added } = fakeContainer()
    const dispose = attachBoard(el, { poll: false })

    expect(added).toEqual(['click', 'change']) // 事件委派与 SSE 照常
    expect(vi.getTimerCount()).toBe(0)

    dispose()
  })
})

// REQ-260928222643-4d34 · serves: FR-2
describe('board-mount 消费一次性定位意图（REQ-260928222643-4d34 FR-2）', () => {
  /** 具备渲染所需最小 DOM 面的容器：innerHTML + 查询方法（node 环境无真实 DOM）。 */
  function richContainer(): HTMLElement {
    return {
      innerHTML: '',
      addEventListener: () => {},
      removeEventListener: () => {},
      querySelectorAll: () => [],
      querySelector: () => null,
    } as unknown as HTMLElement
  }

  const REQ_A = {
    id: 'REQ-a', title: '需求甲', description: 'd', category: 'feature', status: 'implementing',
    blocked: false, comments: [], version: 1, createdAt: 1000, updatedAt: 2000,
    sourceSessionId: 'session-x', createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [],
  }

  function stateWith(reqs: unknown[]): Response {
    return new Response(
      JSON.stringify({ success: true, data: { revision: 1, requirements: reqs, tasks: [], ready: {} } }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    )
  }

  beforeEach(() => {
    vi.useRealTimers() // 覆盖外层 fake timers，配合 vi.waitFor 等待异步渲染
    clearBoardFocus()
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { void cb(0 as never); return 0 })
    vi.stubGlobal('document', {
      hidden: false,
      addEventListener: () => {},
      removeEventListener: () => {},
      getElementById: () => null,
      querySelector: () => null,
      querySelectorAll: () => [],
      createElement: () => ({ style: {}, setAttribute: () => {}, appendChild: () => {}, addEventListener: () => {} }),
    })
  })

  it('TC-7 命中台账 → 挂载进入该需求详情；意图取走即清', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(stateWith([REQ_A]))))
    requestBoardFocus('REQ-a')
    const el = richContainer()
    const dispose = attachBoard(el, { poll: false })
    await vi.waitFor(() => { expect(el.innerHTML).toContain('data-detail-req="REQ-a"') })
    expect(peekBoardFocus()).toBeUndefined() // 消费即清
    dispose()
  })

  it('TC-8 陈旧 id → 回退默认看板；再次挂载仍默认（非粘滞）', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(stateWith([]))))
    requestBoardFocus('REQ-gone')
    const el = richContainer()
    const dispose = attachBoard(el, { poll: false })
    await vi.waitFor(() => { expect(el.innerHTML.length).toBeGreaterThan(0) })
    expect(el.innerHTML).not.toContain('data-detail-req')
    expect(peekBoardFocus()).toBeUndefined()
    dispose()

    // 再次挂载（模拟再次进入看板）→ 意图已清，仍为默认视图（非粘滞）
    const el2 = richContainer()
    const dispose2 = attachBoard(el2, { poll: false })
    await vi.waitFor(() => { expect(el2.innerHTML.length).toBeGreaterThan(0) })
    expect(el2.innerHTML).not.toContain('data-detail-req')
    dispose2()
  })
})
