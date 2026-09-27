/**
 * 公共夹具（`tests/application/harness.ts`）的 v9 契约测试（REQ-260927202051-f6df task-17）。
 *
 * 为什么夹具也要有自己的测试：它是 **31 个用例测试的公共底座**——夹具语义一旦跑偏，
 * 症状是"一大片测试莫名其妙地红/绿"，而根因不在被测代码。本文件把 task-17 定下的
 * 每条夹具契约钉成断言（含 Lead 裁定的两条口径约定）：
 *
 * 1. `makeHarness` **保持同步**，`deps.taskStore` 是**真实 `QueueTaskStore`**（生产实现）；
 * 2. 台账**没有** `tasks` 键；任务经队列（`seed.tasks` → 队列文件，不再塞台账）；
 * 3. **「无队列」= 文件不存在** vs **「空队列」= 文件存在且 tasks 为 `[]`** —— 必须可区分；
 * 4. 失败路径用 `queueExists === false`（比 `readQueue() === undefined` 强：后者把
 *    "不存在"与"存在但校验不过"混为一谈）；
 * 5. `queueRevisionOf` 是**幂等重放判据**（真写盘才 +1；noop 不变）——台账 revision 在任务移出后恒真，不能再用；
 * 6. `setTasks` / `addTasks` / `mutateTask` / `setTaskFields` **async**（走真实写路径）；
 * 7. 任务出口**剥 `layer`**；不合法夹具**响亮抛错**（不留半份脏夹具）。
 */

import { describe, expect, it } from 'vitest'
import { makeHarness, req, task } from './../application/harness.js'
import { QueueTaskStore } from '../../src/repositories/QueueTaskStore.js'

const REQ_ID = 'REQ-000001'
const OTHER = 'REQ-000002'

describe('v9 夹具 · 基本形状', () => {
  it('makeHarness 同步可用；deps.taskStore 是真实的 QueueTaskStore', () => {
    const h = makeHarness({ requirements: [req()] })

    expect(h.deps.taskStore).toBe(h.taskStore)
    expect(h.taskStore).toBeInstanceOf(QueueTaskStore)
  })

  it('台账 v9：没有 tasks 键；任务只在队列里', async () => {
    const h = makeHarness({ requirements: [req()], tasks: [task({ id: 't-1' })] })

    expect(Object.prototype.hasOwnProperty.call(h.ledger, 'tasks')).toBe(false)
    expect(Object.keys(h.ledger).sort()).toEqual(['migrations', 'requirements', 'revision', 'schemaVersion', 'triages'].filter((k) => k !== 'migrations'))
    expect(await h.tasksOf(REQ_ID)).toHaveLength(1)
    expect(h.queueExists(REQ_ID)).toBe(true)
  })

  it('出口剥 layer：tasksOf / seedTasks / mutateTask 的返回都不含 layer', async () => {
    const h = makeHarness({ requirements: [req()], tasks: [task({ id: 't-1' })] })

    const listed = await h.tasksOf(REQ_ID)
    const mutated = await h.setTaskFields('t-1', { status: 'in_progress' })

    expect(Object.keys(listed[0]!)).not.toContain('layer')
    expect(Object.keys(mutated[0]!)).not.toContain('layer')
    // DAG 视图（readQueue）才带 layer
    expect((await h.queueOf(REQ_ID))!.tasks[0]).toHaveProperty('layer')
  })

  it('seed.tasks 按 task.requirementId 分组（跨需求播种各写各的队列）', async () => {
    const h = makeHarness({
      requirements: [req({ id: REQ_ID }), req({ id: OTHER })],
      tasks: [task({ id: 't-a', requirementId: OTHER }), task({ id: 't-b', requirementId: OTHER })],
    })

    expect(await h.tasksOf(OTHER)).toHaveLength(2)
    expect(h.queueExists(REQ_ID)).toBe(false) // 该需求没任务 → 不建文件
  })
})

describe('v9 夹具 · 口径约定（Lead 裁定）', () => {
  it('「无队列」= 文件不存在；「空队列」= 文件存在且 tasks 为 [] —— 两者可区分', async () => {
    const h = makeHarness({ requirements: [req()] })

    // 无队列
    expect(h.queueExists('REQ-absent')).toBe(false)
    expect(h.queueRepo.rawOf('REQ-absent')).toBeUndefined()
    expect(await h.queueOf('REQ-absent')).toBeUndefined()
    expect(await h.tasksOf('REQ-absent')).toEqual([])

    // 空队列（显式播种空任务集）
    h.seedTasks(REQ_ID, [])
    expect(h.queueExists(REQ_ID)).toBe(true)
    expect(h.queueRepo.rawOf(REQ_ID)).toBeDefined()
    expect((await h.queueOf(REQ_ID))!.tasks).toEqual([])
    expect(await h.tasksOf(REQ_ID)).toEqual([])
  })

  it('失败路径判据：queueExists === false（比 readQueue()===undefined 强）', async () => {
    // 构造一份"文件存在但校验不过"的队列：queueExists=true 而 readQueue()=undefined
    const h = makeHarness({ requirements: [req()] })
    h.seedTasks(REQ_ID, [task({ id: 't-1' })])
    // 直接把内存里的 JSON 改坏（绕过 save 的校验，模拟外部写坏/半截文件）
    const broken = JSON.parse(h.queueRepo.rawOf(REQ_ID)!) as Record<string, unknown>
    broken.ready = ['t-does-not-exist']
    h.queueRepo.seedSync(REQ_ID, broken as never)

    expect(h.queueExists(REQ_ID)).toBe(true) // 文件在
    expect(await h.queueOf(REQ_ID)).toBeUndefined() // 但读不出来（V-3 不过）
    expect(h.queueRepo.warnings.some((w) => w.includes('未通过校验'))).toBe(true)
  })
})

