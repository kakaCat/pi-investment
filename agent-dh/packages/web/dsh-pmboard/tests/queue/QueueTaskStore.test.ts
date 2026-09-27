/**
 * QueueTaskStore 测试（REQ-260927202051-f6df · t5 / TC-4.1~TC-4.8 / FR-1, FR-2, FR-3）。
 *
 * 另覆盖 Lead 裁决的两条接口追加：
 * - **D2 `listAll()`**：返回全量任务且顺序稳定（requirementId 字典序 + 组内文件顺序）
 * - **D3 出口剥离 `layer`**：凡返回"任务"的方法，元素都不含 `layer` 键（`readQueue` 才是 DAG 视图）
 *
 * 全在临时目录里跑，不碰真实工作区。
 */

import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { mkdtemp, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { QUEUE_ERROR, JsonQueueRepository } from '../../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../../src/repositories/QueueTaskStore.js'
import type { TaskChange } from '../../src/application/ports.js'
import type { QueueTask } from '../../src/domain/queue/QueueTypes.js'
import { mkTask } from './fixtures.js'

const REQ_A = 'REQ-260927000001-aaaa'
const REQ_B = 'REQ-260927000001-bbbb'
const REQ_NONE = 'REQ-260927000001-nope'

let root: string
let repo: JsonQueueRepository
let store: QueueTaskStore
let warnings: string[]
let clock: number

const now = (): number => (clock += 1000)

beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), 'dsh-queue-store-'))
  warnings = []
  clock = 1759000000000
  repo = new JsonQueueRepository({ workspaceRoot: root, onWarn: (m) => warnings.push(m) })
  store = new QueueTaskStore({ repo, now, onWarn: (m) => warnings.push(m) })
})

afterEach(async () => {
  await rm(root, { recursive: true, force: true })
})

const taskOf = (id: string, opts: Parameters<typeof mkTask>[1] = {}) => mkTask(id, { requirementId: REQ_A, ...opts })
const md5 = async (path: string): Promise<string> => createHash('md5').update(await readFile(path, 'utf8')).digest('hex')

