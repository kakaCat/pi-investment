/**
 * 读方改造等价性证据（REQ-260927202051-f6df / t-66797c、t-0c7f17；D8 口径 a~e）
 *
 * **为什么有这个文件**：本需求把任务从台账搬到按需求分片的 `queue.json`，读方（看板/路由/工具）
 * 全部改数据源。最高风险是"界面空白 / 字段变少 / 顺序漂移"，而**单测绿 ≠ 读方不回归**。
 * 故这里做**真实的迁移前后对照**：同一批 TaskRecord，
 *   ① **迁移前**：用旧表达式（直接读 v8 台账的 `tasks[]`）算出期望值；
 *   ② **迁移后**：同一批 TaskRecord 经 `TaskStore.createMany` 落成 queue.json，走**真实 HTTP 路由**取值；
 *   ③ 断言两者一致。
 *
 * **数据来源是「真实 v8 台账副本」**（Lead D8 口径①）：
 * `tests/fixtures/read-sites-v8-ledger.json` 由 `agent-dh/.dsh-data/dsh-reqboard.json`（schemaVersion=8）
 * **抽取**而来 —— 两个真实需求 + 其**全部**真实任务、**保持原全局数组顺序**、**依赖闭合**（0 悬空引用）。
 * 刻意不手搓夹具：手搓会把"我以为台账长这样"的假设固化进证据（文档字段表 ≠ 真身，已踩过一次）。
 *
 * **断言口径 = Lead 裁决 D8 的 a~e 五条**，且**每条各自独立成 `it`**（串成一条大断言时，
 * 红了不知道是哪条坏的，证据价值大减）：
 *   a) 任务级逐字节：按 `id` 配对 → 键集相等 + 值相等 + **不含 `layer`**
 *   b) **需求内**相对顺序一致（组内 id 序列）—— 分片后唯一保住的顺序语义
 *   c) 计数 = 源台账现算值
 *   d) 响应其余字段逐字节相等
 *   e) **不要求**跨需求全局顺序（见最后一个 `it` 的负向固化）
 *
 * @module dsh-pmboard/tests/read-sites-equivalence
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { JsonQueueRepository } from '../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../src/repositories/QueueTaskStore.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { readyTasks, type RequirementRecord, type TaskRecord } from '../src/shared/protocol.js'
import { transitiveReduce } from '../src/domain/queue/transitiveReduction.js'
import { countDoneTasks, countUnfinishedTasks } from '../src/domain/status/Predicates.js'

const FIXTURE = join(dirname(fileURLToPath(import.meta.url)), 'fixtures/read-sites-v8-ledger.json')

interface V8Fixture {
  __provenance: { source: string; schemaVersion: number; revision: number }
  schemaVersion: number
  revision: number
  requirements: readonly RequirementRecord[]
  tasks: readonly TaskRecord[]
}

const fixture = JSON.parse(readFileSync(FIXTURE, 'utf8')) as V8Fixture

/** 源台账真相（迁移前）：真实 v8 的 tasks[]。 */
const V8_TASKS = fixture.tasks
const V9_REQUIREMENTS = fixture.requirements
const REVISION = fixture.revision
/** 夹具涉及的需求（原序去重）。 */
const REQ_IDS = [...new Set(V8_TASKS.map(t => t.requirementId))]

/**
 * 写路径的依赖归一化（2026-09-29 · REQ-260929010300-dbf9 用户裁定 B「数据侧」）：
 * `createMany` 会把 `dependsOn` 归约为**直接前置**（传递闭包 → 直接前置），
 * 故本用例的"迁移后期望值"必须先做**同一份**归约，才能继续用"逐字节"口径判等价。
 * 归约保持可达性 ⇒ 除 `dependsOn` 外所有字段与顺序都不变；这仍是真实迁移的前后对照，
 * 只是把「写路径会归一化依赖」这条**新契约**显式入账（不是放宽断言）。
 */
function reduceLedgerDeps(tasks: readonly TaskRecord[]): Map<string, string[]> {
  const reduced = new Map<string, string[]>()
  for (const reqId of REQ_IDS) {
    const scoped = tasks.filter(t => t.requirementId === reqId)
    const graph = new Map(scoped.map(t => [t.id, t.dependsOn ?? []]))
    for (const [id, deps] of transitiveReduce(graph)) reduced.set(id, deps)
  }
  return reduced
}
const REDUCED_DEPS = reduceLedgerDeps(V8_TASKS)

/** 迁移前的旧表达式：直接吃 v8 台账 tasks[] 数组（与改造前读方逐字同式；依赖按新契约归一化）。 */
const before = {
  stateTasks: () => V8_TASKS.map(t => ({ ...t, dependsOn: REDUCED_DEPS.get(t.id) ?? t.dependsOn })),
  readyMap: () => Object.fromEntries(
    V9_REQUIREMENTS.map(r => [r.id, readyTasks(V8_TASKS, r.id).map(t => t.id)]),
  ),
  idsOf: (reqId: string) => V8_TASKS.filter(t => t.requirementId === reqId).map(t => t.id),
  countOf: (reqId: string) => V8_TASKS.filter(t => t.requirementId === reqId).length,
  summaryOf: (reqId: string) => {
    // 与路由**逐字同式**：旧路由用的是这两个 domain 判定函数，只有数据源不同。
    const tasks = V8_TASKS.filter(t => t.requirementId === reqId)
    return { tasksDone: countDoneTasks(tasks), tasksActive: countUnfinishedTasks(tasks), tasksTotal: tasks.length }
  },
}

