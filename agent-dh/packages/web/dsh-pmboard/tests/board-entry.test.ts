/**
 * 入口校验与失败提示单测（REQ-260928222643-4d34 · serves: FR-3 · 设计 I-2/I-6，用例 TC-9~TC-13）。
 *
 * 可证伪点：layout 未注入 / REQ 不在台账 / 台账接口失败 → ok:false 且**零副作用**
 * （requestFocus 与 selectPanel 均 0 次）；成功 → requestFocus 恰好 1 次。
 */
import { describe, it, expect, vi } from 'vitest'
import { activateBoardEntry, boardEntryFailureMessage, type BoardEntryDeps } from '../src/client/board-entry.ts'

function mkDeps(over: Partial<BoardEntryDeps> = {}): {
  deps: BoardEntryDeps
  isKnown: ReturnType<typeof vi.fn>
  requestFocus: ReturnType<typeof vi.fn>
  selectPanel: ReturnType<typeof vi.fn>
} {
  const isKnown = vi.fn(async () => true)
  const requestFocus = vi.fn()
  const selectPanel = vi.fn()
  const deps: BoardEntryDeps = {
    isKnown: isKnown as unknown as BoardEntryDeps['isKnown'],
    requestFocus,
    layout: { selectPanel },
    ...over,
  }
  return { deps, isKnown, requestFocus, selectPanel }
}

describe('activateBoardEntry（先校验、后切页）', () => {
  it('TC-9 layout 未注入 → nav-unavailable，零副作用', async () => {
    const { deps, isKnown, requestFocus, selectPanel } = mkDeps({ layout: undefined })
    const v = await activateBoardEntry('REQ-a', deps)
    expect(v.ok).toBe(false)
    if (!v.ok) {
      expect(v.reason).toBe('nav-unavailable')
      expect(v.message).toContain('导航服务不可用')
    }
    expect(isKnown).toHaveBeenCalledTimes(0)
    expect(requestFocus).toHaveBeenCalledTimes(0)
    expect(selectPanel).toHaveBeenCalledTimes(0)
  })

  it('TC-10 REQ 不在台账 → req-missing，零副作用', async () => {
    const { deps, requestFocus, selectPanel } = mkDeps({ isKnown: vi.fn(async () => false) as unknown as BoardEntryDeps['isKnown'] })
    const v = await activateBoardEntry('REQ-a', deps)
    expect(v.ok).toBe(false)
    if (!v.ok) {
      expect(v.reason).toBe('req-missing')
      expect(v.message).toContain('REQ-a')
      expect(v.message).toContain('不在台账')
    }
    expect(requestFocus).toHaveBeenCalledTimes(0)
    expect(selectPanel).toHaveBeenCalledTimes(0)
  })

  it('TC-10′ 空 reqId → req-missing 且不打接口', async () => {
    const { deps, isKnown, requestFocus } = mkDeps()
    const v = await activateBoardEntry('', deps)
    expect(v.ok).toBe(false)
    if (!v.ok) expect(v.reason).toBe('req-missing')
    expect(isKnown).toHaveBeenCalledTimes(0)
    expect(requestFocus).toHaveBeenCalledTimes(0)
  })

  it('TC-11 台账接口失败 → ledger-unreachable，零副作用', async () => {
    const { deps, requestFocus, selectPanel } = mkDeps({ isKnown: vi.fn(async () => { throw new Error('timeout 8000ms') }) as unknown as BoardEntryDeps['isKnown'] })
    const v = await activateBoardEntry('REQ-a', deps)
    expect(v.ok).toBe(false)
    if (!v.ok) {
      expect(v.reason).toBe('ledger-unreachable')
      expect(v.message).toContain('无法确认需求是否可达')
      expect(v.message).toContain('timeout 8000ms')
    }
    expect(requestFocus).toHaveBeenCalledTimes(0)
    expect(selectPanel).toHaveBeenCalledTimes(0)
  })

  it('TC-12 成功路径 → requestFocus 恰好 1 次', async () => {
    const { deps, requestFocus, selectPanel } = mkDeps()
    const v = await activateBoardEntry('REQ-a', deps)
    expect(v).toEqual({ ok: true })
    expect(requestFocus).toHaveBeenCalledTimes(1)
    expect(requestFocus).toHaveBeenCalledWith('REQ-a')
    expect(selectPanel).toHaveBeenCalledTimes(0) // 切页归调用方，本函数不切
  })

  it('TC-13 三种失败路径 requestFocus 与 selectPanel 均为 0', async () => {
    const cases: Array<() => ReturnType<typeof mkDeps>> = [
      () => mkDeps({ layout: undefined }),
      () => mkDeps({ isKnown: vi.fn(async () => false) as unknown as BoardEntryDeps['isKnown'] }),
      () => mkDeps({ isKnown: vi.fn(async () => { throw new Error('boom') }) as unknown as BoardEntryDeps['isKnown'] }),
    ]
    for (const make of cases) {
      const { deps, requestFocus, selectPanel } = make()
      await activateBoardEntry('REQ-a', deps)
      expect(requestFocus).toHaveBeenCalledTimes(0)
      expect(selectPanel).toHaveBeenCalledTimes(0)
    }
  })

  it('boardEntryFailureMessage 三种文案齐备', () => {
    expect(boardEntryFailureMessage('nav-unavailable', 'REQ-a')).toContain('layout 未注入')
    expect(boardEntryFailureMessage('req-missing', 'REQ-a')).toContain('REQ-a')
    expect(boardEntryFailureMessage('ledger-unreachable', 'REQ-a', 'ECONNREFUSED')).toContain('ECONNREFUSED')
  })
})
