/**
 * Dive 会话驱动器装配 + "订阅失败改响亮"（2026-09-26；2026-09-26 二改：两路订阅）。
 *
 * 为什么单独测：两路订阅是整套事件驱动的总开关——采集路（session/event）挂不上 =
 * 证据缓冲/工具痕迹断源；驱动路（agent/status = idle，对齐 dsh-goal-round-driver）挂不上 =
 * 立项引导 / 待立项登记 / 阶段纪律注入 / 节点结算 / 里程碑催办 / 闸门链 Phase B / 断点补写
 * 全部静默停摆。此前只有一行 info 级 FAILED（可选链不抛），这正是"门禁失效而假绿"的同款。
 *
 * @module dsh-pmboard/tests/dive-session-driver-wiring
 */
import { describe, it, expect } from 'vitest'
import { assembleDiveSessionDriver } from '../src/wiring/pm-capture-root.js'
import { emptyLedger } from '../src/shared/protocol.js'

type SessionHandler = (s: unknown, e: unknown) => void
type StatusHandler = (a: unknown, st: unknown) => void

function makeDeps(
  attachSession: (h: SessionHandler) => (() => void) | undefined,
  attachAgentStatus: (h: StatusHandler) => (() => void) | undefined = () => () => {},
) {
  const warns: string[] = []
  const infos: string[] = []
  const deps = {
    store: { snapshot: () => emptyLedger() },
    runtime: {
      pendingCapture: new Map(),
      toolTrace: new Map(),
      recentUserMsgs: new Map(),
      deliverer: { deliver: () => ({ delivered: true }) },
    },
    now: () => 1,
    injectionLog: {},
    gateChain: { enqueue: () => {}, runPending: async () => ({ ran: false }) },
    onNodeSettled: () => {},
    useCaseDeps: () => ({}),
    logger: {
      info: (m: string) => infos.push(m),
      debug: () => {},
      warn: (m: string) => warns.push(m),
    },
    plugin: 'test',
    attachSessionDriver: attachSession,
    attachAgentStatus,
  }
  return { deps, warns, infos }
}

describe('Dive 会话驱动器装配（两路订阅生命周期归 Dive）', () => {
  it('两路订阅成立 → 返回解绑函数、info 登记成功、无 warn', () => {
    const { deps, warns, infos } = makeDeps(() => () => {}, () => () => {})
    const un = assembleDiveSessionDriver(deps as never)
    expect(typeof un).toBe('function')
    expect(warns).toEqual([])
    expect(infos.some(m => m.includes('dive session driver registered'))).toBe(true)
    expect(infos.some(m => m.includes('session/event=SUCCESS') && m.includes('agent/status=SUCCESS'))).toBe(true)
  })

  it('返回的合并解绑会同时解除两路订阅', () => {
    let sessionOff = 0
    let statusOff = 0
    const { deps } = makeDeps(() => () => { sessionOff++ }, () => () => { statusOff++ })
    const un = assembleDiveSessionDriver(deps as never)
    un?.()
    expect(sessionOff).toBe(1)
    expect(statusOff).toBe(1)
  })

  it('两路都没成立 → **响亮**：返回 undefined、warn 写明后果（不再只留 info）', () => {
    const { deps, warns } = makeDeps(() => undefined, () => undefined)
    const un = assembleDiveSessionDriver(deps as never)
    expect(un).toBeUndefined()
    const hit = warns.find(w => w.includes('订阅未成立'))
    expect(hit).toBeDefined()
    expect(hit).toContain('闸门链 Phase B')
    expect(hit).toContain('agent/status')
  })

  it('只装配一路 → 响亮 warn 指出缺哪一路（半接线不得假绿）', () => {
    const { deps, warns } = makeDeps(() => () => {}, () => undefined)
    const un = assembleDiveSessionDriver(deps as never)
    expect(typeof un).toBe('function')
    const hit = warns.find(w => w.includes('仅装配了一路订阅'))
    expect(hit).toBeDefined()
    expect(hit).toContain('agent/status=MISSING')
  })
})