describe('TaskStore createMany（TC-4.1 / TC-4.2）', () => {
  it('TC-4.1 createMany 5 任务：队列含 5 条、layer 已算、派生视图齐备', async () => {
    const created = await store.createMany(REQ_A, [
      taskOf('t-000001'),
      taskOf('t-000002', { dependsOn: ['t-000001'] }),
      taskOf('t-000003', { dependsOn: ['t-000001'] }),
      taskOf('t-000004', { dependsOn: ['t-000002'] }),
      taskOf('t-000005'),
    ])

    expect(created).toHaveLength(5)

    const queue = await store.readQueue(REQ_A)
    expect(queue).not.toBeUndefined()
    expect(queue!.tasks).toHaveLength(5)
    expect(queue!.requirement_id).toBe(REQ_A)
    expect(queue!.version).toBe(1)
    expect(queue!.schemaVersion).toBe(9)
    expect(queue!.generated_at).toBe(new Date(1759000000000 + 1000).toISOString())
    expect(queue!.updated_at).toBe(new Date(1759000000000 + 2000).toISOString())

    // layer 已算（0/1/2 三层）
    const layerOf = Object.fromEntries(queue!.tasks.map((t) => [t.id, t.layer]))
    expect(layerOf).toEqual({
      't-000001': 0,
      't-000005': 0,
      't-000002': 1,
      't-000003': 1,
      't-000004': 2,
    })
    expect(queue!.layers).toEqual([
      { layer: 0, tasks: ['t-000001', 't-000005'] },
      { layer: 1, tasks: ['t-000002', 't-000003'] },
      { layer: 2, tasks: ['t-000004'] },
    ])
    expect(queue!.edges).toEqual([
      { from: 't-000001', to: 't-000002' },
      { from: 't-000001', to: 't-000003' },
      { from: 't-000002', to: 't-000004' },
    ])
    expect(queue!.ready).toEqual(['t-000001', 't-000005'])
  })

  it('TC-4.2 createMany 重复 id：幂等跳过、不覆盖既有字段、文件 mtime 不变', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])
    const path = repo.pathOf(REQ_A)
    const firstMtime = (await stat(path)).mtimeMs
    const firstContent = await readFile(path, 'utf8')

    // 同 id 再来一次，但标题/状态都不同 → 必须**不覆盖**
    const dupes = await store.createMany(REQ_A, [
      { ...taskOf('t-000001', { status: 'done' }), title: '被覆盖的标题' },
      taskOf('t-000002'),
    ])

    expect(dupes.map((t) => t.id)).toEqual(['t-000002']) // 只新增了 t-000002
    const tasks = await store.listByRequirement(REQ_A)
    const t1 = tasks.find((t) => t.id === 't-000001')!
    expect(t1.title).toBe('任务 t-000001') // 未被覆盖
    expect(t1.status).toBe('todo') // 状态未被覆盖
    expect((await stat(path)).mtimeMs).toBeGreaterThanOrEqual(firstMtime)
    expect(await readFile(path, 'utf8')).not.toBe(firstContent) // 因为确实新增了 t-000002

    // 全部 id 都已存在 → 不写盘（mtime 与内容都不变）——t11 幂等判据的可观测形态
    const mtimeBefore = (await stat(path)).mtimeMs
    const contentBefore = await readFile(path, 'utf8')
    const again = await store.createMany(REQ_A, [taskOf('t-000001'), taskOf('t-000002')])
    expect(again).toEqual([])
    expect((await stat(path)).mtimeMs).toBe(mtimeBefore)
    expect(await readFile(path, 'utf8')).toBe(contentBefore)
  })

  it('createMany 空数组：不建文件、不报错', async () => {
    expect(await store.createMany(REQ_A, [])).toEqual([])
    expect(existsSync(repo.pathOf(REQ_A))).toBe(false)
  })

  it('createMany 的 requirementId 不一致：拒绝写入（防任务落到别人档案）', async () => {
    await expect(store.createMany(REQ_A, [mkTask('t-000001', { requirementId: REQ_B })])).rejects.toMatchObject({
      code: QUEUE_ERROR.VALIDATION_FAILED,
    })
    expect(existsSync(repo.pathOf(REQ_A))).toBe(false)
  })
})

