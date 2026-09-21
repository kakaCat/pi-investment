/**
 * 需求侧接收标记单测（REQ-d3e61a T-5 / serve FR-3）
 *
 * 验收口径：**取消某张卡对某条的交付后，该条回落为「未被接收（红）」**。
 * 这是 R9 的解药：它当时在任何界面上都没有"没人接"的痕迹，所以能溜过四个节点。
 */
import { describe, expect, it } from 'vitest'
import { clauseReceiveStatus, unreceivedClauses } from '../src/application/internal/content-gate-wiring.js'

const ROOTS = ['FR-1', 'FR-4', 'FR-9']

describe('clauseReceiveStatus（四态）', () => {
  it('有卡接收 → received，并列出卡 id', () => {
    const s = clauseReceiveStatus(ROOTS, [{ id: 't-1', requirement_refs: ['FR-1'] }], [{ id: 't-1', status: 'in_progress' }])
    expect(s.find(x => x.clause === 'FR-1')).toEqual({ clause: 'FR-1', state: 'received', by: ['t-1'] })
  })

  it('接收它的卡全结单且有证据 → done', () => {
    const s = clauseReceiveStatus(
      ROOTS,
      [{ id: 't-1', requirement_refs: ['FR-1'] }],
      [{ id: 't-1', status: 'done', lastReport: { completed: ['改了 a.ts'] } }],
    )
    expect(s.find(x => x.clause === 'FR-1')?.state).toBe('done')
  })

  it('卡结单但**没有证据** → 停在 received（不算完成）', () => {
    const s = clauseReceiveStatus(
      ROOTS,
      [{ id: 't-1', requirement_refs: ['FR-1'] }],
      [{ id: 't-1', status: 'done' }],
    )
    expect(s.find(x => x.clause === 'FR-1')?.state).toBe('received')
  })

  it('无人接收且未裁剪 → **unreceived（红）**', () => {
    const s = clauseReceiveStatus(ROOTS, [{ id: 't-1', requirement_refs: ['FR-1'] }], [])
    expect(s.find(x => x.clause === 'FR-9')?.state).toBe('unreceived')
  })

  it('显式裁剪 → skipped（不是红）', () => {
    const s = clauseReceiveStatus(ROOTS, [], [], ['FR-9'])
    expect(s.find(x => x.clause === 'FR-9')?.state).toBe('skipped')
  })

  it('camelCase 的 requirementRefs 同样被认', () => {
    const s = clauseReceiveStatus(ROOTS, [{ id: 't-1', requirementRefs: ['FR-4'] }], [])
    expect(s.find(x => x.clause === 'FR-4')?.state).toBe('received')
  })
})

describe('**验收场景**：取消某张卡对某条的交付 → 该条回落为「未被接收（红）」', () => {
  const before = [
    { id: 't-1', requirement_refs: ['FR-1', 'FR-4'] },
    { id: 't-2', requirement_refs: ['FR-9'] },
  ]
  const after = [
    { id: 't-1', requirement_refs: ['FR-1'] },       // 取消了对 FR-4 的交付
    { id: 't-2', requirement_refs: ['FR-9'] },
  ]
  const tasks = [{ id: 't-1', status: 'in_progress' }, { id: 't-2', status: 'in_progress' }]

  it('取消前：三条都有接收，无红', () => {
    expect(unreceivedClauses(clauseReceiveStatus(ROOTS, before, tasks))).toEqual([])
  })

  it('取消后：FR-4 **回落为未被接收（红）**', () => {
    const s = clauseReceiveStatus(ROOTS, after, tasks)
    expect(s.find(x => x.clause === 'FR-4')?.state).toBe('unreceived')
    expect(unreceivedClauses(s)).toEqual(['FR-4'])
  })

  it('未被接收的清单是显式输出（供看板/状态面标红），不是靠人读全文', () => {
    const s = clauseReceiveStatus(ROOTS, after, tasks)
    expect(unreceivedClauses(s)).toHaveLength(1)
    expect(unreceivedClauses(s)[0]).toBe('FR-4')
  })
})
