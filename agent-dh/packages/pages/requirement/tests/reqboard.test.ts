/**
 * Reqboard M1 单测：状态机、闸门、DAG 校验、Store 并发与持久化。
 * 运行：cd agent-dh && npx vitest run packages/pages/requirement/tests/
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import {
  assertReqTransition,
  assertTaskTransition,
  assertDagAcyclic,
  readyTasks,
  newRequirementId,
  newTaskId,
  emptyLedger,
  type RequirementRecord,
  type TaskRecord,
} from '../src/shared/protocol.js'

/** vitest toThrow 检查 message 而非 code；用 helper 断言 code。 */
function throwsCode(fn: () => void, expectedCode: string): void {
  try { fn(); expect.fail('期望抛错但未抛') } catch (e: any) { expect(e.code).toBe(expectedCode) }
}
import { ReqboardStore } from '../src/host/store.js'

// ---------------------------------------------------------------------------
// Requirement 状态机
// ---------------------------------------------------------------------------

describe('Requirement state machine', () => {
  it('allows legal transitions', () => {
    expect(() => assertReqTransition('draft', 'reviewing', 'human')).not.toThrow()
    expect(() => assertReqTransition('reviewing', 'decomposing', 'human')).not.toThrow()
    expect(() => assertReqTransition('decomposing', 'implementing', 'human')).not.toThrow()
    expect(() => assertReqTransition('implementing', 'accepting', 'system')).not.toThrow()
    expect(() => assertReqTransition('accepting', 'done', 'human')).not.toThrow()
    expect(() => assertReqTransition('done', 'archived', 'human')).not.toThrow()
    expect(() => assertReqTransition('canceled', 'archived', 'human')).not.toThrow()
  })

  it('rejects illegal transitions', () => {
    throwsCode(() => assertReqTransition('draft', 'done', 'human'), 'invalid_transition')
    throwsCode(() => assertReqTransition('done', 'draft', 'human'), 'invalid_transition')
    throwsCode(() => assertReqTransition('archived', 'draft', 'human'), 'invalid_transition')
  })

  it('human gate: agent cannot confirm review/decompose/accept/archive', () => {
    throwsCode(() => assertReqTransition('reviewing', 'decomposing', 'agent'), 'human_gate')
    throwsCode(() => assertReqTransition('decomposing', 'implementing', 'agent'), 'human_gate')
    throwsCode(() => assertReqTransition('accepting', 'done', 'agent'), 'human_gate')
    throwsCode(() => assertReqTransition('done', 'archived', 'agent'), 'human_gate')
  })

  it('system gate: system only allowed implementing→accepting rollup', () => {
    expect(() => assertReqTransition('implementing', 'accepting', 'system')).not.toThrow()
    throwsCode(() => assertReqTransition('draft', 'reviewing', 'system'), 'system_gate')
    throwsCode(() => assertReqTransition('reviewing', 'decomposing', 'system'), 'human_gate')
  })
})

// ---------------------------------------------------------------------------
// Task 状态机
// ---------------------------------------------------------------------------

