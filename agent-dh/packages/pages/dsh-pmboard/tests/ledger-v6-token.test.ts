import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, writeFileSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { makeHarness, req, task } from './application/harness.js'
import { executeMoveRequirement } from '../src/application/use-cases/MoveRequirement.js'
import { executeMoveTask } from '../src/application/use-cases/MoveTask.js'
import { executeReportTask } from '../src/application/use-cases/ReportTask.js'
import { JsonLedgerRepository } from '../src/adapters/JsonLedgerRepository.js'
import { accumulateStageDelta } from '../src/application/internal/token-usage.js'
import { emptyBuckets, type StatusEvent, type TokenBuckets, type TokenSnapshot } from '../src/shared/protocol.js'

const EXEC = { agent: { id: 'session-w-001' } }
const B = (n: number): TokenBuckets => ({ uncachedInputTokens: n, outputTokens: n * 2, cacheReadTokens: n * 10, cacheWriteTokens: 0 })
const snap = (n: number, sessionId = 'session-w-001'): TokenSnapshot => ({ sessionId, at: 1000 + n, totals: B(n), source: 'projection' })
const unavailable = (): TokenSnapshot => ({ at: 1, totals: emptyBuckets(), source: 'unavailable' })

describe('REQ-a33899 t3 · 写时快照：需求节点', () => {
  it('推进后新事件带 tokenSnapshot，并结算离开节点的差值（同会话）', async () => {
    const draft: StatusEvent = { status: 'draft', at: 1, by: { kind: 'agent', sessionId: 'session-w-001' }, tokenSnapshot: snap(1) }
    const h = makeHarness({ requirements: [req({ status: 'draft', statusHistory: [draft] })] })
    h.session.tokenSnapshot = snap(4)
    await executeMoveRequirement(h.deps, { to: 'brainstorming' }, EXEC)
    const after = h.repo.ledger.requirements[0]!
    const last = after.statusHistory![after.statusHistory!.length - 1]!
    expect(last.status).toBe('brainstorming')
    expect(last.tokenSnapshot!.totals).toEqual(B(4))
    expect(after.tokenUsage!.byStage.draft).toEqual(B(3))
    expect(after.tokenUsage!.totals).toEqual(B(3))
  })

  it('快照不可得 → 事件标 unavailable，且不产生 tokenUsage（缺失 ≠ 0）', async () => {
    const draft: StatusEvent = { status: 'draft', at: 1, by: { kind: 'agent', sessionId: 'session-w-001' }, tokenSnapshot: snap(1) }
    const h = makeHarness({ requirements: [req({ status: 'draft', statusHistory: [draft] })] })
    h.session.tokenSnapshot = unavailable()
    await executeMoveRequirement(h.deps, { to: 'brainstorming' }, EXEC)
    const after = h.repo.ledger.requirements[0]!
    const last = after.statusHistory![after.statusHistory!.length - 1]!
    expect(last.tokenSnapshot!.source).toBe('unavailable')
    expect(after.tokenUsage).toBeUndefined()
  })

  it('跨 2 节点：byStage 两个键、totals = 各节点之和', () => {
    const r = req({
      status: 'implementing',
      statusHistory: [
        { status: 'draft', at: 1, by: { kind: 'agent', sessionId: 's' }, tokenSnapshot: snap(1, 's') },
        { status: 'brainstorming', at: 2, by: { kind: 'agent', sessionId: 's' }, tokenSnapshot: snap(3, 's') },
      ],
    })
    expect(accumulateStageDelta(r, 'draft', snap(3, 's'))).toBe(true)
    expect(accumulateStageDelta(r, 'brainstorming', snap(7, 's'))).toBe(true)
    expect(Object.keys(r.tokenUsage!.byStage).sort()).toEqual(['brainstorming', 'draft'])
    expect(r.tokenUsage!.byStage.draft).toEqual(B(2))
    expect(r.tokenUsage!.byStage.brainstorming).toEqual(B(4))
    expect(r.tokenUsage!.totals).toEqual(B(6))
  })

  it('会话不一致 → 不做减法（宁可无快照，也不把别的会话算进来）', () => {
    const r = req({
      statusHistory: [{ status: 'draft', at: 1, by: { kind: 'agent', sessionId: 'other' }, tokenSnapshot: snap(1, 'other') }],
    })
    expect(accumulateStageDelta(r, 'draft', snap(9, 'session-w-001'))).toBe(false)
    expect(r.tokenUsage).toBeUndefined()
  })
})