describe('TaskStore mutate（TC-4.3 / TC-4.4 / TC-4.5 / TC-4.8）', () => {
  it('TC-4.3 mutate 改 done：ready 解锁下游 + updated_at 刷新 + statusHistory 追加', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001'), taskOf('t-000002', { dependsOn: ['t-000001'] })])
    const before = await store.readQueue(REQ_A)
    expect(before!.ready).toEqual(['t-000001'])

    const changed = await store.mutate(REQ_A, (tasks) =>
      tasks.map((t): QueueTask =>
        t.id === 't-000001'
          ? {
              ...t,
              status: 'done' as const,
              statusHistory: [...(t.statusHistory ?? []), { status: 'done' as const, at: now(), by: t.updatedBy }],
            }
          : t,
      ),
    )

    expect(changed.map((t) => t.id)).toEqual(['t-000001'])

    const after = await store.readQueue(REQ_A)
    expect(after!.tasks.find((t) => t.id === 't-000001')!.status).toBe('done')
    expect(after!.ready).toEqual(['t-000002']) // 下游被解锁
    expect(after!.updated_at).not.toBeUndefined()
    expect(after!.updated_at).not.toBe(before!.updated_at)
    expect(after!.layers).toEqual([{ layer: 0, tasks: ['t-000001'] }, { layer: 1, tasks: ['t-000002'] }])
  })

  it('TC-4.4 mutate 到无队列的需求：抛 QUEUE_NOT_FOUND（不隐式建档）', async () => {
    await expect(store.mutate(REQ_NONE, (tasks) => tasks)).rejects.toMatchObject({ code: QUEUE_ERROR.NOT_FOUND })
    expect(existsSync(repo.pathOf(REQ_NONE))).toBe(false)
  })

  it('TC-4.5 mutate 后校验失败：抛错且文件 md5 与更新前**完全一致**（保持上次有效内容）', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001'), taskOf('t-000002', { dependsOn: ['t-000001'] })])
    const path = repo.pathOf(REQ_A)
    const beforeMd5 = await md5(path)

    await expect(
      store.mutate(REQ_A, (tasks) => tasks.map((t) => (t.id === 't-000002' ? { ...t, dependsOn: ['t-not-exist'] } : t))),
    ).rejects.toMatchObject({ code: QUEUE_ERROR.VALIDATION_FAILED })

    expect(await md5(path)).toBe(beforeMd5)
    // 内存缓存也不得被污染（后续读仍看到改动前的状态）
    expect((await store.listByRequirement(REQ_A)).find((t) => t.id === 't-000002')!.dependsOn).toEqual(['t-000001'])
  })

  it('mutate 回调返回 undefined：视为无变更（不写盘、不广播、mtime 不变）', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])
    const path = repo.pathOf(REQ_A)
    const before = await stat(path)
    const changes: TaskChange[] = []
    store.subscribe((c) => changes.push(c))

    const changed = await store.mutate(REQ_A, () => undefined)

    expect(changed).toEqual([])
    expect((await stat(path)).mtimeMs).toBe(before.mtimeMs)
    expect(changes).toEqual([])
  })

  it('**纯删除必须写盘**（回归：曾因 changed.length===0 提前返回而静默不生效）', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001'), taskOf('t-000002')])
    const path = repo.pathOf(REQ_A)
    const beforeSeq = (await stat(path)).mtimeMs
    const changes: TaskChange[] = []
    store.subscribe((c) => changes.push(c))

    // 删光：回调只做删除（返回空数组）——这正是曾经被静默吞掉的形状
    const removed = await store.mutate(REQ_A, () => [])

    // ① 文件真的变了（内容为空队列；mtime 前进）
    const onDisk = JSON.parse(await readFile(path, 'utf8')) as { tasks: unknown[] }
    expect(onDisk.tasks).toEqual([])
    expect((await stat(path)).mtimeMs).toBeGreaterThanOrEqual(beforeSeq)
    // ② 读路径立即反映
    expect(await store.listByRequirement(REQ_A)).toEqual([])
    // ③ 订阅者收到 task-removed，且变更集**非空**（否则订阅者无法失效缓存）
    expect(changes).toHaveLength(1)
    expect(changes[0]!.kind).toBe('task-removed')
    expect(changes[0]!.tasks.map((t) => t.id).sort()).toEqual(['t-000001', 't-000002'])
    // ④ 返回值如实给出被删卡的末态
    expect(removed.map((t) => t.id).sort()).toEqual(['t-000001', 't-000002'])
    expect(Object.keys(removed[0]!)).not.toContain('layer')
  })

  it('部分删除：只删一张也写盘（保留者在，删除者消失）', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001'), taskOf('t-000002')])
    const changes: TaskChange[] = []
    store.subscribe((c) => changes.push(c))

    await store.mutate(REQ_A, (tasks) => tasks.filter((t) => t.id !== 't-000002'))

    expect((await store.listByRequirement(REQ_A)).map((t) => t.id)).toEqual(['t-000001'])
    expect(changes).toHaveLength(1)
    expect(changes[0]!.kind).toBe('task-removed')
    expect(changes[0]!.tasks.map((t) => t.id)).toEqual(['t-000002'])
  })

  it('mutate 回调没改出差异：不白写一次盘（mtime 不变）', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])
    const path = repo.pathOf(REQ_A)
    const before = await stat(path)

    const changed = await store.mutate(REQ_A, (tasks) => tasks.map((t) => ({ ...t })))

    expect(changed).toEqual([])
    expect((await stat(path)).mtimeMs).toBe(before.mtimeMs)
  })

  it('mutate 原地修改（不返回新数组）同样生效', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])

    const changed = await store.mutate(REQ_A, (tasks) => {
      tasks[0]!.status = 'in_progress'
      return tasks
    })

    expect(changed.map((t) => t.id)).toEqual(['t-000001'])
    expect((await store.listByRequirement(REQ_A))[0]!.status).toBe('in_progress')
  })

  it('TC-4.8 subscribe 收到 TaskChange：kind=task-moved 且 tasks 含改动任务', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])
    const changes: TaskChange[] = []
    store.subscribe((c) => changes.push(c))

    await store.mutate(REQ_A, (tasks) => tasks.map((t) => ({ ...t, status: 'in_progress' as const })))

    expect(changes).toHaveLength(1)
    expect(changes[0]!.requirementId).toBe(REQ_A)
    expect(changes[0]!.kind).toBe('task-moved')
    expect(changes[0]!.tasks.map((t) => t.id)).toEqual(['t-000001'])
    expect(changes[0]!.revision).toBeGreaterThan(0)
  })

  it('subscribe 退订后不再收到通知；订阅者抛错不阻断写', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])
    const seen: TaskChange[] = []
    const off = store.subscribe(() => {
      throw new Error('订阅者炸了')
    })
    store.subscribe((c) => seen.push(c))

    await expect(store.mutate(REQ_A, (tasks) => tasks.map((t) => ({ ...t, status: 'in_progress' as const })))).resolves.toBeDefined()
    expect(seen).toHaveLength(1)
    expect(warnings.some((w) => w.includes('订阅者回调抛错'))).toBe(true)

    off()
    store.subscribe(() => undefined)
    await store.mutate(REQ_A, (tasks) => tasks.map((t) => ({ ...t, status: 'todo' as const })))
    expect(seen).toHaveLength(2)
  })
})

