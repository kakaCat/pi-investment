import { describe, it, expect } from 'vitest'
import { parseParts, pickParts, HOT_PARTS, COLD_PARTS, ALL_PARTS, hasColdParts, refreshModeFor, fetchPlanFor } from '../src/services/parts'

/**
 * 分块契约锁（2026-09-13，w-adb088f2）
 *
 * 背景：整包 82 KB 中 watchRules 占 79.5 KB（94.8%），而看板每 15 秒轮询同一接口 →
 * 每 15 秒重传 82 KB、其中 95% 是几乎不变的盯盘规则，页面"卡住"。
 * 契约：缺省＝全量（向后兼容）；hot/cold 预设；**未知输入必须退回全量**（绝不能返回空页面）。
 */
describe('parseParts', () => {
  it('缺省 / 空串 → 全量（向后兼容，老客户端不带参数照常工作）', () => {
    expect(parseParts(null)).toEqual([...ALL_PARTS])
    expect(parseParts(undefined)).toEqual([...ALL_PARTS])
    expect(parseParts('')).toEqual([...ALL_PARTS])
    expect(parseParts('   ')).toEqual([...ALL_PARTS])
  })

  it('hot 预设 = 高频小块（不含盯盘规则/成交明细）', () => {
    const parts = parseParts('hot')
    expect(parts).toEqual([...HOT_PARTS])
    expect(parts).not.toContain('watchRules')
    expect(parts).not.toContain('tradeHistory')
  })

  it('hot 必须包含 currentAccount（下拉框 selected 由它渲染，缺了会「下拉显示 A、数据是 B」）', () => {
    expect(parseParts('hot')).toContain('currentAccount')
  })

  it('cold 预设 = 低频大块', () => {
    expect(parseParts('cold')).toEqual([...COLD_PARTS])
  })

  it('显式列表过滤未知块；全是未知块时退回全量', () => {
    expect(parseParts('positions,summary')).toEqual(['positions', 'summary'])
    expect(parseParts('positions,不存在的块')).toEqual(['positions'])
    expect(parseParts('乱写')).toEqual([...ALL_PARTS])
  })

  it('大小写与空格容错', () => {
    expect(parseParts(' HOT ')).toEqual([...HOT_PARTS])
    expect(parseParts('Positions , Summary')).toEqual(['positions', 'summary'])
  })
})

describe('pickParts', () => {
  it('只取本次实际返回的块 —— 不把未返回的大块擦成空（否则页面会"有数据突然变空"）', () => {
    const full = { accounts: [1], positions: [2], watchRules: [3], tradeHistory: [4], parts: ['accounts', 'positions'] }
    const merged = pickParts(full, full.parts)
    expect(merged).toEqual({ accounts: [1], positions: [2] })
    expect('watchRules' in merged).toBe(false)
  })

  it('未声明 parts 时取全部（保守）', () => {
    const payload = { a: 1, b: 2 }
    expect(pickParts(payload, undefined)).toEqual({ a: 1, b: 2 })
  })
})

/**
 * 取数时机契约（2026-09-13 二次修正，w-adb088f2）
 *
 * 实证问题：旧逻辑 refresh() 里 `pollTick % 4 === 1 → full`，而 refresh 是在 **挂载** 时调用的
 * → 用户整天没点开看板，也白拉一次 77 KB 全量；而打开看板却没有 onOpen 回调，看到的是挂载那刻的旧数据。
 */
describe('refreshModeFor / hasColdParts', () => {
  it('冷块不在手 → 必须 full（否则盯盘/成交卡片永远是空的）', () => {
    expect(refreshModeFor(1, undefined)).toBe('full')
    expect(refreshModeFor(1, { parts: [...HOT_PARTS] })).toBe('full')
    expect(refreshModeFor(1, { parts: ['accounts', 'watchRules'] })).toBe('full')
  })

  it('冷块在手 → 第 1 次必须是 hot（回归锁：旧写法让首次恒为 77 KB 全量）', () => {
    const all = { parts: [...ALL_PARTS] }
    expect(refreshModeFor(1, all)).toBe('hot')
    expect(refreshModeFor(2, all)).toBe('hot')
  })

  it('冷块在手 → 每 4 次补一次 full（15s × 4 ≈ 60s）', () => {
    const all = { parts: [...ALL_PARTS] }
    expect(refreshModeFor(3, all)).toBe('hot')
    expect(refreshModeFor(4, all)).toBe('full')
    expect(refreshModeFor(8, all)).toBe('full')
  })

  it('冷块判据是「全都到手」而非「有一个就算」', () => {
    expect(hasColdParts({ parts: ['watchRules'] })).toBe(false)
    expect(hasColdParts({ parts: ['watchRules', 'tradeHistory'] })).toBe(false)
    expect(hasColdParts({ parts: [...COLD_PARTS] })).toBe(true)
    expect(hasColdParts(undefined)).toBe(false)
  })
})

/**
 * 取数时机契约锁（2026-09-13 三次修正，w-ae7eb4c0 / REQ-6cbbf7）
 *
 * 实证缺陷：容器由 page-kit 在**启动时**就同步挂载（显隐靠 html[data-dsh-hld-active]，
 * 挂载 ≠ 用户在看），而 board-mount 的 onMount 里主动拉了一次 hot
 * → 用户没点开看板，启动就发了请求（控制台可见 mount prime (hot) + 已渲染）。
 * 契约：**mount 永不取数**（返回 null）；open 首次为 full（一次拿齐冷块）；poll 沿用每 4 次补一次 full。
 */
describe('fetchPlanFor', () => {
  it('mount 恒不取数（冷块在手/不在手都返回 null）——启动阶段零请求', () => {
    expect(fetchPlanFor('mount', 1, undefined)).toBeNull()
    expect(fetchPlanFor('mount', 1, { parts: [...ALL_PARTS] })).toBeNull()
    expect(fetchPlanFor('mount', 4, { parts: [...HOT_PARTS] })).toBeNull()
  })

  it('open：冷块不在手 → full（首次打开一次拿齐）；已在手 → hot', () => {
    expect(fetchPlanFor('open', 1, undefined)).toBe('full')
    expect(fetchPlanFor('open', 1, { parts: [...HOT_PARTS] })).toBe('full')
    expect(fetchPlanFor('open', 1, { parts: [...ALL_PARTS] })).toBe('hot')
  })

  it('poll：沿用 refreshModeFor（每 4 次补一次 full）', () => {
    const all = { parts: [...ALL_PARTS] }
    expect(fetchPlanFor('poll', 1, all)).toBe('hot')
    expect(fetchPlanFor('poll', 4, all)).toBe('full')
    expect(fetchPlanFor('poll', 2, undefined)).toBe('full')
  })
})