describe('Task state machine', () => {
  it('allows legal transitions', () => {
    expect(() => assertTaskTransition('todo', 'in_progress', 'human')).not.toThrow()
    expect(() => assertTaskTransition('in_progress', 'integrating', 'human')).not.toThrow()
    expect(() => assertTaskTransition('in_progress', 'testing', 'human')).not.toThrow() // skip integration
    expect(() => assertTaskTransition('integrating', 'testing', 'human')).not.toThrow()
    expect(() => assertTaskTransition('testing', 'in_review', 'human')).not.toThrow()
    expect(() => assertTaskTransition('in_review', 'done', 'human')).not.toThrow()
    expect(() => assertTaskTransition('canceled', 'todo', 'human')).not.toThrow()
  })

  it('rejects illegal transitions', () => {
    throwsCode(() => assertTaskTransition('todo', 'done', 'human'), 'invalid_transition')
    throwsCode(() => assertTaskTransition('done', 'todo', 'human'), 'invalid_transition')
  })

  it('human gate: done only by human', () => {
    throwsCode(() => assertTaskTransition('in_review', 'done', 'agent'), 'human_gate')
    throwsCode(() => assertTaskTransition('in_review', 'done', 'system'), 'human_gate')
    expect(() => assertTaskTransition('in_review', 'done', 'human')).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// DAG 校验
// ---------------------------------------------------------------------------

function makeTasks(reqId: string, defs: Array<{ id: string; deps: string[] }>): TaskRecord[] {
  return defs.map(d => ({
    id: d.id, requirementId: reqId, title: d.id, description: '', phase: 'implement' as const,
    side: 'backend' as const, dependsOn: d.deps, scope: { apis: [], tables: [], files: [] },
    acceptance: '', context: '', status: 'todo', blocked: false, executions: [], comments: [],
    version: 1, createdAt: 0, updatedAt: 0, createdBy: { kind: 'human' as const }, updatedBy: { kind: 'human' as const },
  }))
}

describe('DAG validation', () => {
  const reqId = 'REQ-000001'

  it('passes on acyclic DAG', () => {
    const tasks = makeTasks(reqId, [
      { id: 't-01', deps: [] },
      { id: 't-02', deps: ['t-01'] },
      { id: 't-03', deps: ['t-01'] },
      { id: 't-04', deps: ['t-02', 't-03'] },
    ])
    expect(() => assertDagAcyclic(tasks, reqId)).not.toThrow()
  })

  it('detects self-dependency', () => {
    const tasks = makeTasks(reqId, [{ id: 't-01', deps: ['t-01'] }])
    throwsCode(() => assertDagAcyclic(tasks, reqId), 'invalid_dag')
  })

  it('detects missing dependency', () => {
    const tasks = makeTasks(reqId, [{ id: 't-01', deps: ['t-99'] }])
    throwsCode(() => assertDagAcyclic(tasks, reqId), 'invalid_dag')
  })

  it('detects indirect cycle', () => {
    const tasks = makeTasks(reqId, [
      { id: 't-01', deps: ['t-03'] },
      { id: 't-02', deps: ['t-01'] },
      { id: 't-03', deps: ['t-02'] },
    ])
    throwsCode(() => assertDagAcyclic(tasks, reqId), 'invalid_dag')
  })

  it('readyTasks selects todo with all deps done', () => {
    const tasks: TaskRecord[] = [
      ...makeTasks(reqId, [
        { id: 't-01', deps: [] },
        { id: 't-02', deps: ['t-01'] },
        { id: 't-03', deps: ['t-01'] },
        { id: 't-04', deps: ['t-02', 't-03'] },
      ]),
    ]
    tasks[0].status = 'done'
    const ready = readyTasks(tasks, reqId)
    expect(ready.map(t => t.id)).toEqual(['t-02', 't-03'])
  })
})

// ---------------------------------------------------------------------------
// Store 持久化与并发
// ---------------------------------------------------------------------------

describe('ReqboardStore', () => {
  let tmpDir: string
  let store: ReqboardStore

  beforeEach(() => {
    tmpDir = mkdtempSync(join(tmpdir(), 'reqboard-'))
    store = new ReqboardStore({ file: join(tmpDir, 'reqboard.json') })
  })

  afterEach(() => {
    try { rmSync(tmpDir, { recursive: true, force: true }) } catch { /* ignore */ }
  })

  it('persists requirement creation and reloads', async () => {
    const r = await store.mutate('requirement-created', (ledger) => {
      ledger.requirements.push({
        id: 'REQ-000001', title: '测试需求', description: '', status: 'draft', blocked: false,
        comments: [], version: 1, createdAt: 0, updatedAt: 0,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
      })
      return { requirements: ledger.requirements }
    })
    expect(r.changed.requirements[0].title).toBe('测试需求')
    expect(r.ledger.revision).toBe(1)

    // 重新加载新 store 实例（显式 load，snapshot 不自动触发 load）
    const store2 = new ReqboardStore({ file: join(tmpDir, 'reqboard.json') })
    await store2.load()
    const snap = store2.snapshot()
    expect(snap.requirements.length).toBe(1)
    expect(snap.revision).toBe(1)
  })

  it('serializes concurrent mutations (revision monotonic)', async () => {
    const promises: Promise<unknown>[] = []
    for (let i = 0; i < 10; i++) {
      promises.push(store.mutate('requirement-created', (ledger) => {
        ledger.requirements.push({
          id: `REQ-${String(i).padStart(6, '0')}`, title: `R${i}`, description: '', status: 'draft', blocked: false,
          comments: [], version: 1, createdAt: 0, updatedAt: 0,
          createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
        })
        return { requirements: ledger.requirements }
      }))
    }
    await Promise.all(promises)
    const snap = store.snapshot()
    expect(snap.revision).toBe(10)
    expect(snap.requirements.length).toBe(10)
  })

  it('snapshot is frozen (mutating throws)', async () => {
    await store.mutate('requirement-created', (ledger) => {
      ledger.requirements.push({
        id: 'REQ-000001', title: 'T', description: '', status: 'draft', blocked: false,
        comments: [], version: 1, createdAt: 0, updatedAt: 0,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
      })
      return { requirements: ledger.requirements }
    })
    const snap = store.snapshot()
    expect(() => { (snap as any).revision = 999 }).toThrow()
  })

  it('corrupt file quarantined and starts fresh', async () => {
    const file = join(tmpDir, 'reqboard.json')
    const fs = await import('node:fs/promises')
    await fs.writeFile(file, 'not-json-at-all')
    const store2 = new ReqboardStore({ file })
    await store2.load()
    expect(store2.snapshot().requirements.length).toBe(0)
    const files = (await fs.readdir(tmpDir)).filter(f => f.includes('corrupt'))
    expect(files.length).toBeGreaterThanOrEqual(1)
  })

  it('notifies subscribers on mutation', async () => {
    const events: Array<{ kind: string; revision: number }> = []
    store.subscribe((ch) => events.push({ kind: ch.kind, revision: ch.revision }))
    await store.mutate('requirement-created', (ledger) => {
      ledger.requirements.push({
        id: 'REQ-000001', title: 'Sub', description: '', status: 'draft', blocked: false,
        comments: [], version: 1, createdAt: 0, updatedAt: 0,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
      })
      return { requirements: ledger.requirements }
    })
    expect(events.length).toBe(1)
    expect(events[0].kind).toBe('requirement-created')
    expect(events[0].revision).toBe(1)
  })
})