describe('读方等价性证据（REQ-260927202051-f6df / D8 a~e）', () => {
  let dir: string
  let store: ReqboardStore
  let taskStore: QueueTaskStore
  let handler: ReturnType<typeof createReqboardHandler>

  beforeEach(async () => {
    // 夹具自检：必须是**真实 v8**（证明"迁移前"那一侧取自真实台账，而非理想化手搓）
    expect(fixture.schemaVersion, '夹具必须来自 v8 台账').toBe(8)
    expect(fixture.__provenance.source).toContain('dsh-reqboard.json')
    expect(V8_TASKS.length).toBeGreaterThan(0)
    expect(REQ_IDS.length).toBeGreaterThanOrEqual(2)

    dir = mkdtempSync(join(tmpdir(), 'pmboard-equiv-'))
    mkdirSync(join(dir, 'docs/requirements'), { recursive: true })
    // v9 台账：只有 requirements / triages（不再有 tasks 键）
    writeFileSync(
      join(dir, 'dsh-reqboard.json'),
      JSON.stringify({ schemaVersion: 9, revision: REVISION, requirements: V9_REQUIREMENTS, triages: [] }),
      'utf8',
    )
    store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
    await store.load()
    taskStore = new QueueTaskStore({ repo: new JsonQueueRepository({ workspaceRoot: dir }), now: () => 1_000 })
    // 「迁移」动作：同一批 TaskRecord 落成各需求 queue.json（与迁移脚本写入契约同形）
    for (const reqId of REQ_IDS) {
      await taskStore.createMany(reqId, V8_TASKS.filter(t => t.requirementId === reqId))
    }
    handler = createReqboardHandler({ store, taskStore, now: () => 1_000, cwd: dir })
  })
  afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

  function fakeReq(url: string): any {
    const req = new EventEmitter() as any
    req.url = url
    req.method = 'GET'
    req[Symbol.asyncIterator] = async function* () { /* no body */ }
    return req
  }
  function fakeRes(): any {
    const res: any = new EventEmitter()
    res.statusCode = 0
    res.payload = undefined
    res.writeHead = (code: number) => { res.statusCode = code; return res }
    res.end = (text?: string) => { res.payload = text === undefined ? undefined : JSON.parse(text); return res }
    return res
  }
  async function get(url: string) {
    const res = fakeRes()
    await handler(fakeReq(`/dashboard/api/reqboard${url}`), res)
    return res
  }
  const stateOf = async () => {
    const res = await get('/state')
    expect(res.statusCode).toBe(200)
    return res.payload.data as {
      revision: number
      requirements: readonly RequirementRecord[]
      tasks: readonly Record<string, unknown>[]
      ready: Record<string, readonly string[]>
    }
  }

  // ── a) 任务级逐字节（独立可判）────────────────────────────────────────────
  it('a) 任务级逐字节：按 id 配对 + 键集相等 + 值相等 + 不含 layer', async () => {
    const data = await stateOf()
    const expected = before.stateTasks()
    expect(data.tasks.length).toBe(expected.length)
    const byId = new Map(data.tasks.map(t => [String(t.id), t]))
    const mismatched: string[] = []
    for (const exp of expected) {
      const act = byId.get(String(exp.id))
      expect(act, '缺少任务 ' + String(exp.id)).toBeDefined()
      if (JSON.stringify(Object.keys(act!).sort()) !== JSON.stringify(Object.keys(exp).sort())) mismatched.push(String(exp.id) + ':键集')
      else if (JSON.stringify(act) !== JSON.stringify(exp)) mismatched.push(String(exp.id) + ':值')
    }
    expect(mismatched).toEqual([])
  })

  it('a) 任务对象不含队列专有派生字段 layer（D3 端口出口契约）', async () => {
    const data = await stateOf()
    expect(data.tasks.filter(t => Object.prototype.hasOwnProperty.call(t, 'layer')).map(t => t.id)).toEqual([])
    // 端口出口：get / listByRequirement / listAll 都不带 layer；readQueue（队列文件视图）才带
    for (const reqId of REQ_IDS) {
      for (const t of await taskStore.listByRequirement(reqId)) {
        expect(Object.prototype.hasOwnProperty.call(t, 'layer')).toBe(false)
      }
    }
    const file = await taskStore.readQueue(REQ_IDS[0]!)
    expect(file!.tasks.every(t => typeof t.layer === 'number')).toBe(true)
  })

  // ── b) 需求内相对顺序（独立可判）──────────────────────────────────────────
  it('b) 需求内相对顺序一致：每个需求的 id 序列与迁移前相同', async () => {
    const data = await stateOf()
    const mismatched: Record<string, unknown> = {}
    for (const reqId of REQ_IDS) {
      const actual = data.tasks.filter(t => t.requirementId === reqId).map(t => t.id)
      const expected = before.idsOf(reqId)
      if (JSON.stringify(actual) !== JSON.stringify(expected)) mismatched[reqId] = { actual, expected }
    }
    expect(mismatched).toEqual({})
  })

  // ── c) 计数（独立可判）────────────────────────────────────────────────────
  it('c) 计数 = 源台账现算值（总数 + 各需求数）', async () => {
    const data = await stateOf()
    expect(data.tasks.length).toBe(V8_TASKS.length)
    for (const reqId of REQ_IDS) {
      expect(data.tasks.filter(t => t.requirementId === reqId).length).toBe(before.countOf(reqId))
    }
  })

  // ── d) 其余字段逐字节（独立可判）──────────────────────────────────────────
  it('d) 响应其余字段逐字节相等（requirements / ready 映射 / revision 语义）', async () => {
    const data = await stateOf()
    // 注意两点（都不属"任务换数据源"的回归面）：
    //  ① `/state` 开头跑产物自动发现（`syncAllReqArtifacts`），它会**就地登记产物 → 改需求记录**、
    //     并可能 bump 台账 revision —— 这是改造前就有的行为。故 requirements 的比较基线取
    //     「请求后的台账快照」而不是夹具原件；要断言的是**路由忠实返回台账**，与任务数据源无关。
    //  ② 响应里的 revision 就是**台账 revision**（不是队列 revision）。
    expect(data.revision).toBe(store.snapshot().revision)
    expect(JSON.stringify(data.requirements)).toBe(JSON.stringify(store.snapshot().requirements))
    // 任务派生的 ready 映射必须与迁移前**逐字节一致**（这条才是本需求真正碰的字段）
    expect(data.ready).toEqual(before.readyMap())
  })

  it('d) /requirements/summary 的任务计数逐字段一致', async () => {
    const res = await get('/requirements/summary')
    expect(res.statusCode).toBe(200)
    const rows = (res.payload.data as { requirements: Record<string, unknown>[] }).requirements
    const mismatched: Record<string, unknown> = {}
    let compared = 0
    for (const reqId of REQ_IDS) {
      const row = rows.find(r => r.id === reqId)
      // 摘要只列**进行中**需求（`isActiveRequirement` 过滤）→ 已归档/完成的不出现，属正确行为而非回归
      if (row === undefined) continue
      compared += 1
      const exp = before.summaryOf(reqId)
      const act = { tasksDone: row.tasksDone, tasksActive: row.tasksActive, tasksTotal: row.tasksTotal }
      if (JSON.stringify(act) !== JSON.stringify(exp)) mismatched[reqId] = { act, exp }
    }
    expect(compared, '至少应有一个夹具需求出现在摘要里，否则本用例没验到东西').toBeGreaterThan(0)
    expect(mismatched).toEqual({})
  })

  it('d) /requirements/:id/stages 的节点任务 id 序列与迁移前一致', async () => {
    const mismatched: Record<string, unknown> = {}
    for (const reqId of REQ_IDS) {
      const res = await get(`/requirements/${reqId}/stages`)
      expect(res.statusCode, reqId + ' stages 未返回 200').toBe(200)
      const overview = res.payload.data as {
        stages: readonly { stage: string; body?: { tasks?: readonly Record<string, unknown>[] } }[]
      }
      for (const stage of ['decomposing', 'implementing']) {
        const node = overview.stages.find(s => s.stage === stage)
        const tasks = node?.body?.tasks ?? []
        if (tasks.length === 0) continue // 该需求未走到该节点 → 无任务，跳过（不是回归）
        const actual = tasks.map(t => String(t.id))
        const expected = before.idsOf(reqId)
        if (JSON.stringify(actual) !== JSON.stringify(expected)) mismatched[reqId + '/' + stage] = { actual, expected }
        if (tasks.some(t => Object.prototype.hasOwnProperty.call(t, 'layer'))) mismatched[reqId + '/' + stage + ':layer'] = true
      }
    }
    expect(mismatched).toEqual({})
  })

  // ── e) 跨需求全局顺序：**不要求**（负向固化 D8 裁定）──────────────────────
  it('e) 不要求跨需求全局顺序：/state.tasks 按 listAll() 契约重排，且**据此不再断言全序**', async () => {
    const data = await stateOf()
    const actualGlobal = data.tasks.map(t => String(t.id))
    const beforeGlobal = before.stateTasks().map(t => String(t.id))
    // 契约序 = requirementId 字典序分组（组内保原序）
    const contractOrder = [...REQ_IDS].sort().flatMap(reqId => before.idsOf(reqId))
    expect(actualGlobal).toEqual(contractOrder)
    // 真实数据确实"被切断" ⇒ 全局序与迁移前**不同**（这正是 D8 把它从验收里去掉的原因）
    expect(actualGlobal).not.toEqual(beforeGlobal)
    // 负向固化：任何人"顺手"把全序断言加回来都会先在这里看到这条注释与断言
    expect(REQ_IDS.length).toBeGreaterThanOrEqual(2)
  })
})
