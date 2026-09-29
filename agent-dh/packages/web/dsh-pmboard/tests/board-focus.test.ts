/**
 * 一次性交接持有器语义单测（REQ-260928222643-4d34 · serves: FR-2 · 设计 I-1/T-2/T-3，用例 TC-6）。
 *
 * 可证伪点：① 登记后 take 得值；② take 取走即清（第二次为 undefined）；③ clear 幂等；
 * ④ 空串/纯空白不登记空意图；⑤ peek 只读不消费。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { requestBoardFocus, takeBoardFocus, clearBoardFocus, peekBoardFocus } from '../src/client/board-focus.ts'

describe('board-focus（一次性定位交接）', () => {
  beforeEach(() => { clearBoardFocus() })

  it('TC-6① 登记后 take 得值', () => {
    requestBoardFocus('REQ-a')
    expect(takeBoardFocus()).toBe('REQ-a')
  })

  it('TC-6② 取走即清：第二次 take 必为 undefined', () => {
    requestBoardFocus('REQ-a')
    takeBoardFocus()
    expect(takeBoardFocus()).toBeUndefined()
  })

  it('TC-6③ clear 幂等，peek 为 undefined', () => {
    requestBoardFocus('REQ-a')
    clearBoardFocus()
    clearBoardFocus()
    expect(peekBoardFocus()).toBeUndefined()
  })

  it('TC-6④ 空串/纯空白不登记空意图', () => {
    requestBoardFocus('   ')
    expect(peekBoardFocus()).toBeUndefined()
    expect(takeBoardFocus()).toBeUndefined()
  })

  it('peek 只读不消费', () => {
    requestBoardFocus('REQ-b')
    expect(peekBoardFocus()).toBe('REQ-b')
    expect(peekBoardFocus()).toBe('REQ-b')
    expect(takeBoardFocus()).toBe('REQ-b')
  })
})
