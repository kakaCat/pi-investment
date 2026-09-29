/**
 * 两端注册接线单测（REQ-260928185112-e20d FR-1/FR-2，t-75e700）：
 * ① registerPmboardPage 一次注册 main（key）与 sidebar.panellist（id），两端 id 同源；
 * ② page-runtime 的 layout 持有器 set/get/clear 往返一致、无残留（session-jump 的读取面）。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { registerPmboardPage, PMBOARD_PAGE_ORDER } from '../src/client/page/register.ts'
import { BoardPanelHost } from '../src/client/page/host.ts'
import { PANEL_ID, PANEL_LABEL } from '../src/client/dom.ts'
import { setPageLayout, getPageLayout, clearPageLayout } from '../src/client/page/page-runtime.ts'

interface Reg {
  name?: string
  key?: string
  id?: string
  order?: number
  label?: string
  occupant?: unknown
}

/** 假 slots：记录 inject 的目标槽位与每次 register 的 options/occupant。 */
function fakeSlots(): { slots: { inject(s: string, t: () => unknown): unknown; register(o: Record<string, unknown>, c: unknown): unknown }; regs: Reg[]; injections: string[] } {
  const regs: Reg[] = []
  const injections: string[] = []
  const slots = {
    inject(slot: string, thunk: () => unknown): unknown {
      injections.push(slot)
      return thunk()
    },
    register(options: Record<string, unknown>, occupant: unknown): unknown {
      regs.push({ ...options, occupant })
      return undefined
    },
  }
  return { slots, regs, injections }
}

describe('registerPmboardPage', () => {
  it('一次注册 main(key) 与 sidebar.panellist(id)，两端同源', () => {
    const f = fakeSlots()
    registerPmboardPage({ slots: f.slots })

    expect(f.injections).toEqual(['main', 'sidebar.panellist'])
    expect(f.regs).toHaveLength(2)
    const main = f.regs[0]
    const side = f.regs[1]

    expect(main.name).toBe('main')
    expect(main.key).toBe(PANEL_ID)
    expect(main.occupant).toBe(BoardPanelHost)

    expect(side.name).toBe('sidebar.panellist')
    expect(side.id).toBe(PANEL_ID)
    expect(side.order).toBe(PMBOARD_PAGE_ORDER)
    expect(side.label).toBe(PANEL_LABEL)

    // 同源：不可能只改一端（FR-1 的可证伪点）
    expect(main.key).toBe(side.id)
  })

  it('ctx.slots 缺失时响亮抛错（不静默降级为「页面不存在」）', () => {
    expect(() => registerPmboardPage({})).toThrow(/ctx.slots unavailable/)
  })
})

describe('page-runtime layout 持有器', () => {
  beforeEach(() => { clearPageLayout() })

  it('未注入时返回 undefined（调用方须显式处理不可用）', () => {
    expect(getPageLayout()).toBeUndefined()
  })

  it('set/get/clear 往返一致，clear 后无残留', () => {
    const calls: Array<string | null> = []
    const layout = { selectPanel: (id: string | null): void => { calls.push(id) } }

    setPageLayout(layout)
    expect(getPageLayout()).toBe(layout)
    getPageLayout()?.selectPanel(null)
    expect(calls).toEqual([null])

    clearPageLayout()
    expect(getPageLayout()).toBeUndefined()
  })
})
