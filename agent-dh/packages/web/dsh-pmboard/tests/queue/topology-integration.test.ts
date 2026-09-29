/**
 * topology ⇄ 队列写路径 ⇄ 校验器 接口联调（REQ-260927202051-f6df · t-315ea1 / integrate / FR-1）。
 *
 * t-5be8c6（dev）只证明拓扑纯函数自身正确；本文件证明的是**接口联调**——
 * `topology.computeLayers/computeEdges/computeReady` 是否真的是落盘队列文件里
 * `layers/edges/ready/layer` 的**唯一来源**，而不是"单测里算得对、写盘时另算一套"。
 *
 * 联调对象（全部是既有真实实现，本文件不自造 mock 端口、不手填派生字段）：
 * - `JsonQueueRepository`（真实临时工作区的队列文件读写）      ← src/repositories/QueueRepository.ts
 * - `QueueTaskStore.createMany / mutate / readQueue`（写路径重算派生视图） ← src/repositories/QueueTaskStore.ts
 * - `validateQueueFile`（V-5 用 topology.computeReady 反查 ready）          ← src/domain/queue/validateQueue.ts
 * - `computeLayers / computeEdges / computeReady`（被联调的纯函数）          ← src/domain/queue/topology.ts
 *
 * 验收口径「给出请求样例与期望响应，实际返回与预期一致」在本文件的落法：
 * - 请求样例 = createMany(4 任务菱形) / mutate(t1→done) / createMany(成环) 三次真实调用
 * - 期望响应 = 落盘 JSON 的派生视图与 `topology` 输出逐字段相等、V-5 通过、环输入拒绝且不落盘
 * - 实际返回 = vitest 断言结果（命令与输出见台账汇报 evidence）
 *
 * 纪律：全程在 `os.tmpdir()` 临时工作区跑，**不碰真实仓库 docs/ 与真实队列文件**。
 */

import { existsSync } from 'node:fs'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { computeEdges, computeLayers, computeReady } from '../../src/domain/queue/topology.js'
import type { QueueFile } from '../../src/domain/queue/QueueTypes.js'
import { validateQueueFile } from '../../src/domain/queue/validateQueue.js'
import { JsonQueueRepository } from '../../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../../src/repositories/QueueTaskStore.js'
import { mkTask } from './fixtures.js'

/** 联调用需求 id（刻意不同于本需求自身 id，避免与真实工作区需求混淆）。 */
const REQ = 'REQ-260927000001-topo'

let root: string
let repo: JsonQueueRepository
let store: QueueTaskStore

beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), 'dsh-topology-integ-'))
  repo = new JsonQueueRepository({ workspaceRoot: root })
  store = new QueueTaskStore({ repo, now: () => 1759000000000 })
})

afterEach(async () => {
  await rm(root, { recursive: true, force: true })
})

/** 读回落盘的队列文件（真实磁盘 JSON，不是 store 缓存）。 */
async function readDiskQueue(): Promise<QueueFile> {
  return JSON.parse(await readFile(repo.pathOf(REQ), 'utf8')) as QueueFile
}

const T1 = 't-000001'
const T2 = 't-000002'
const T3 = 't-000003'
const T4 = 't-000004'

/** 菱形：t1 → {t2,t3} → t4（与父卡验收锚点同形）。 */
const diamond = () => [
  mkTask(T1, { requirementId: REQ }),
  mkTask(T2, { requirementId: REQ, dependsOn: [T1] }),
  mkTask(T3, { requirementId: REQ, dependsOn: [T1] }),
  mkTask(T4, { requirementId: REQ, dependsOn: [T2, T3] }),
]

