import { describe, it, expect } from 'vitest'
import { parseParts, pickParts, HOT_PARTS, COLD_PARTS, ALL_PARTS } from '../src/services/parts'

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
