/**
 * t9 读方改造 C 的定向验收（REQ-260927202051-f6df t-860900 / FR-8）。
 *
 * 覆盖三条卡内验收：
 *  - TC-8.10 用例层父子树结构一致（TaskTree 改经 TaskStore 后逐字段不变）；
 *  - TC-8.8 rollup 推导一致（applyTaskRollup 新签名 `(ledger, tasks, ctx, onlyReqId?)` 仍能推进）；
 *  - TC-8.11 顺序契约（**打点证据**）：MoveTask 中 `taskStore.mutate` 必须先于 `repo.mutate`。
 *
 * 口径（R-013 / Lead 冻结令）：公共 `tests/application/harness.ts` 归 queue-core，
 * 本文件**只依赖它的 `makeHarness` / `req` / `task` 工厂**，任务一律用真实
 * `JsonQueueRepository` + `QueueTaskStore` 落临时目录——不依赖任何公共内存夹具的内部实现。
 */
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { makeHarness, req, task } from './application/harness.js'
import { executeTaskTree } from '../src/application/use-cases/TaskTree.js'
import { executeMoveTask } from '../src/application/use-cases/MoveTask.js'
import { applyTaskRollup } from '../src/application/internal/rollup.js'
import { JsonQueueRepository } from '../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../src/repositories/QueueTaskStore.js'
import type { ReqboardLedger } from '../src/shared/protocol.js'

const REQ_ID = 'REQ-000001'
const WINDOW = 'session-w-001'

const roots: string[] = []
afterEach(() => { for (const r of roots.splice(0)) rmSync(r, { recursive: true, force: true }) })

function realQueue() {
  const root = mkdtempSync(join(tmpdir(), 't9-queue-'))
  roots.push(root)
  return new QueueTaskStore({ repo: new JsonQueueRepository({ workspaceRoot: root }), now: () => 1_000_000 })
}

describe('t9 · TC-8.10 用例层父子树改经 TaskStore', () => {
  it('TaskTree 的父子结构与队列内 parentId 一致', async () => {
    const store = realQueue()
    const h = makeHarness({ requirements: [req({ status: 'implementing', sourceSessionId: WINDOW, createdAt: 1 })] })
    h.deps.taskStore = store
    await store.createMany(REQ_ID, [
      task({ id: 't-parent', status: 'in_progress', createdAt: 1 }),
      task({ id: 't-sub-1', parentId: 't-parent', stageKind: 'dev', status: 'done', dependsOn: [], createdAt: 1 }),
      task({ id: 't-sub-2', parentId: 't-parent', stageKind: 'test', status: 'todo', dependsOn: ['t-sub-1'], createdAt: 1 }),
    ])

    const res = await executeTaskTree(h.deps, { requirement_id: REQ_ID, parent_id: 't-parent' }, {}) as {
      success: boolean
      parents: { parent: { id: string }; subtasks: { id: string }[] }[]
    }

    expect(res.success).toBe(true)
    expect(res.parents).toHaveLength(1)
    expect(res.parents[0]?.parent.id).toBe('t-parent')
    // 链序：subtasks 按 dependsOn 排（TaskTree 既有语义，未因换数据源而变）
    expect(res.parents[0]?.subtasks.map(s => s.id)).toEqual(['t-sub-1', 't-sub-2'])
  })

  it('队列无该需求时 TaskTree 报 TASK_NOT_FOUND（不静默返回空树）', async () => {
    const store = realQueue()
    const h = makeHarness({ requirements: [req({ status: 'implementing', sourceSessionId: WINDOW })] })
    h.deps.taskStore = store
    const res = await executeTaskTree(h.deps, { requirement_id: REQ_ID, parent_id: 't-none' }, {}) as { success: boolean; error?: string }
    expect(res.success).toBe(false)
    expect(res.error ?? '').toContain('REQBOARD_TASK_NOT_FOUND')
  })
})

describe('t9 · TC-8.8 rollup 推导与队列任务一致', () => {
  it('applyTaskRollup(ledger, tasks, ctx)：全部任务 done → 需求 implementing 推进到 accepting', () => {
    const ledger: ReqboardLedger = {
      schemaVersion: 9,
      revision: 1,
      requirements: [req({ status: 'implementing', sourceSessionId: WINDOW })],
      triages: [],
    }
    const advanced = applyTaskRollup(
      ledger,
      [task({ id: 't-1', status: 'done' }), task({ id: 't-2', status: 'done' })],
      { now: 2_000_000, commentId: () => 'c-1' },
      REQ_ID,
    )
    expect(advanced).toHaveLength(1)
    expect(advanced[0]?.status).toBe('accepting')
  })

  it('有未完成任务 → 不推进（推导以队列任务为唯一输入）', () => {
    const ledger: ReqboardLedger = {
      schemaVersion: 9,
      revision: 1,
      requirements: [req({ status: 'implementing', sourceSessionId: WINDOW })],
      triages: [],
    }
    const advanced = applyTaskRollup(
      ledger,
      [task({ id: 't-1', status: 'done' }), task({ id: 't-2', status: 'todo' })],
      { now: 2_000_000, commentId: () => 'c-1' },
      REQ_ID,
    )
    expect(advanced).toHaveLength(0)
    expect(ledger.requirements[0]?.status).toBe('implementing')
  })
})

describe('t9/t12 · TC-8.11 顺序契约（打点证据）', () => {
  it('MoveTask：taskStore.mutate 先于 repo.mutate', async () => {
    const store = realQueue()
    const h = makeHarness({ requirements: [req({ status: 'implementing', sourceSessionId: WINDOW, createdAt: 1 })] })
    h.deps.taskStore = store
    await store.createMany(REQ_ID, [task({ id: 't-1', status: 'todo', createdAt: 1 })])

    const log: string[] = []
    const originalStoreMutate = store.mutate.bind(store)
    store.mutate = async (reqId: string, fn: Parameters<typeof originalStoreMutate>[1]) => {
      log.push('taskStore.mutate')
      return originalStoreMutate(reqId, fn)
    }
    const originalRepoMutate = h.repo.mutate.bind(h.repo)
    h.repo.mutate = async (reason: string, fn: Parameters<typeof originalRepoMutate>[1]) => {
      log.push('repo.mutate')
      return originalRepoMutate(reason, fn)
    }

    await executeMoveTask(h.deps, { task_id: 't-1', to: 'in_progress' }, {})

    // 打点 = 运行期真实调用次序（不是静态 grep、不是口头声明）
    expect(log).toEqual(['taskStore.mutate', 'repo.mutate'])
    expect((await store.get('t-1'))?.status).toBe('in_progress')
  })

  it('MoveTask：任务状态只落队列，台账无 tasks 键（v9）', async () => {
    const store = realQueue()
    const h = makeHarness({ requirements: [req({ status: 'implementing', sourceSessionId: WINDOW, createdAt: 1 })] })
    h.deps.taskStore = store
    await store.createMany(REQ_ID, [task({ id: 't-1', status: 'todo', createdAt: 1 })])
    await executeMoveTask(h.deps, { task_id: 't-1', to: 'in_progress' }, {})
    expect(Object.prototype.hasOwnProperty.call(h.repo.ledger, 'tasks')).toBe(false)
  })
})
