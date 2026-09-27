/**
 * 写时 token 快照 + 台账版本读兼容测试（REQ-a33899 t3）。
 *
 * REQ-260927202051-f6df task-16 的改造说明（**逐用例判定，非放宽断言**）：
 *
 * 1. **夹具从"台账带 tasks"的世界迁到 v9 世界**：原来 5 个用例通过 `makeHarness` 建台账、
 *    把任务塞进 `ledger.tasks`，再读 `h.repo.ledger.tasks[0]`。v9 起台账**没有** `tasks` 键
 *    （任务唯一存储 = 各需求 `queue.json`），继续那样写会得到 `undefined.filter`。
 *    现在用 `tests/queue/v9-harness.ts`：内存 v9 台账 + **真实 QueueTaskStore**（真实
 *    `JsonQueueRepository` 落临时目录），任务经 `taskStore.createMany` 真实入队，
 *    断言一律从队列读。**端口是真的，不是 mock**。
 * 2. **v5 台账被拒是既定契约，不是 bug**：v9 起 `JsonLedgerRepository.load` 对
 *    `schemaVersion < 9`（或带非空 tasks）的台账抛 `LEDGER_REQUIRES_MIGRATION`
 *    （design/interfaces.md I-6「读兼容（硬约束）」/ t-2417da 验收项③）。
 *    原用例名"v5 台账可载入（读路径不自动迁移）"的语义**已被本需求取代**，故改写为
 *    "被迁移门拒绝，且不就地改写、记录一条不丢"——**放宽迁移门 = 回退 t6**，不在此列。
 *    顺带保留原用例的另一半意图（缺 token 字段的台账可载入、文件不被就地改写），
 *    把它移植到 v9 台账上（新用例 3）。
 * 3. 纯函数用例（`accumulateStageDelta`）不依赖台账结构，**原样保留、零改动**。
 */

import { describe, it, expect, afterEach } from 'vitest'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { makeV9Harness, type V9Harness } from './queue/v9-harness.js'
import { req, task } from './application/harness.js'
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

let live: V9Harness | undefined
/** 建 v9 夹具并登记以便 afterEach 清理临时目录。 */
async function harness(seed: Parameters<typeof makeV9Harness>[0] = {}): Promise<V9Harness> {
  const h = await makeV9Harness(seed)
  live = h
  return h
}
afterEach(() => {
  live?.dispose()
  live = undefined
})

/** 从**队列**读任务（v9：任务不再在台账里）。 */
async function taskInQueue(h: V9Harness, taskId: string): Promise<NonNullable<Awaited<ReturnType<V9Harness['taskStore']['get']>>>> {
  const t = await h.taskStore.get(taskId)
  expect(t, `队列里应有任务 ${taskId}`).not.toBeUndefined()
  return t!
}

describe('REQ-a33899 t3 · 写时快照：需求节点', () => {
  it('推进后新事件带 tokenSnapshot，并结算离开节点的差值（同会话）', async () => {
    const draft: StatusEvent = { status: 'draft', at: 1, by: { kind: 'agent', sessionId: 'session-w-001' }, tokenSnapshot: snap(1) }
    const h = await harness({ requirements: [req({ status: 'draft', statusHistory: [draft] })] })
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
    const h = await harness({ requirements: [req({ status: 'draft', statusHistory: [draft] })] })
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

describe('REQ-a33899 t3 · 写时快照：任务执行（断言源 = 队列，不再是台账 tasks）', () => {
  it('开工写 start；完工（canceled）写 end 与 delta', async () => {
    const h = await harness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'todo' })] })
    h.session.tokenSnapshot = snap(2)
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'in_progress' }, EXEC)
    let tk = await taskInQueue(h, 't-000001')
    expect(tk.executions[0]!.tokenUsage!.start!.totals).toEqual(B(2))
    expect(tk.executions[0]!.tokenUsage!.delta).toBeUndefined()
    h.session.tokenSnapshot = snap(5)
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'integrating' }, EXEC)
    tk = await taskInQueue(h, 't-000001')
    expect(tk.executions[0]!.tokenUsage!.end!.totals).toEqual(B(5))
    expect(tk.executions[0]!.tokenUsage!.delta).toEqual(B(3))
  })

  it('中途汇报刷新 running 执行的 end/delta（进度检查点）', async () => {
    const h = await harness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'todo' })] })
    h.session.tokenSnapshot = snap(1)
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'in_progress' }, EXEC)
    h.session.tokenSnapshot = snap(4)
    await executeReportTask(h.deps, { task_id: 't-000001', summary: '做到一半' }, EXEC)
    const e = (await taskInQueue(h, 't-000001')).executions[0]!
    expect(e.outcome).toBe('running')
    expect(e.tokenUsage!.end!.totals).toEqual(B(4))
    expect(e.tokenUsage!.delta).toEqual(B(3))
  })

  it('快照不可得 → start/end 记 unavailable，delta 不产出（禁止编造）', async () => {
    const h = await harness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'todo' })] })
    h.session.tokenSnapshot = unavailable()
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'in_progress' }, EXEC)
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'integrating' }, EXEC)
    const e = (await taskInQueue(h, 't-000001')).executions[0]!
    expect(e.tokenUsage!.start!.source).toBe('unavailable')
    expect(e.tokenUsage!.end!.source).toBe('unavailable')
    expect(e.tokenUsage!.delta).toBeUndefined()
  })
})

