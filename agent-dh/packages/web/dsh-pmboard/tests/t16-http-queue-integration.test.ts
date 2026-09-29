/**
 * t-6df9a0（看板实测回归·**联调**）——reqboard HTTP 面 × 队列存储的接口联调用例。
 *
 * 为什么单独一个用例：生产实例上的联调探针（`notes/board-live/integration-probe.mjs`）只打**只读接口**
 * 与**写接口的拒绝路径**（对活台账零写）；写接口的**成功路径**（建卡 → 流转 → 改卡，任务只进
 * `queue.json`、台账不再有 `tasks`）必须在一个可写的真实环境里跑完 —— 本用例用
 * **真实 handler + 真实台账/队列文件**（`os.tmpdir()` 临时工作区）跑，活数据零接触。
 *
 * 请求样例与期望（与探针同口径：真值取磁盘文件，不取被测代码的内存快照）：
 *   POST /task/create  → 200，队列多一条（含 layer），台账仍无 `tasks` 键
 *   POST /task/move    → 200，队列 status 更新、下游 ready 解锁（V-5 派生视图重算）
 *   POST /task/update  → 200，队列字段更新 + version +1
 *   GET  /state        → 616 口径同款：tasks = Σ 队列文件、出口无 `layer`、ready 与队列一致
 *   全链收口：两卡 done 后 → 需求 rollup 由 system 推进到 accepting（台账只存需求，任务在队列）
 */
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { JsonLedgerRepository } from '../src/adapters/JsonLedgerRepository.js'
import { JsonQueueRepository } from '../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../src/repositories/QueueTaskStore.js'
import { createReqboardHandler } from '../src/http/routes.js'

let root: string
let store: JsonLedgerRepository
let taskStore: QueueTaskStore
let handler: ReturnType<typeof createReqboardHandler>
let queueFile: (reqId: string) => string

