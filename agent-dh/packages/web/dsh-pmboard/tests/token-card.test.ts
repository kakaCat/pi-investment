import { describe, it, expect } from 'vitest'
import { toReqCards, renderListCard } from '../src/client/views/board.ts'
import { renderReqCard } from '../src/client/views/artifacts.ts'
import type { BoardState, RequirementRecord, ReqCard } from '../src/client/types.ts'

function req(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: 'REQ-abc123', title: '需求', description: 'd', category: 'feature', status: 'implementing',
    blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    ...over,
  } as RequirementRecord
}

function state(over: Partial<BoardState> = {}): BoardState {
  return { revision: 1, requirements: [req()], tasks: [], ready: {}, ...over }
}

function cardFor(s: BoardState): ReqCard {
  return toReqCards(s)[0]!
}

describe('REQ-a33899 t7 · 卡面累计 token', () => {
  it('有 tokenTotals → 卡面渲染 🪙 徽章', () => {
    const s = state({ tokenTotals: { 'REQ-abc123': 1234567 } })
    expect(cardFor(s).tokenTotal).toBe(1234567)
    const html = renderReqCard(cardFor(s), 1)
    expect(html).toContain('dsh-pm-token-badge')
    expect(html).toContain('🪙 1.2M')
  })

  it('无 tokenTotals → 不渲染徽章（零噪音，不显示 0）', () => {
    const s = state()
    expect(cardFor(s).tokenTotal).toBeUndefined()
    expect(renderReqCard(cardFor(s), 1)).not.toContain('dsh-pm-token-badge')
  })

  it('列表视图同样带徽章', () => {
    const s = state({ tokenTotals: { 'REQ-abc123': 1234 } })
    const html = renderListCard(cardFor(s), 1)
    expect(html).toContain('dsh-pm-token-badge')
    expect(html).toContain('🪙 1.2k')
  })
})
