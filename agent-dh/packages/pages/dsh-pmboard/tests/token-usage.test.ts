import { describe, it, expect } from 'vitest'
import {
  emptyBuckets, addBuckets, subBuckets, totalTokens,
  estimateTokensFromChars, TOKENS_PER_CHAR, fmtTokens, fmtCny,
  type TokenBuckets,
} from '../src/shared/protocol.js'

const B = (a: number, o: number, r: number, w: number): TokenBuckets =>
  ({ uncachedInputTokens: a, outputTokens: o, cacheReadTokens: r, cacheWriteTokens: w })

describe('token 契约：四桶运算（REQ-a33899 t1）', () => {
  it('emptyBuckets 全 0（空桶是「无新增」，不是缺失）', () => {
    expect(emptyBuckets()).toEqual(B(0, 0, 0, 0))
  })

  it('addBuckets 逐分量相加', () => {
    expect(addBuckets(B(1, 2, 3, 4), B(10, 20, 30, 40))).toEqual(B(11, 22, 33, 44))
  })

  it('subBuckets 正常差值', () => {
    expect(subBuckets(B(10, 20, 30, 40), B(1, 2, 3, 4))).toEqual(B(9, 18, 27, 36))
  })

  it('subBuckets 负分量截断为 0（快照乱序不产出负数）', () => {
    expect(subBuckets(B(1, 20, 3, 40), B(10, 2, 30, 4))).toEqual(B(0, 18, 0, 36))
  })

  it('totalTokens = 四桶之和', () => {
    expect(totalTokens(B(1, 2, 3, 4))).toBe(10)
    expect(totalTokens(emptyBuckets())).toBe(0)
  })
})

describe('token 契约：字符→token 估算', () => {
  it('密度常量与 DSH 固定启发式一致（4 字符/token）', () => {
    expect(TOKENS_PER_CHAR).toBe(0.25)
  })

  it('estimateTokensFromChars 单调非负且向上取整', () => {
    expect(estimateTokensFromChars(0)).toBe(0)
    expect(estimateTokensFromChars(1)).toBe(1)
    expect(estimateTokensFromChars(4)).toBe(1)
    expect(estimateTokensFromChars(5)).toBe(2)
    const xs = [1, 10, 100, 1000, 10000]
    const ys = xs.map(estimateTokensFromChars)
    for (let i = 1; i < ys.length; i += 1) expect(ys[i]).toBeGreaterThanOrEqual(ys[i - 1])
    for (const y of ys) expect(y).toBeGreaterThanOrEqual(0)
  })

  it('负数/非有限 → 0（缺失不冒充数字）', () => {
    expect(estimateTokensFromChars(-5)).toBe(0)
    expect(estimateTokensFromChars(Number.NaN)).toBe(0)
    expect(estimateTokensFromChars(Number.POSITIVE_INFINITY)).toBe(0)
  })
})

describe('token 契约：显示格式', () => {
  it('fmtTokens：<1000 原数 / k / M', () => {
    expect(fmtTokens(0)).toBe('0')
    expect(fmtTokens(999)).toBe('999')
    expect(fmtTokens(1000)).toBe('1.0k')
    expect(fmtTokens(1234)).toBe('1.2k')
    expect(fmtTokens(999999)).toBe('1000.0k')
    expect(fmtTokens(1000000)).toBe('1.0M')
    expect(fmtTokens(1234567)).toBe('1.2M')
  })

  it('fmtTokens：负值/非有限按 0', () => {
    expect(fmtTokens(-1)).toBe('0')
    expect(fmtTokens(Number.NaN)).toBe('0')
  })

  it('fmtCny：undefined/null → —；否则 ¥N.NN', () => {
    expect(fmtCny(undefined)).toBe('—')
    expect(fmtCny(null)).toBe('—')
    expect(fmtCny(Number.NaN)).toBe('—')
    expect(fmtCny(0)).toBe('¥0.00')
    expect(fmtCny(2.3)).toBe('¥2.30')
    expect(fmtCny(2.345)).toBe('¥2.35')
  })
})
