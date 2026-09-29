/**
 * 依赖传递归约 / 队列依赖归一化（REQ-260929010300-dbf9 · 用户 2026-09-29 裁定 B「数据侧」）。
 *
 * 背景：拆分落库时每张卡写的是「全部前置」（传递闭包），数据里普遍存在 A→B、B→C、A→C 三角形
 * （线上实测 33/55 份队列有冗余前置）。本文件钉住修复后的口径：**数据落盘时 dependsOn 只含直接前置**，
 * 且归约不改变 layer / ready（传递归约保持可达性）。
 *
 * 三层覆盖：
 * - 纯函数层：transitiveReduce 的判据与边界（悬空保留、保序、去重、环安全）
 * - 文件层：normalizeQueueFile 归约 + 派生视图整份重算 + 幂等
 * - 写路径层：QueueTaskStore.createMany / mutate 落盘即直接前置（真临时工作区 + 真磁盘 JSON）
 */
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { normalizeQueueFile } from '../../src/domain/queue/normalizeQueue.js'
import { transitiveReduce } from '../../src/domain/queue/transitiveReduction.js'
import { computeLayers, computeReady } from '../../src/domain/queue/topology.js'
import type { QueueFile } from '../../src/domain/queue/QueueTypes.js'
import { validateQueueFile } from '../../src/domain/queue/validateQueue.js'
import { JsonQueueRepository } from '../../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../../src/repositories/QueueTaskStore.js'
import { mkTask, queueOf } from './fixtures.js'

const graph = (pairs: Array<[string, string[]]>): Map<string, string[]> => new Map(pairs)

describe('transitiveReduce：依赖闭包 → 直接前置', () => {
  it('同源三角形 A→B、B→C、A→C ⇒ C 只留直接前置 B', () => {
    const out = transitiveReduce(graph([['A', []], ['B', ['A']], ['C', ['A', 'B']]]))
    expect(out.get('C')).toEqual(['B'])
    expect(out.get('B')).toEqual(['A'])
  })

  it('菱形闭包 t4=[t1,t2,t3]（t2/t3 均依赖 t1）⇒ [t2,t3]', () => {
    const out = transitiveReduce(graph([['t1', []], ['t2', ['t1']], ['t3', ['t1']], ['t4', ['t1', 't2', 't3']]]))
    expect(out.get('t4')).toEqual(['t2', 't3'])
  })

  it('保序 + 去重：依赖顺序是数据，归约后顺序不变', () => {
    const out = transitiveReduce(graph([['a', []], ['b', []], ['t', ['b', 'a', 'b']]]))
    expect(out.get('t')).toEqual(['b', 'a'])
  })

  it('悬空前置一律保留（即便能从别的依赖到达）——不替 V-3 静默消灭问题', () => {
    const out = transitiveReduce(graph([['a', ['missing']], ['t', ['a', 'missing']]]))
    expect(out.get('t')).toEqual(['a', 'missing'])
  })

  it('成环不爆栈、不抛错（判环是 computeLayers / validateQueue 的职责）', () => {
    const cyc = graph([['a', ['b']], ['b', ['a']], ['c', ['a', 'b']]])
    expect(() => transitiveReduce(cyc)).not.toThrow()
    expect(Array.isArray(transitiveReduce(cyc).get('c'))).toBe(true)
    // 单前置节点不进归约分支（环上也不会被删）
    expect(transitiveReduce(cyc).get('a')).toEqual(['b'])
  })

  it('简单链无冗余 ⇒ 结果与输入一致（幂等）', () => {
    const out = transitiveReduce(graph([['a', []], ['b', ['a']], ['c', ['b']]]))
    expect(out.get('b')).toEqual(['a'])
    expect(out.get('c')).toEqual(['b'])
  })
})

