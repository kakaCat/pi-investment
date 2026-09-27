/**
 * t12 定向验收（REQ-260927202051-f6df t-fa3e16 / FR-2, FR-3）：
 * 执行读队列 + 状态流转解锁下游 + 顺序契约打点 + task_run 只读。
 *
 * 覆盖：
 *  - TC-9.2 `task_run` 日志含 `Queue ready tasks:`，父卡字段取自队列；
 *  - TC-9.3 `task_move(to=done)` 后队列 `ready` 出现下游；
 *  - TC-8.11 顺序契约：**打点断言** `taskStore.mutate` 先于 `repo.mutate`（真实 QueueTaskStore）；
 *  - TC-9.4 队列缺失时 `task_move` 不崩（干净错误码，非未捕获异常）；
 *  - `task_run`（投递式）前后队列 **md5 相同**（只读）。
 *
 * 口径（R-013）：队列用真实 `JsonQueueRepository` + `QueueTaskStore` 落临时目录——
 * md5/mtime 只有真实文件才是事实；台账/文档用内存端口。
 */
import { createHash } from 'node:crypto'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { makeHarness, req, task } from './application/harness.js'
import { executeMoveTask } from '../src/application/use-cases/MoveTask.js'
import { executeSubtask } from '../src/application/use-cases/ExecuteTask.js'
import { advanceRequirement } from '../src/application/use-cases/AdvanceChain.js'
import { JsonQueueRepository, queueRelativePath } from '../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../src/repositories/QueueTaskStore.js'
import type { JobsPort } from '../src/application/ports.js'
import type { TaskRecord } from '../src/shared/protocol.js'

const REQ_ID = 'REQ-000001'
const WINDOW = 'session-w-001'

const roots: string[] = []
afterEach(() => { for (const r of roots.splice(0)) rmSync(r, { recursive: true, force: true }) })

function realQueue() {
  const root = mkdtempSync(join(tmpdir(), 't12-queue-'))
  roots.push(root)
  const repo = new JsonQueueRepository({ workspaceRoot: root })
  const store = new QueueTaskStore({ repo, now: () => 1_000_000 })
  return { root, repo, store, file: join(root, queueRelativePath(REQ_ID)) }
}

const md5 = (p: string): string => createHash('md5').update(readFileSync(p)).digest('hex')

/** 子卡可过凭证门的夹具（run.ok + lastReport + 真实文件 mtime ≥ 链出身）。 */
function doneReadySubtask(over: Partial<TaskRecord>): TaskRecord {
  return task({
    status: 'in_progress',
    parentId: 't-parent',
    stageKind: 'dev',
    createdAt: 1,
    claimedAt: 1,
    lastRun: { at: 2, ok: true, stopReason: 'completed', valueNonEmpty: true },
    lastReport: { at: 2, reportIndex: 1, filesChanged: ['docs/req/a.md'], completed: ['做了 a'] },
    ...over,
  })
}

describe('t12 · TC-9.3 task_move(to=done) 解锁下游 ready', () => {
  it('子卡 from in_progress → done 后，队列 ready 出现依赖它的下游', async () => {
    const q = realQueue()
    const h = makeHarness({ requirements: [req({ status: 'implementing', sourceSessionId: WINDOW, createdAt: 1 })] })
    h.docs.put('docs/req/a.md')
    h.deps.taskStore = q.store
    await q.store.createMany(REQ_ID, [
      task({ id: 't-parent', status: 'in_progress', createdAt: 1, dependsOn: [] }),
      doneReadySubtask({ id: 't-s1', dependsOn: [] }),
      task({ id: 't-s2', parentId: 't-parent', stageKind: 'test', status: 'todo', dependsOn: ['t-s1'], createdAt: 1 }),
    ])
    // 前置：s2 被 s1 挡着，ready 不含 s2
    expect((await q.store.readQueue(REQ_ID))?.ready).not.toContain('t-s2')

    const res = await executeMoveTask(h.deps, { task_id: 't-s1', to: 'done' }, {}) as { status?: string }
    expect(res.status).toBe('done')

    const after = await q.store.readQueue(REQ_ID)
    expect(after?.tasks.find(t => t.id === 't-s1')?.status).toBe('done')
    expect(after?.ready).toContain('t-s2')
  })
})

