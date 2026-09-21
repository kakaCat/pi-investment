/**
 * web-liveness 判定逻辑单测。
 *
 * 这一层是"该不该刷新页面"的全部判断依据 —— 判错的两个方向都很难受：
 * 该刷不刷 = 用户继续对着旧页面（本次要修的事故）；不该刷乱刷 = 打字打到一半被刷掉。
 * 所以边界（读不到 rev、同进程重连、防抖窗口）逐条钉住。
 */
import { describe, expect, it } from 'vitest'
import {
  DEFAULT_QUIET_MS,
  RELOAD_GUARD_MS,
  bootRevOf,
  decideGraph,
  parseFrame,
  reloadAllowed,
  shouldReloadNow,
} from '../src/client/watch.js'

describe('bootRevOf', () => {
  it('读出注入的 graph rev', () => {
    expect(bootRevOf({ rev: '62e6b4c5bc83', entries: [] })).toBe('62e6b4c5bc83')
  })

  it('读不到就返回 undefined（缺字段 / 形状变了 / 空串）', () => {
    expect(bootRevOf(undefined)).toBeUndefined()
    expect(bootRevOf(null)).toBeUndefined()
    expect(bootRevOf('62e6b4c5bc83')).toBeUndefined()
    expect(bootRevOf({})).toBeUndefined()
    expect(bootRevOf({ rev: 42 })).toBeUndefined()
    expect(bootRevOf({ rev: '' })).toBeUndefined()
  })
})

describe('parseFrame', () => {
  it('解析 graph 帧（带 rev）', () => {
    expect(parseFrame('{"type":"graph","graph":{"rev":"5ef21f47205b612b-0"}}')).toEqual({
      type: 'graph',
      rev: '5ef21f47205b612b-0',
    })
  })

  it('解析无 graph 的帧（如 HMR 的 rebuilt）—— 帧型保留、rev 缺省', () => {
    expect(parseFrame('{"type":"rebuilt","id":"x"}')).toEqual({ type: 'rebuilt' })
  })

  it('非 JSON / 非对象 / 缺 type 一律 undefined', () => {
    expect(parseFrame('not json')).toBeUndefined()
    expect(parseFrame('[]')).toBeUndefined()
    expect(parseFrame('null')).toBeUndefined()
    expect(parseFrame('{"graph":{"rev":"a"}}')).toBeUndefined()
  })
})

describe('decideGraph', () => {
  it('rev 相同 = 同一进程（含同进程断线重连）→ recover，不刷新', () => {
    expect(decideGraph('62e6b4c5bc83', '62e6b4c5bc83')).toBe('recover')
  })

  it('rev 不同 = 换过进程或换过 bundle → reload', () => {
    expect(decideGraph('62e6b4c5bc83', '78d1cc62ab74')).toBe('reload')
    expect(decideGraph('5ef21f47205b612b-0', '5ef21f47205b612b-1')).toBe('reload')
  })

  it('任一侧读不到 → ignore（信息不足时不动，比乱刷安全）', () => {
    expect(decideGraph(undefined, '62e6b4c5bc83')).toBe('ignore')
    expect(decideGraph('62e6b4c5bc83', undefined)).toBe('ignore')
    expect(decideGraph(undefined, undefined)).toBe('ignore')
  })
})

describe('shouldReloadNow', () => {
  const now = 1_000_000

  it('页面在后台 → 立即刷新（没人在看，刷掉不心疼）', () => {
    expect(shouldReloadNow({ hidden: true, lastInputAt: now, now })).toBe(true)
  })

  it('用户刚打过字 → 先不刷，等停手', () => {
    expect(shouldReloadNow({ hidden: false, lastInputAt: now - 100, now })).toBe(false)
    expect(shouldReloadNow({ hidden: false, lastInputAt: now - DEFAULT_QUIET_MS + 1, now })).toBe(false)
  })

  it('用户已停顿够久 → 刷新', () => {
    expect(shouldReloadNow({ hidden: false, lastInputAt: now - DEFAULT_QUIET_MS, now })).toBe(true)
  })

  it('停顿阈值可覆盖', () => {
    expect(shouldReloadNow({ hidden: false, lastInputAt: now - 1_000, now, quietMs: 500 })).toBe(true)
  })
})

describe('reloadAllowed（刷新防抖闸门：防"刷新后仍拿旧 HTML"刷成死循环）', () => {
  const now = 1_000_000

  it('从没刷过 → 放行', () => {
    expect(reloadAllowed(undefined, now)).toBe(true)
  })

  it('刚刷过 → 拦住', () => {
    expect(reloadAllowed(now - 1, now)).toBe(false)
    expect(reloadAllowed(now - RELOAD_GUARD_MS + 1, now)).toBe(false)
  })

  it('超出闸门宽度 → 放行', () => {
    expect(reloadAllowed(now - RELOAD_GUARD_MS, now)).toBe(true)
  })

  it('标记损坏（NaN）→ 视为没刷过，放行', () => {
    expect(reloadAllowed(Number.NaN, now)).toBe(true)
  })
})