describe('TaskStore 读（TC-4.6 / TC-4.7）', () => {
  it('TC-4.6 listByRequirement 无文件：返回 []（不是错误）', async () => {
    expect(await store.listByRequirement(REQ_NONE)).toEqual([])
    expect(await store.readQueue(REQ_NONE)).toBeUndefined()
  })

  it('TC-4.7 写后 get 立即读到新值（缓存已刷新，不是陈旧快照）', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])
    expect((await store.get('t-000001'))!.status).toBe('todo') // 首次未命中索引 → 扫盘建索引

    await store.mutate(REQ_A, (tasks) => tasks.map((t) => ({ ...t, status: 'in_progress' as const })))

    expect((await store.get('t-000001'))!.status).toBe('in_progress')
  })

  it('get 不存在的任务：返回 undefined（不抛错）', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])
    expect(await store.get('t-nope00')).toBeUndefined()
  })

  it('get 跨需求命中（未缓存需求靠一次扫盘建索引）', async () => {
    await repo.save(REQ_B, {
      version: 1,
      requirement_id: REQ_B,
      schemaVersion: 9,
      generated_at: '2026-09-27T22:00:00.000Z',
      tasks: [{ ...mkTask('t-b00001', { requirementId: REQ_B }), layer: 0 }],
      edges: [],
      layers: [{ layer: 0, tasks: ['t-b00001'] }],
      ready: ['t-b00001'],
    })

    expect((await store.get('t-b00001'))!.requirementId).toBe(REQ_B)
  })

  it('读到的返回值是副本：改它不会污染缓存', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])
    const first = await store.listByRequirement(REQ_A)
    ;(first[0] as unknown as Record<string, unknown>).title = '被改了'
    ;(first[0]!.executions as unknown[]).push({ bogus: true })

    expect((await store.listByRequirement(REQ_A))[0]!.title).toBe('任务 t-000001')
    expect((await store.listByRequirement(REQ_A))[0]!.executions).toEqual([])
  })

  it('TC-11.6 启动不预读：损坏的队列文件在首次访问前不产生告警', async () => {
    await repo.save(REQ_B, {
      version: 1,
      requirement_id: REQ_B,
      schemaVersion: 9,
      generated_at: '2026-09-27T22:00:00.000Z',
      tasks: [{ ...mkTask('t-b00001', { requirementId: REQ_B }), layer: 0 }],
      edges: [],
      layers: [{ layer: 0, tasks: ['t-b00001'] }],
      ready: ['t-b00001'],
    })
    // 另造一个损坏队列
    await writeFile(join(root, 'docs', 'requirements', 'REQ-260927000001-cccc', 'queue.json'), '{ broken', 'utf8').catch(async () => {
      const { mkdir } = await import('node:fs/promises')
      await mkdir(join(root, 'docs', 'requirements', 'REQ-260927000001-cccc'), { recursive: true })
      await writeFile(join(root, 'docs', 'requirements', 'REQ-260927000001-cccc', 'queue.json'), '{ broken', 'utf8')
    })

    const fresh = new QueueTaskStore({ repo, now, onWarn: (m) => warnings.push(m) })
    expect(warnings).toEqual([]) // 构造时零读盘

    await fresh.readQueue(REQ_B)
    expect(warnings).toEqual([]) // 只读了 REQ_B，没碰损坏的那个

    await fresh.listByRequirement('REQ-260927000001-cccc')
    expect(warnings.some((w) => w.includes('隔离'))).toBe(true) // 访问到才告警
  })
})