describe('REQ-a33899 t3 · 台账版本读兼容（REQ-260927202051-f6df t6 起：v9 之前的台账被拒）', () => {
  let dir: string
  let file: string

  const openTemp = (): { dir: string; file: string } => {
    dir = mkdtempSync(join(tmpdir(), 'pmboard-ledger-'))
    file = join(dir, 'ledger.json')
    return { dir, file }
  }

  afterEach(() => {
    if (dir !== undefined) rmSync(dir, { recursive: true, force: true })
  })

  it('v5 台账（自报 schemaVersion=5）→ load 抛 LEDGER_REQUIRES_MIGRATION，且**不就地改写**、不隔离', async () => {
    const { file } = openTemp()
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

    await expect(repo.load()).rejects.toMatchObject({ code: 'LEDGER_REQUIRES_MIGRATION' })
    await expect(repo.load()).rejects.toThrow(/migrate-ledger\.ts/)

    // 读路径不自动迁移：文件仍是 v5、需求记录原样、没被隔离改名（迁移必须显式跑脚本）
    expect(existsSync(file)).toBe(true)
    const onDisk = JSON.parse(readFileSync(file, 'utf8')) as Record<string, unknown>
    expect(onDisk.schemaVersion).toBe(5)
    expect(onDisk.revision).toBe(3)
    expect(onDisk.requirements).toHaveLength(1)
    expect(onDisk.tasks).toEqual([])
  })

  it('v8 台账带非空 tasks → 同样被拒，**任务一条不丢地留在磁盘上**（防静默丢弃）', async () => {
    const { dir, file } = openTemp()
    const v8 = {
      schemaVersion: 8,
      revision: 9,
      requirements: [{ id: 'REQ-260927202051-f6df', title: '需求', description: 'd', category: 'feature', status: 'implementing', blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: 1, createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [] }],
      tasks: [
        { id: 't-000001', requirementId: 'REQ-260927202051-f6df', title: '卡一', description: 'd', phase: 'implement', side: 'backend', scope: { apis: [], tables: [], files: [] }, acceptance: 'a', context: '', dependsOn: [], status: 'todo', blocked: false, executions: [], comments: [], version: 1, createdAt: 1, updatedAt: 1, createdBy: { kind: 'agent' }, updatedBy: { kind: 'agent' } },
        { id: 't-000002', requirementId: 'REQ-260927202051-f6df', title: '卡二', description: 'd', phase: 'test', side: 'backend', scope: { apis: [], tables: [], files: [] }, acceptance: 'a', context: '', dependsOn: ['t-000001'], status: 'todo', blocked: false, executions: [], comments: [], version: 1, createdAt: 1, updatedAt: 1, createdBy: { kind: 'agent' }, updatedBy: { kind: 'agent' } },
      ],
      triages: [],
    }
    writeFileSync(file, JSON.stringify(v8))
    const repo = new JsonLedgerRepository({ file })

    await expect(repo.load()).rejects.toMatchObject({ code: 'LEDGER_REQUIRES_MIGRATION' })

    const onDisk = JSON.parse(readFileSync(file, 'utf8')) as { tasks: unknown[] }
    expect(onDisk.tasks).toHaveLength(2) // 绝不静默丢弃
    expect(readFileSync(file, 'utf8')).toContain('t-000002')
    expect(existsSync(join(dir, 'ledger.json.corrupt-1'))).toBe(false)
  })

  it('v9 台账缺 token 字段 → load 成功、记录完整、**文件版本不被就地改写**', async () => {
    const { file } = openTemp()
    const v9 = {
      schemaVersion: 9,
      revision: 3,
      requirements: [{
        id: 'REQ-abcdef', title: '旧需求', description: 'd', category: 'feature', status: 'draft', blocked: false,
        comments: [], version: 1, createdAt: 1, updatedAt: 1,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
      }],
      triages: [],
    }
    writeFileSync(file, JSON.stringify(v9))
    const repo = new JsonLedgerRepository({ file })

    await repo.load()
    const s = repo.snapshot()
    expect(s.requirements).toHaveLength(1)
    expect(s.requirements[0]!.tokenUsage).toBeUndefined() // 缺 token 字段不算损坏
    expect(s.migrations ?? []).toEqual([])
    expect(JSON.parse(readFileSync(file, 'utf8')).schemaVersion).toBe(9)
    expect(JSON.parse(readFileSync(file, 'utf8')).revision).toBe(3)
  })
})