describe('v9 夹具 · 写路径（全 async，走真实 QueueTaskStore）', () => {
  it('setTasks 整份替换：createMany 建档 / 之后 mutate 覆盖', async () => {
    const h = makeHarness({ requirements: [req()] })

    await h.setTasks(REQ_ID, [task({ id: 't-1', status: 'todo' }), task({ id: 't-2', status: 'todo' })])
    expect((await h.tasksOf(REQ_ID)).map((t) => t.id)).toEqual(['t-1', 't-2'])

    await h.setTasks(REQ_ID, [task({ id: 't-9', status: 'done' })])
    expect((await h.tasksOf(REQ_ID)).map((t) => t.id)).toEqual(['t-9'])
  })

  it('addTasks 幂等：重复 id 跳过；**队列写入序号不变**= 幂等重放判据', async () => {
    const h = makeHarness({ requirements: [req()] })

    await h.addTasks(REQ_ID, [task({ id: 't-1' })])
    const seq = h.queueRevisionOf(REQ_ID)
    expect(seq).toBe(1)

    const again = await h.addTasks(REQ_ID, [task({ id: 't-1' }), task({ id: 't-2' })])
    expect(again.map((t) => t.id)).toEqual(['t-2']) // 只新增 t-2：一次写入
    expect(h.queueRevisionOf(REQ_ID)).toBe(2)

    const noop = await h.addTasks(REQ_ID, [task({ id: 't-1' }), task({ id: 't-2' })])
    expect(noop).toEqual([])
    expect(h.queueRevisionOf(REQ_ID)).toBe(2) // 全已存在 → 不写盘 → 序号不变
  })

  it('mutateTask / setTaskFields 改字段：走真实 store（重算派生 + 校验 + 落盘）', async () => {
    const h = makeHarness({ requirements: [req()], tasks: [task({ id: 't-1', status: 'todo' })] })

    await h.mutateTask('t-1', (t) => { t.status = 'in_progress'; t.claimedBy = 'session-w-001' })

    let t1 = (await h.tasksOf(REQ_ID))[0]!
    expect(t1.status).toBe('in_progress')
    expect(t1.claimedBy).toBe('session-w-001')

    await h.setTaskFields('t-1', { status: 'done', lastReport: { at: 1, reportIndex: 1, filesChanged: ['x'], completed: ['y'] } })

    t1 = (await h.tasksOf(REQ_ID))[0]!
    expect(t1.status).toBe('done')
    expect(t1.lastReport?.filesChanged).toEqual(['x'])
  })

  it('setTaskFields 改状态会重算 ready（派生视图随真实 store 更新）', async () => {
    const h = makeHarness({
      requirements: [req()],
      tasks: [task({ id: 't-1', status: 'todo' }), task({ id: 't-2', status: 'todo', dependsOn: ['t-1'] })],
    })
    expect((await h.queueOf(REQ_ID))!.ready).toEqual(['t-1'])

    await h.setTaskFields('t-1', { status: 'done' })

    expect((await h.queueOf(REQ_ID))!.ready).toEqual(['t-2'])
  })

  it('mutateTask 目标不存在：抛 TASK_NOT_FOUND（不静默）', async () => {
    const h = makeHarness({ requirements: [req()], tasks: [task({ id: 't-1' })] })

    await expect(h.mutateTask('t-404', () => undefined)).rejects.toMatchObject({ code: 'TASK_NOT_FOUND' })
  })

  it('改完不合法（造出环）→ 抛 QUEUE_VALIDATION_FAILED 且文件保持原样', async () => {
    const h = makeHarness({ requirements: [req()], tasks: [task({ id: 't-1' })] })
    const before = h.queueRepo.rawOf(REQ_ID)

    await expect(h.setTaskFields('t-1', { dependsOn: ['t-ghost'] })).rejects.toMatchObject({ code: 'QUEUE_VALIDATION_FAILED' })

    expect(h.queueRepo.rawOf(REQ_ID)).toBe(before)
    expect((await h.tasksOf(REQ_ID))[0]!.dependsOn).toEqual([])
  })

  it('seedTasks 不合法 → 播种点就响亮抛错（不留半份脏夹具）', () => {
    const h = makeHarness({ requirements: [req()] })

    expect(() => h.seedTasks(REQ_ID, [task({ id: 't-1' }), task({ id: 't-1' })])).toThrowError(/QUEUE_VALIDATION_FAILED|不是合法 v9 队列|V-2/)
    expect(h.queueExists(REQ_ID)).toBe(false)
  })
})

describe('v9 夹具 · 台账（v9 两键语义）', () => {
  it('repo.mutate 的 change 恒为 requirements/triages 两键（undefined 补空数组）', async () => {
    const h = makeHarness({ requirements: [req()] })

    const noop = await h.repo.mutate('x', () => undefined)
    expect(Object.keys(noop.changed).sort()).toEqual(['requirements', 'triages'])
    expect(noop.changed.requirements).toEqual([])

    const changed = await h.repo.mutate('x', (ledger) => {
      ledger.requirements[0]!.title = '改过'
      return { requirements: [ledger.requirements[0]!] }
    })
    expect(changed.changed.requirements).toHaveLength(1)
    expect('tasks' in changed.changed).toBe(false)
    // 无变更不 bump（noop 返回 revision 0）→ 只有那次真实变更 +1
    expect(changed.revision).toBe(1)
  })
})