describe('TaskStore 接口追加 D2/D3（Lead 裁决）', () => {
  it('D2 listAll：返回全量任务，顺序 = requirementId 字典序 + 组内文件顺序（两次调用逐字节相等）', async () => {
    await store.createMany(REQ_B, [mkTask('t-b00001', { requirementId: REQ_B }), mkTask('t-b00002', { requirementId: REQ_B })])
    await store.createMany(REQ_A, [mkTask('t-a00001', { requirementId: REQ_A }), mkTask('t-a00002', { requirementId: REQ_A })])

    const first = await store.listAll()
    const second = await store.listAll()

    expect(first.map((t) => t.id)).toEqual(['t-a00001', 't-a00002', 't-b00001', 't-b00002'])
    expect(JSON.stringify(second)).toBe(JSON.stringify(first)) // 稳定：逐字节相等
  })

  it('D2 listAll 在需求目录为空时返回 []（不抛错）', async () => {
    expect(await store.listAll()).toEqual([])
  })

  it('D3 出口剥离 layer：listByRequirement / listAll / get / createMany / mutate 的元素都不含 layer 键', async () => {
    const created = await store.createMany(REQ_A, [taskOf('t-000001'), taskOf('t-000002', { dependsOn: ['t-000001'] })])
    const mutated = await store.mutate(REQ_A, (tasks) => tasks.map((t) => (t.id === 't-000002' ? { ...t, status: 'in_progress' as const } : t)))
    const listed = await store.listByRequirement(REQ_A)
    const all = await store.listAll()
    const got = await store.get('t-000001')

    for (const [label, list] of [
      ['createMany', created],
      ['mutate', mutated],
      ['listByRequirement', listed],
      ['listAll', all],
      ['get', got === undefined ? [] : [got]],
    ] as const) {
      expect(list.length, label).toBeGreaterThan(0)
      for (const t of list) {
        expect(Object.keys(t), `${label} 的 ${t.id} 不该带 layer`).not.toContain('layer')
      }
    }

    // 但 readQueue 是 DAG 视图，必须带 layer
    const queue = await store.readQueue(REQ_A)
    expect(queue!.tasks.every((t) => typeof t.layer === 'number')).toBe(true)
  })

  it('D3 listAll 返回的是 TaskRecord 全集：去掉 layer 后字段一个不少', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])
    const [record] = await store.listAll()
    const queue = await store.readQueue(REQ_A)
    const queued: QueueTask = queue!.tasks[0]!

    expect(Object.keys(queued).sort()).toEqual([...Object.keys(record!), 'layer'].sort())
  })
})

describe('TaskStore 落盘形态', () => {
  it('队列 JSON 由 QueueRepository 写出：目录内无临时文件残留', async () => {
    await store.createMany(REQ_A, [taskOf('t-000001')])
    await store.mutate(REQ_A, (tasks) => tasks.map((t) => ({ ...t, status: 'in_progress' as const })))

    const names = await readdir(join(root, 'docs', 'requirements', REQ_A))
    expect(names).toEqual(['queue.json'])
  })
})
