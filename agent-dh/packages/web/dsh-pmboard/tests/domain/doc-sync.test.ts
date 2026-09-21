/**
 * L1 领域单测 · 文档同步规约（REQ-47939a t3 / INV-7，REQ-2e9473 t19/W8）。
 * 规则：上游变更 → 下游待同步；重交下游销标；同源旧标记被替换。
 */
import { describe, it, expect } from 'vitest'
import {
  applyDocSync,
  clearDocSync,
  docSyncDownstream,
  docSyncPendingOf,
  docSyncSummary,
  type DocSyncReqLike,
} from '../../src/domain/workflow/DocSyncSpec.js'

describe('docSyncDownstream', () => {
  it('requirement 变更 → 已登记的 plan / decomposition', () => {
    expect(docSyncDownstream('requirement', [{ kind: 'plan' }, { kind: 'decomposition' }])).toEqual(['plan', 'decomposition'])
    expect(docSyncDownstream('requirement', [{ kind: 'plan' }])).toEqual(['plan'])
    expect(docSyncDownstream('requirement', [])).toEqual([])
  })
  it('plan 变更 → 已登记的 decomposition', () => {
    expect(docSyncDownstream('plan', [{ kind: 'decomposition' }])).toEqual(['decomposition'])
    expect(docSyncDownstream('plan', [{ kind: 'plan' }])).toEqual([])
  })
})

describe('applyDocSync / clearDocSync / docSyncSummary', () => {
  it('applyDocSync 替换同源旧标记并写入新标记', () => {
    const req: DocSyncReqLike = {
      artifacts: [{ kind: 'plan' }, { kind: 'decomposition' }],
      docSyncPending: [{ source: 'requirement', downstream: ['plan'], reason: '旧', at: 1 }],
    }
    applyDocSync(req, 'requirement', '改了需求文档', 100)
    expect(req.docSyncPending).toEqual([
      { source: 'requirement', downstream: ['plan', 'decomposition'], reason: '改了需求文档', at: 100 },
    ])
  })

  it('clearDocSync 按 downstream 销标', () => {
    const req: DocSyncReqLike = {
      docSyncPending: [
        { source: 'requirement', downstream: ['plan', 'decomposition'], reason: 'r', at: 1 },
        { source: 'plan', downstream: ['decomposition'], reason: 'p', at: 2 },
      ],
    }
    clearDocSync(req, 'plan')
    expect(req.docSyncPending).toEqual([{ source: 'plan', downstream: ['decomposition'], reason: 'p', at: 2 }])
    clearDocSync(req, 'decomposition')
    expect(req.docSyncPending).toEqual([])
  })

  it('docSyncSummary：无标记 → 仅前缀；有标记 → source→downstream 串联', () => {
    expect(docSyncSummary({})).toBe('⏳ 文档待同步：')
    const req: DocSyncReqLike = {
      docSyncPending: [
        { source: 'requirement', downstream: ['plan', 'decomposition'], reason: 'r', at: 1 },
        { source: 'plan', downstream: [], reason: 'p', at: 2 },
      ],
    }
    expect(docSyncSummary(req)).toBe('⏳ 文档待同步：requirement→plan/decomposition；plan→-')
    expect(docSyncPendingOf(req)).toHaveLength(2)
    expect(docSyncPendingOf({})).toEqual([])
  })
})
