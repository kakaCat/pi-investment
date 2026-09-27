/**
 * t11 定向验收（REQ-260927202051-f6df t-05925b / FR-1）：拆分把任务写进队列，台账零新增。
 *
 * 覆盖：
 *  - TC-9.1 `reqboard_decompose` 后 `docs/requirements/<REQ>/queue.json` 生成（真实文件系统）；
 *  - 返回体 `queue_file` 非空（Decompose 返回体契约，另在静态断言里核对字段存在）；
 *  - **台账不新增任务**（v9 台账无 `tasks` 键——本仓 `ReqboardLedger` 类型上已没有该字段）；
 *  - 重复调用幂等：重复 id **不覆盖** + 队列文件 **mtime 不变**；
 *  - 硬验收：两条落库路径（拆分 `Decompose.ts` / 计划批准即落库 `confirm-settle.ts`）
 *    共用**唯一写路径** `landPlanTasks`，且我方写域内无 `ledger.tasks` 残留。
 *
 * 口径（R-013）：队列用真实 `JsonQueueRepository` + `QueueTaskStore` 落在临时目录
 * （md5/mtime 才是真事实）；台账/文档用内存端口。临时目录在用例结束时删除。
 */
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { makeHarness, req } from './application/harness.js'
import { landPlanTasks } from '../src/application/internal/plan-landing.js'
import { JsonQueueRepository, queueRelativePath } from '../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../src/repositories/QueueTaskStore.js'

const REQ_ID = 'REQ-000001'
const WINDOW = 'session-w-001'

const draft = [
  { key: 't1', title: '任务一', description: 'd1', phase: 'implement', side: 'backend', acceptance: '跑命令 A 看到 X', implementation: '改 a.ts', context: '', dependsOn: [] },
  { key: 't2', title: '任务二', description: 'd2', phase: 'test', side: 'backend', acceptance: '跑命令 B 看到 Y', implementation: '改 b.ts', context: '', dependsOn: ['t1'] },
]

const roots: string[] = []
afterEach(() => {
  for (const r of roots.splice(0)) rmSync(r, { recursive: true, force: true })
})

function realQueue() {
  const root = mkdtempSync(join(tmpdir(), 't11-queue-'))
  roots.push(root)
  const repo = new JsonQueueRepository({ workspaceRoot: root })
  const store = new QueueTaskStore({ repo, now: () => 1_000_000 })
  return { root, repo, store, file: join(root, queueRelativePath(REQ_ID)) }
}

function harnessWithRealQueue() {
  const q = realQueue()
  const h = makeHarness({ requirements: [req({ status: 'decomposing', sourceSessionId: WINDOW })] })
  h.deps.taskStore = q.store
  return { ...q, h }
}

describe('t11 · TC-9.1 拆分落队列（真实文件）', () => {
  it('landPlanTasks 生成 queue.json，且台账不新增任务', async () => {
    const { h, file, store } = harnessWithRealQueue()
    const landed = await landPlanTasks(h.deps, {
      requirementId: REQ_ID, windowKey: WINDOW, nowTs: 1_000_000,
      draft, refsByKey: new Map(),
    })

    // ① 队列文件真实生成且可解析
    expect(existsSync(file)).toBe(true)
    const parsed = JSON.parse(readFileSync(file, 'utf8')) as { requirement_id: string; tasks: { id: string }[]; ready: string[] }
    expect(parsed.requirement_id).toBe(REQ_ID)
    expect(parsed.tasks).toHaveLength(2)
    // DAG 派生视图：t2 依赖 t1 → 仅 t1 ready
    expect(parsed.ready).toEqual([landed.created[0]?.id])
    expect(landed.createdIds).toHaveLength(2)

    // ② 台账**没有** tasks 键（v9）；需求侧只多了评论/产物，不长任务
    expect(Object.prototype.hasOwnProperty.call(h.repo.ledger, 'tasks')).toBe(false)
    expect(await store.listByRequirement(REQ_ID)).toHaveLength(2)
    expect(h.repo.ledger.requirements[0]?.comments.some(c => c.body.includes('[拆分]'))).toBe(true)
  })

  it('重复调用幂等：重复 id 不覆盖 + 文件 mtime 不变', async () => {
    const { h, file, store } = harnessWithRealQueue()
    await landPlanTasks(h.deps, {
      requirementId: REQ_ID, windowKey: WINDOW, nowTs: 1_000_000,
      draft, refsByKey: new Map(),
    })
    const before = await store.listByRequirement(REQ_ID)
    const mtimeBefore = statSync(file).mtimeMs

    // 把队列里第一张卡改名（模拟"已开工/已汇报"后的真实内容）
    await store.mutate(REQ_ID, (tasks) => {
      const t = tasks.find(x => x.id === before[0]?.id)
      if (t !== undefined) t.title = '已被执行改过的标题'
      return tasks
    })
    const mutated = (await store.listByRequirement(REQ_ID))[0]
    const mtimeAfterMutate = statSync(file).mtimeMs

    // 再用**原始 id** 重复写（幂等断言）
    const again = await store.createMany(REQ_ID, before)
    expect(again).toEqual([])
    expect(statSync(file).mtimeMs).toBe(mtimeAfterMutate)
    expect(statSync(file).mtimeMs).not.toBe(mtimeBefore) // 前一步 mutate 确实写过（对照组）
    // 重复 id 不覆盖：改名仍在
    expect((await store.listByRequirement(REQ_ID))[0]?.title).toBe(mutated?.title)
    expect((await store.listByRequirement(REQ_ID))).toHaveLength(2)
  })
})

describe('t11 · 两条落库路径共用唯一写路径 + 台账零任务', () => {
  it('Decompose.ts 与 confirm-settle.ts 都经 landPlanTasks 落库；写域内无 ledger.tasks 残留', () => {
    const srcRoot = 'src/application'
    const decompose = readFileSync(join(srcRoot, 'use-cases/Decompose.ts'), 'utf8')
    const confirmSettle = readFileSync(join(srcRoot, 'internal/confirm-settle.ts'), 'utf8')
    const landing = readFileSync(join(srcRoot, 'internal/plan-landing.ts'), 'utf8')

    // ① 两条路径都委托唯一实现
    expect(decompose).toContain('landPlanTasks(')
    expect(confirmSettle).toContain('landPlanTasks(')
    // ② 唯一写路径用 createMany 落队列（台账侧只写 requirements）
    expect(landing).toContain('store.createMany(')
    expect(landing).not.toContain('ledger.tasks')
    // ③ 两个调用方自己也不写任务到台账
    expect(decompose).not.toContain('ledger.tasks')
    expect(confirmSettle).not.toContain('ledger.tasks')
    // ④ 返回体契约：Decompose 给出非空 queue_file
    expect(decompose).toContain('queue_file')
  })
})