describe('t12 · TC-9.2 执行读队列并打印 ready', () => {
  it('executeSubtask 日志含 "Queue ready tasks:" 且 log 列出队列就绪卡', async () => {
    const q = realQueue()
    const h = makeHarness({ requirements: [req({ status: 'implementing', sourceSessionId: WINDOW, createdAt: 1 })] })
    h.deps.taskStore = q.store
    await q.store.createMany(REQ_ID, [
      task({ id: 't-parent', status: 'in_progress' }),
      task({ id: 't-s1', parentId: 't-parent', stageKind: 'dev', status: 'todo', dependsOn: [] }),
      task({ id: 't-s2', parentId: 't-parent', stageKind: 'test', status: 'todo', dependsOn: ['t-s1'] }),
    ])
    const spy = vi.spyOn(console, 'log').mockImplementation(() => {})
    try {
      const r = await executeSubtask(h.deps, { subtaskId: 't-s1', windowKey: WINDOW })
      const logged = spy.mock.calls.map(c => String(c[0])).join('\n')
      expect(logged).toContain('Queue ready tasks:')
      expect(logged).toContain('t-s1')
      expect(logged).not.toContain('t-s2') // s2 依赖 s1 → 尚不就绪（ready 口径取自队列依赖）
      // 父卡取自队列：无引擎时响亮失败（不是"找不到父卡"这类数据缺失）
      expect(r.ok).toBe(false)
      expect(r.parentId).toBe('t-parent')
    } finally {
      spy.mockRestore()
    }
  })
})

describe('t12 · TC-8.11 顺序契约（真实 QueueTaskStore 打点）', () => {
  it('MoveTask 调用次序 = taskStore.mutate → repo.mutate', async () => {
    const q = realQueue()
    const h = makeHarness({ requirements: [req({ status: 'implementing', sourceSessionId: WINDOW, createdAt: 1 })] })
    h.deps.taskStore = q.store
    await q.store.createMany(REQ_ID, [task({ id: 't-1', status: 'todo', createdAt: 1 })])

    const log: string[] = []
    const originalMutate = q.store.mutate.bind(q.store)
    q.store.mutate = async (reqId: string, fn: Parameters<typeof originalMutate>[1]) => {
      log.push('taskStore.mutate')
      return originalMutate(reqId, fn)
    }
    const originalRepo = h.repo.mutate.bind(h.repo)
    h.repo.mutate = async (reason: string, fn: Parameters<typeof originalRepo>[1]) => {
      log.push('repo.mutate')
      return originalRepo(reason, fn)
    }

    await executeMoveTask(h.deps, { task_id: 't-1', to: 'in_progress' }, {})
    expect(log).toEqual(['taskStore.mutate', 'repo.mutate'])
  })
})

describe('t12 · TC-9.4 队列缺失容错', () => {
  it('无 queue.json 时 task_move 干净报 TASK_NOT_FOUND（不崩、不隐式建档）', async () => {
    const q = realQueue()
    const h = makeHarness({ requirements: [req({ status: 'implementing', sourceSessionId: WINDOW })] })
    h.deps.taskStore = q.store
    expect(existsSync(q.file)).toBe(false)

    await expect(
      executeMoveTask(h.deps, { task_id: 't-ghost', to: 'in_progress' }, {}),
    ).rejects.toMatchObject({ code: 'REQBOARD_TASK_NOT_FOUND' })
    // 写操作不隐式建档：文件仍不存在
    expect(existsSync(q.file)).toBe(false)
  })
})

describe('t12 · task_run（投递式）前后队列 md5 相同（只读）', () => {
  it('advanceRequirement 仅投递、不改任务：queue.json md5 不变', async () => {
    const q = realQueue()
    const h = makeHarness({
      requirements: [req({
        status: 'implementing', sourceSessionId: WINDOW, createdAt: 1, autoRun: true,
        advance: {} as never,
      })],
    })
    h.deps.taskStore = q.store
    await q.store.createMany(REQ_ID, [
      task({ id: 't-parent', status: 'todo', createdAt: 1 }),
      task({ id: 't-s1', parentId: 't-parent', stageKind: 'dev', status: 'todo', createdAt: 1 }),
    ])

    // 注入"只记录不执行"的后台任务端口：投递式路径（真跑在 jobs 里，不在本调用内）
    const started: string[] = []
    h.deps.jobs = {
      available: () => true,
      start: async (spec) => { started.push(spec.kind); return 'job-1' },
      get: async () => null,
    } as JobsPort

    const before = md5(q.file)
    const out = await advanceRequirement(h.deps, REQ_ID)
    const after = md5(q.file)

    expect(out.dispatched).toBe(true)
    expect(started).toEqual(['reqboard'])
    expect(after).toBe(before) // 只读：投递不改队列
  })
})
