import { describe, it, expect } from 'vitest'
import { assembleRequirementToken } from '../src/application/query/QueryRequirementToken.js'
import { renderTokenTab } from '../src/client/token-info.ts'
import { emptyBuckets, type RequirementRecord, type TaskRecord, type TokenBuckets } from '../src/shared/protocol.js'

const B = (n: number): TokenBuckets => ({ uncachedInputTokens: n, outputTokens: n * 2, cacheReadTokens: n * 10, cacheWriteTokens: 0 })
const snap = (n: number) => ({ sessionId: 's1', at: n, totals: B(n), source: 'projection' as const })

function noNodeSnapshotReq(): RequirementRecord {
  return {
    id: 'REQ-abc123', title: '旧需求', description: 'd', category: 'feature', status: 'implementing',
    blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    // 关键：没有 tokenUsage.byStage（功能上线前创建）——节点全部无快照
    statusHistory: [{ status: 'implementing', at: 1, by: { kind: 'agent', sessionId: 's1' } }],
  } as RequirementRecord
}

function taskWithDelta(): TaskRecord {
  return {
    id: 't-abc123', requirementId: 'REQ-abc123', title: '返工任务', description: 'd', phase: 'implement', side: 'backend',
    dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: 'a', context: '', status: 'done',
    blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'agent', sessionId: 's1' }, updatedBy: { kind: 'agent', sessionId: 's1' },
    statusHistory: [],
    executions: [{ id: 'e-abc123', sessionId: 's1', trigger: 'manual', startedAt: 1, endedAt: 2, outcome: 'succeeded',
      tokenUsage: { start: snap(2), end: snap(5), delta: B(3) } }],
  } as TaskRecord
}

describe('REQ-a33899 兜底：节点无快照但任务有执行差值', () => {
  it('总量把无快照节点的执行差值算进来（避免「总量 0、任务行有数」）', () => {
    const view = assembleRequirementToken(noNodeSnapshotReq(), { tasks: [taskWithDelta()] })
    const impl = view.byStage.find(s => s.stage === 'implementing')!
    expect(impl.buckets).toBeUndefined()            // 节点仍如实「无快照」
    expect(impl.executions).toHaveLength(1)
    expect(view.totals).toEqual(B(3))               // 兜底进总量
  })

  it('无执行差值时总量仍是 0（诚实：确实没有可算的数据）', () => {
    const view = assembleRequirementToken(noNodeSnapshotReq(), { tasks: [] })
    expect(view.totals).toEqual(emptyBuckets())
  })

  it('UI：无快照节点行仍渲染任务下钻（不把执行差值吞掉）', () => {
    const view = assembleRequirementToken(noNodeSnapshotReq(), { tasks: [taskWithDelta()] })
    const html = renderTokenTab(view)
    expect(html).toContain('t-abc123')
    expect(html).toContain('返工任务')
    expect(html).toContain('无快照')       // 节点行如实标注
    expect(html).toContain('dsh-pm-tok-sub')
    expect(html).toContain('39')           // B(3) 三桶和 = 39
  })
})
