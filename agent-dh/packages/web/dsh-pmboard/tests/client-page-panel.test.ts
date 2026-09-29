/**
 * 页面插槽注册 helper 单测（REQ-260928185112-e20d t1）。
 *
 * 核心契约：一次调用注册两端，且 main.key 与 sidebar.panellist.id 同源。
 * 假 ctx 只记录调用参数——不依赖 React、不依赖真实 slots 服务。
 */
import { describe, it, expect } from 'vitest'
import { registerPagePanel, PAGE_PANEL_MAIN_SLOT, PAGE_PANEL_SIDEBAR_SLOT } from '../src/client/page/page-panel.ts'

interface Registration {
  options: Record<string, unknown>
  occupant: unknown
}

function fakeSlots() {
  const injected: string[] = []
  const regs: Registration[] = []
  const disposed: number[] = []
  let seq = 0
  const slots = {
    inject(slot: string, thunk: () => unknown): unknown {
      injected.push(slot)
      return thunk()
    },
    register(options: Record<string, unknown>, occupant: unknown): unknown {
      const i = seq++
      regs.push({ options, occupant })
      return () => { disposed.push(i) }
    },
  }
  return { slots, injected, regs, disposed }
}

const COMPONENT = () => null

describe("registerPagePanel", () => {
  it("一次调用注册两端，且注入名与注册名一一对应", () => {
    const f = fakeSlots()
    registerPagePanel({ slots: f.slots }, { id: "dsh-pmboard", label: "项目看板", Component: COMPONENT })
    expect(f.injected).toEqual([PAGE_PANEL_MAIN_SLOT, PAGE_PANEL_SIDEBAR_SLOT])
    expect(f.regs).toHaveLength(2)
    expect(f.regs[0].options.name).toBe("main")
    expect(f.regs[1].options.name).toBe("sidebar.panellist")
  })

  it("两端 id 同源：main.key 与 panellist.id 都等于 spec.id", () => {
    const f = fakeSlots()
    registerPagePanel({ slots: f.slots }, { id: "dsh-pmboard", label: "项目看板", Component: COMPONENT })
    expect(f.regs[0].options.key).toBe("dsh-pmboard")
    expect(f.regs[1].options.id).toBe("dsh-pmboard")
    expect(f.regs[0].options.id).toBeUndefined()
    expect(f.regs[1].options.key).toBeUndefined()
  })

  it("侧栏元数据：label 透传、order 缺省为 0、显式值生效", () => {
    const a = fakeSlots()
    registerPagePanel({ slots: a.slots }, { id: "x", label: "看板", Component: COMPONENT })
    expect(a.regs[1].options.label).toBe("看板")
    expect(a.regs[1].options.order).toBe(0)
    const b = fakeSlots()
    registerPagePanel({ slots: b.slots }, { id: "x", label: "看板", order: 110, Component: COMPONENT })
    expect(b.regs[1].options.order).toBe(110)
  })

  it("Component 透传给 main 占用者；Icon 缺省仍注册侧栏条目（占位组件）", () => {
    const f = fakeSlots()
    registerPagePanel({ slots: f.slots }, { id: "x", label: "看板", Component: COMPONENT })
    expect(f.regs[0].occupant).toBe(COMPONENT)
    expect(typeof f.regs[1].occupant).toBe("function")
    expect((f.regs[1].occupant as () => unknown)()).toBeNull()
    const g = fakeSlots()
    const ICON = () => null
    registerPagePanel({ slots: g.slots }, { id: "x", label: "看板", Component: COMPONENT, Icon: ICON })
    expect(g.regs[1].occupant).toBe(ICON)
  })

  it("disposer 幂等：两次调用只撤销一轮", () => {
    const f = fakeSlots()
    const dispose = registerPagePanel({ slots: f.slots }, { id: "x", label: "看板", Component: COMPONENT })
    dispose()
    dispose()
    expect(f.disposed).toEqual([0, 1])
  })

  it("ctx.slots 缺失时抛错（响亮失败，不静默降级）", () => {
    expect(() => registerPagePanel({}, { id: "x", label: "看板", Component: COMPONENT })).toThrow(/ctx.slots unavailable/)
    expect(() => registerPagePanel(undefined as never, { id: "x", label: "看板", Component: COMPONENT })).toThrow(/ctx.slots unavailable/)
  })
})