describe('联调 1：createMany → 落盘派生视图 = topology 输出', () => {
  it('请求样例：createMany(菱形 4 任务)；期望响应：layers=[[t1],[t2,t3],[t4]]、ready=[t1]、V-5 通过', async () => {
    // ── 请求样例 ──────────────────────────────────────────────────────────
    const created = await store.createMany(REQ, diamond())

    // 出口契约（D3）：写路径返回的是 TaskRecord（无 layer），不是队列视图
    expect(created).toHaveLength(4)
    expect(created.every((t) => !('layer' in t))).toBe(true)

    // ── 实际返回（真实磁盘 JSON）──────────────────────────────────────────
    const file = await readDiskQueue()

    // 期望：菱形分层与 ready（父卡验收锚点 ②）
    expect(file.layers).toEqual([
      { layer: 0, tasks: [T1] },
      { layer: 1, tasks: [T2, T3] },
      { layer: 2, tasks: [T4] },
    ])
    expect(file.ready).toEqual([T1])
    expect(file.edges).toEqual([
      { from: T1, to: T2 },
      { from: T1, to: T3 },
      { from: T2, to: T4 },
      { from: T3, to: T4 },
    ])

    // 联调核心：落盘的三个派生字段必须**逐字段等于** topology 对同一 tasks 的输出
    expect(file.layers).toEqual(computeLayers(file.tasks))
    expect(file.edges).toEqual(computeEdges(file.tasks))
    expect(file.ready).toEqual(computeReady(file.tasks))

    // 每个任务的 layer 也来自同一次拓扑计算（V-4 的判据来源）
    const layerOf = new Map<string, number>()
    for (const layer of computeLayers(file.tasks)) for (const id of layer.tasks) layerOf.set(id, layer.layer)
    for (const t of file.tasks) expect(t.layer).toBe(layerOf.get(t.id))

    // 校验器（V-5 用 topology.computeReady 反查 ready）必须放行这份自洽队列
    const verdict = validateQueueFile(file)
    expect(verdict.issues).toEqual([])
    expect(verdict.passed).toBe(true)
  })
})

describe('联调 2：mutate 推进状态 → ready 解锁与落盘同步', () => {
  it('请求样例：mutate(t1→done)；期望响应：ready=[t2,t3]，再推 t2→done 后 ready=[t4]', async () => {
    await store.createMany(REQ, diamond())

    // ── 请求样例 1：t1 todo → done ────────────────────────────────────────
    const changed = await store.mutate(REQ, (tasks) => tasks.map((t) => (t.id === T1 ? { ...t, status: 'done' as const } : t)))
    expect(changed.map((t) => t.id)).toEqual([T1])

    // ── 实际返回：缓存视图与磁盘 JSON 都解锁下游，且等于 topology 的输出 ──
    const viaStore = await store.readQueue(REQ)
    const viaDisk = await readDiskQueue()
    expect(viaStore?.ready).toEqual([T2, T3])
    expect(viaDisk.ready).toEqual([T2, T3])
    expect(viaDisk.ready).toEqual(computeReady(viaDisk.tasks))
    expect(validateQueueFile(viaDisk).passed).toBe(true)

    // ── 请求样例 2：t2 todo → done（t3 仍未完成 → t4 不得解锁）────────────
    await store.mutate(REQ, (tasks) => tasks.map((t) => (t.id === T2 ? { ...t, status: 'done' as const } : t)))

    const after2 = await readDiskQueue()
    expect(after2.ready).toEqual([T3]) // t3 是 ready；t4 仍被 t3 阻塞
    expect(after2.ready).toEqual(computeReady(after2.tasks))
    expect(after2.tasks.find((t) => t.id === T1)?.layer).toBe(0)
    expect(after2.tasks.find((t) => t.id === T4)?.layer).toBe(2)

    // ── 请求样例 3：t3 todo → done → t4 解锁 ──────────────────────────────
    await store.mutate(REQ, (tasks) => tasks.map((t) => (t.id === T3 ? { ...t, status: 'done' as const } : t)))

    const after3 = await readDiskQueue()
    expect(after3.ready).toEqual([T4])
    expect(after3.ready).toEqual(computeReady(after3.tasks))
    expect(validateQueueFile(after3).passed).toBe(true)
  })
})

describe('联调 3：成环输入经写路径拒绝且不落盘', () => {
  it('请求样例：createMany(t1→t2→t3→t1)；期望响应：拒绝且 message 含 CIRCULAR、无 queue.json', async () => {
    // ── 请求样例：环依赖（t1←t3←t2←t1）──────────────────────────────────
    const cyclic = [
      mkTask(T1, { requirementId: REQ, dependsOn: [T3] }),
      mkTask(T2, { requirementId: REQ, dependsOn: [T1] }),
      mkTask(T3, { requirementId: REQ, dependsOn: [T2] }),
    ]

    // ── 实际返回：写路径把 topology 的环错误原样上抛，且**没有落盘** ────────
    await expect(store.createMany(REQ, cyclic)).rejects.toThrow(/CIRCULAR/)
    expect(existsSync(repo.pathOf(REQ))).toBe(false)
  })
})