/** 假请求（与 tests/http/file-route.test.ts 同款）：url/method + 可被 readBody 消费的 body。 */
function fakeReq(method: string, url: string, body?: unknown): any {
  const req = new EventEmitter() as any
  req.url = `/dashboard/api/reqboard${url}`
  req.method = method
  req[Symbol.asyncIterator] = async function* () {
    if (body !== undefined) yield Buffer.from(JSON.stringify(body), 'utf8')
  }
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
const get = async (url: string) => { const res = fakeRes(); await handler(fakeReq('GET', url), res); return res }
const post = async (url: string, body: unknown) => { const res = fakeRes(); await handler(fakeReq('POST', url, body), res); return res }

/** 磁盘真值：队列文件（含 layer）＋台账文本。 */
const readQueue = (reqId: string): any => JSON.parse(readFileSync(queueFile(reqId), 'utf8'))
const readLedger = (): { requirements: any[]; revision: number } =>
  JSON.parse(readFileSync(join(root, 'dsh-reqboard.json'), 'utf8')) as { requirements: any[]; revision: number }
const ledgerHasTasksKey = (): boolean =>
  Object.prototype.hasOwnProperty.call(JSON.parse(readFileSync(join(root, 'dsh-reqboard.json'), 'utf8')) as Record<string, unknown>, 'tasks')

beforeEach(async () => {
  root = mkdtempSync(join(tmpdir(), 'pmboard-t16-integrate-'))
  store = new JsonLedgerRepository({ file: join(root, 'dsh-reqboard.json') })
  const queueRepo = new JsonQueueRepository({ workspaceRoot: root })
  taskStore = new QueueTaskStore({ repo: queueRepo, now: () => Date.now() })
  handler = createReqboardHandler({ store, taskStore, now: () => Date.now(), cwd: root })
  queueFile = (reqId) => join(root, 'docs/requirements', reqId, 'queue.json')
})
afterEach(() => { rmSync(root, { recursive: true, force: true }) })

/**
 * 建一个 implementing 需求（联调前置夹具）。
 * 走真实 `POST /req/create` 建卡，再直接把状态置为 implementing —— 绕开设计/拆分人工门
 * （那几道门的联调不属本卡，本卡只联调任务 → 队列这条链路）。
 */
async function seedRequirement(): Promise<string> {
  const created = await post('/req/create', { title: '联调夹具需求' })
  expect(created.statusCode).toBe(200)
  const id = created.payload.data.id as string
  // mutate 语义：变更器拿 draft **原地改**，返回值只用于变更通知（不原地改 = 静默不落盘）
  await store.mutate('requirement-updated', (ledger) => {
    const r = ledger.requirements.find(x => x.id === id)
    if (r !== undefined) r.status = 'implementing'
    return { requirements: r === undefined ? [] : [r] }
  })
  return id
}

describe('t16 联调：reqboard HTTP 面 × queue.json（真实 handler + 真实文件）', () => {
  it('建卡/流转/改卡全链：任务只进 queue.json，台账无 tasks，读回与磁盘真值一致', async () => {
    const reqId = await seedRequirement()

    // ── 样例 1：POST /task/create（A 无依赖、B 依赖 A）─────────────────────
    const a = await post('/task/create', {
      requirementId: reqId, title: '联调任务A', phase: 'implement', side: 'backend',
      acceptance: 'A 的验收', dependsOn: [], scope: { apis: [], tables: [], files: [] },
    })
    expect(a.statusCode).toBe(200)
    expect(a.payload.success).toBe(true)
    const aId = a.payload.data.id as string
    // 期望：响应无 layer（TaskStore 出口剥离 D3）；磁盘队列有 layer（派生字段在文件里）
    expect(Object.prototype.hasOwnProperty.call(a.payload.data, 'layer')).toBe(false)
    let q = readQueue(reqId)
    expect(q.tasks).toHaveLength(1)
    expect(q.tasks[0].id).toBe(aId)
    expect(q.tasks[0].layer).toBe(0)
    expect(q.ready).toEqual([aId])

    const b = await post('/task/create', {
      requirementId: reqId, title: '联调任务B', phase: 'test', side: 'backend',
      acceptance: 'B 的验收', dependsOn: [aId], scope: { apis: [], tables: [], files: [] },
    })
    expect(b.statusCode).toBe(200)
    const bId = b.payload.data.id as string
    q = readQueue(reqId)
    expect(q.tasks.map((t: any) => t.id)).toEqual([aId, bId])
    expect(q.tasks.find((t: any) => t.id === bId).layer).toBe(1) // 拓扑分层：B 在下一层
    expect(q.ready).toEqual([aId]) // 下游未解锁
    expect(q.edges).toEqual([{ from: aId, to: bId }])
    // 期望：任务不进台账（v9 无 tasks 键）
    expect(ledgerHasTasksKey()).toBe(false)

    // ── 样例 2：GET /state（读回与磁盘真值逐字段一致）─────────────────────
    const state = await get('/state')
    expect(state.statusCode).toBe(200)
    expect(state.payload.data.tasks.map((t: any) => t.id)).toEqual([aId, bId])
    expect(state.payload.data.tasks.some((t: any) => 'layer' in t)).toBe(false)
    expect(state.payload.data.ready[reqId]).toEqual([aId])
    const diskA = readQueue(reqId).tasks.find((t: any) => t.id === aId)
    const apiA = state.payload.data.tasks.find((t: any) => t.id === aId)
    for (const t of readQueue(reqId).tasks) {
      const api = state.payload.data.tasks.find((x: any) => x.id === t.id)
      const stripped = { ...t }
      delete stripped.layer
      expect(api).toEqual(stripped)
    }
    expect(apiA.title).toBe(diskA.title)

    // ── 样例 3：POST /task/move 把 A 推到 done（legacy 五段合法边）────────
    for (const to of ['in_progress', 'testing', 'in_review', 'done']) {
      const moved = await post('/task/move', { id: aId, to, actor: 'human' })
      expect(moved.statusCode).toBe(200)
      expect(moved.payload.data.id).toBe(aId)
      expect(moved.payload.data.status).toBe(to)
      expect(moved.payload.data).not.toHaveProperty('layer')
    }
    q = readQueue(reqId)
    expect(q.tasks.find((t: any) => t.id === aId).status).toBe('done')
    // 期望（V-5）：A done 后 ready 解锁下游 B，statusHistory 也已随状态迁移记录
    expect(q.ready).toEqual([bId])
    expect(q.tasks.find((t: any) => t.id === aId).statusHistory.map((e: any) => e.status)).toContain('done')

    const state2 = await get('/state')
    expect(state2.payload.data.ready[reqId]).toEqual([bId])

    // ── 样例 4：POST /task/update 改卡（字段落队列 + version 递增）────────
    const beforeVersion = readQueue(reqId).tasks.find((t: any) => t.id === bId).version
    const updated = await post('/task/update', { id: bId, acceptance: 'B 的验收（联调改后）' })
    expect(updated.statusCode).toBe(200)
    expect(updated.payload.data.acceptance).toBe('B 的验收（联调改后）')
    const bDisk = readQueue(reqId).tasks.find((t: any) => t.id === bId)
    expect(bDisk.acceptance).toBe('B 的验收（联调改后）')
    expect(bDisk.version).toBe(beforeVersion + 1)

    // ── 样例 5：B 也 done → 需求 rollup 由 system 推进到 accepting ─────────
    for (const to of ['in_progress', 'testing', 'in_review', 'done']) {
      const moved = await post('/task/move', { id: bId, to, actor: 'human' })
      expect(moved.statusCode).toBe(200)
    }
    const req = readLedger().requirements.find((r: any) => r.id === reqId)
    expect(req.status).toBe('accepting')
    expect(req.updatedBy.kind).toBe('system')
    expect(ledgerHasTasksKey()).toBe(false)
    expect(readQueue(reqId).tasks.every((t: any) => t.status === 'done')).toBe(true)

    // ── 样例 6：错误契约（与生产探针同款，逐条对齐 code）──────────────────
    const notFoundTask = await post('/task/move', { id: 't-deadbeef0001', to: 'done' })
    expect(notFoundTask.statusCode).toBe(404)
    expect(notFoundTask.payload).toMatchObject({ success: false, code: 'not_found' })

    const badTransition = await post('/task/move', { id: aId, to: 'todo', actor: 'human' })
    expect(badTransition.statusCode).toBe(400)
    expect(badTransition.payload.code).toBe('invalid_transition')

    const badStatus = await post('/task/move', { id: aId, to: '不存在的状态' })
    expect(badStatus.statusCode).toBe(400)
    expect(badStatus.payload.code).toBe('invalid_input')

    const orphanCreate = await post('/task/create', { requirementId: 'REQ-does-not-exist-000000', title: 'x', phase: 'implement', side: 'backend' })
    expect(orphanCreate.statusCode).toBe(404)
    expect(orphanCreate.payload.code).toBe('not_found')
    expect(existsSync(join(root, 'docs/requirements/REQ-does-not-exist-000000/queue.json'))).toBe(false)

    // ── 样例 7：阶段视图任务投影与队列一致（StageTaskRef 契约字段）─────────
    const stages = await get(`/requirements/${reqId}/stages`)
    expect(stages.statusCode).toBe(200)
    const implNode = stages.payload.data.stages.find((s: any) => s.stage === 'implementing')
    const implIds = implNode.body.tasks.map((t: any) => t.id)
    expect(implIds).toEqual([aId, bId])
    for (const t of readQueue(reqId).tasks) {
      const ref = implNode.body.tasks.find((x: any) => x.id === t.id)
      expect(ref.title).toBe(t.title)
      expect(ref.status).toBe(t.status)
      expect(ref.dependsOn).toEqual(t.dependsOn)
      expect(ref.acceptance).toBe(t.acceptance)
      expect(ref.executions).toEqual(t.executions)
      expect(ref).not.toHaveProperty('layer')
    }
  })

  it('队列损坏时的读方行为：/state 不崩、该需求任务缺席、损坏文件被隔离（不冒充空队列为正常）', async () => {
    // 关键次序：先把损坏的 queue.json 放到盘上，**再**让服务端第一次读它
    //（QueueTaskStore 读缓存优先，先读写过的需求不会重读磁盘——故本用例必须用全新需求）
    const reqId = await seedRequirement()
    const dir = join(root, 'docs/requirements', reqId)
    mkdirSync(dir, { recursive: true })
    writeFileSync(queueFile(reqId), '{ 坏 JSON', 'utf8')

    const state = await get('/state')
    expect(state.statusCode).toBe(200)
    expect(state.payload.success).toBe(true)
    expect(state.payload.data.tasks.filter((t: any) => t.requirementId === reqId)).toHaveLength(0)
    // 损坏文件被隔离改名（QueueRepository 的容错口径），不拖垮看板
    const quarantined = readdirSync(dir).filter((f: string) => f.includes('.corrupt-'))
    expect(quarantined.length).toBe(1)
    // 该需求仍在台账（需求记录不受队列损坏影响），只是任务视图为空
    expect(readLedger().requirements.some((r: any) => r.id === reqId)).toBe(true)
  })
})