describe('REQ-a33899 t3 · 写时快照：任务执行', () => {
  it('开工写 start；完工（canceled）写 end 与 delta', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'todo' })] })
    h.session.tokenSnapshot = snap(2)
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'in_progress' }, EXEC)
    let tk = h.repo.ledger.tasks[0]!
    expect(tk.executions[0]!.tokenUsage!.start!.totals).toEqual(B(2))
    expect(tk.executions[0]!.tokenUsage!.delta).toBeUndefined()
    h.session.tokenSnapshot = snap(5)
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'integrating' }, EXEC)
    tk = h.repo.ledger.tasks[0]!
    expect(tk.executions[0]!.tokenUsage!.end!.totals).toEqual(B(5))
    expect(tk.executions[0]!.tokenUsage!.delta).toEqual(B(3))
  })

  it('中途汇报刷新 running 执行的 end/delta（进度检查点）', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'todo' })] })
    h.session.tokenSnapshot = snap(1)
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'in_progress' }, EXEC)
    h.session.tokenSnapshot = snap(4)
    await executeReportTask(h.deps, { task_id: 't-000001', summary: '做到一半' }, EXEC)
    const e = h.repo.ledger.tasks[0]!.executions[0]!
    expect(e.outcome).toBe('running')
    expect(e.tokenUsage!.end!.totals).toEqual(B(4))
    expect(e.tokenUsage!.delta).toEqual(B(3))
  })

  it('快照不可得 → start/end 记 unavailable，delta 不产出（禁止编造）', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'todo' })] })
    h.session.tokenSnapshot = unavailable()
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'in_progress' }, EXEC)
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'integrating' }, EXEC)
    const e = h.repo.ledger.tasks[0]!.executions[0]!
    expect(e.tokenUsage!.start!.source).toBe('unavailable')
    expect(e.tokenUsage!.end!.source).toBe('unavailable')
    expect(e.tokenUsage!.delta).toBeUndefined()
  })
})

describe('REQ-a33899 t3 · v5 台账可载入（读路径不自动迁移）', () => {
  let dir: string
  let file: string
  beforeEach(() => { dir = mkdtempSync(join(tmpdir(), 'pmboard-v5-')); file = join(dir, 'ledger.json') })
  afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

  it('缺 token 字段的 v5 台账：load 成功、记录完整、文件版本不被就地改写', async () => {
    const v5 = {
      schemaVersion: 5,
      revision: 3,
      requirements: [{
        id: 'REQ-abcdef', title: '旧需求', description: 'd', category: 'feature', status: 'draft', blocked: false,
        comments: [], version: 1, createdAt: 1, updatedAt: 1,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
      }],
      tasks: [],
      triages: [],
    }
    writeFileSync(file, JSON.stringify(v5))
    const repo = new JsonLedgerRepository({ file })
    await repo.load()
    const s = repo.snapshot()
    expect(s.requirements).toHaveLength(1)
    expect(s.requirements[0]!.tokenUsage).toBeUndefined()
    expect(s.migrations ?? []).toEqual([])
    // 读路径不自动迁移：磁盘上的文件仍是 v5（迁移必须由 scripts/migrate-ledger.ts 显式执行）
    expect(JSON.parse(readFileSync(file, 'utf8')).schemaVersion).toBe(5)
  })
})