describe('normalizeQueueFile：归约 + 派生视图重算（layer/ready 不变）', () => {
  const R = 'REQ-reduce-unit'
  const T1 = 't-r1'
  const T2 = 't-r2'
  const T3 = 't-r3'
  /** t1 → t2 → t3，而 t3 写成闭包 [t1,t2]。 */
  const draft = () => [
    mkTask(T1, { requirementId: R }),
    mkTask(T2, { requirementId: R, dependsOn: [T1] }),
    mkTask(T3, { requirementId: R, dependsOn: [T1, T2] }),
  ]

  it('dependsOn/edges 只留直接前置；layer 与 ready 与归约前逐字相同', () => {
    const before = queueOf(R, draft())
    const after = normalizeQueueFile(before)
    expect(after.tasks.find((t) => t.id === T3)?.dependsOn).toEqual([T2])
    expect(after.edges).toEqual([{ from: T1, to: T2 }, { from: T2, to: T3 }])
    expect(after.layers).toEqual(computeLayers(draft()))
    expect(after.ready).toEqual(computeReady(draft()))
    expect(after.tasks.map((t) => t.layer)).toEqual(before.tasks.map((t) => t.layer))
  })

  it('幂等：对已归约的文件再归一化得到同一份结果', () => {
    const once = normalizeQueueFile(queueOf(R, draft()))
    expect(normalizeQueueFile(once)).toEqual(once)
  })
})

describe('QueueTaskStore 写路径：落盘即直接前置', () => {
  const R = 'REQ-reduce-store'
  const T1 = 't-s1'
  const T2 = 't-s2'
  const T3 = 't-s3'

  let root: string
  let repo: JsonQueueRepository
  let store: QueueTaskStore

  beforeEach(async () => {
    root = await mkdtemp(join(tmpdir(), 'dsh-queue-reduce-'))
    repo = new JsonQueueRepository({ workspaceRoot: root })
    store = new QueueTaskStore({ repo, now: () => 1759000000000 })
  })
  afterEach(async () => {
    await rm(root, { recursive: true, force: true })
  })

  const readDisk = async (id: string): Promise<QueueFile> =>
    JSON.parse(await readFile(repo.pathOf(id), 'utf8')) as QueueFile

  it('createMany：入参带闭包 ⇒ 落盘/返回值都是直接前置，V-5 通过', async () => {
    const created = await store.createMany(R, [
      mkTask(T1, { requirementId: R }),
      mkTask(T2, { requirementId: R, dependsOn: [T1] }),
      mkTask(T3, { requirementId: R, dependsOn: [T1, T2] }),
    ])
    // 返回值取归一化后的落盘态（不取入参副本）
    expect(created.find((t) => t.id === T3)?.dependsOn).toEqual([T2])

    const disk = await readDisk(R)
    expect(disk.tasks.find((t) => t.id === T3)?.dependsOn).toEqual([T2])
    expect(disk.edges).toEqual([{ from: T1, to: T2 }, { from: T2, to: T3 }])
    expect(disk.ready).toEqual([T1])
    expect(validateQueueFile(disk).passed).toBe(true)
  })

  it('mutate：存量带闭包的文件经任一写路径也被归一化（迁移兜底）', async () => {
    await repo.save(R, queueOf(R, [
      mkTask(T1, { requirementId: R }),
      mkTask(T2, { requirementId: R, dependsOn: [T1] }),
      mkTask(T3, { requirementId: R, dependsOn: [T1, T2] }),
    ]))
    // 写前磁盘仍是闭包（证明这是"存量"而非 createMany 产物）
    expect((await readDisk(R)).tasks.find((t) => t.id === T3)?.dependsOn).toEqual([T1, T2])

    await store.mutate(R, (tasks) => tasks) // 空变换：唯一变化来自写路径归一化
    const disk = await readDisk(R)
    expect(disk.tasks.find((t) => t.id === T3)?.dependsOn).toEqual([T2])
    expect(disk.edges).toHaveLength(2)
    expect(validateQueueFile(disk).passed).toBe(true)
  })
})
