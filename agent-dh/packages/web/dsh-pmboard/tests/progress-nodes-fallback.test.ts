import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { taskStoreAt } from './queue/route-deps.js'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { type ReqboardLedger, type TaskRecord, type TokenBuckets } from '../src/shared/protocol.js'

const SID = 'session-w-001'
const B = (n: number): TokenBuckets => ({ uncachedInputTokens: n, outputTokens: n * 2, cacheReadTokens: n * 10, cacheWriteTokens: 0 })
const snap = (n: number) => ({ sessionId: SID, at: n, totals: B(n), source: 'projection' as const })

// 关键场景：需求没有 byStage（功能上线前创建），但任务有真实执行差值
function ledger(): ReqboardLedger {
  return {
    schemaVersion: 9, revision: 1,
    requirements: [{
      id: 'REQ-abc123', title: '旧需求', description: 'd', category: 'feature', status: 'accepting',
      blocked: false, sourceSessionId: SID, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    }],
    triages: [],
  }
}

/**
 * v9：任务唯一存储 = 队列（台账已无 `tasks` 通道）。
 * 原判据 = "ledger.tasks 里带 tokenUsage 的执行"；新判据 = "队列里同一张卡的同一条执行"，
 * 装配形状（B(3) 差值）逐字保留，只是数据源换成 `TaskStore`。
 */
const SEED_TASK: TaskRecord = {
  id: 't-abc123', requirementId: 'REQ-abc123', title: '任务', description: 'd', phase: 'implement', side: 'backend',
  dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: 'a', context: '', status: 'done',
  blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: 1,
  createdBy: { kind: 'agent', sessionId: SID }, updatedBy: { kind: 'agent', sessionId: SID }, statusHistory: [],
  executions: [{ id: 'e-abc123', sessionId: SID, trigger: 'manual', startedAt: 1, endedAt: 2, outcome: 'succeeded',
    tokenUsage: { start: snap(2), end: snap(5), delta: B(3) } }],
}

let dir: string
let store: ReqboardStore
beforeEach(async () => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-prognodes-'))
  store = new ReqboardStore({ file: join(dir, 'l.json') })
  await store.replaceAll('seed', ledger())
  // v9：任务落队列（真实 TaskStore + 临时目录 = 与 handler 的 taskStore 同源）
  await taskStoreAt(dir).createMany('REQ-abc123', [{ ...SEED_TASK }])
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function fakeRes(): any {
  const res: any = new EventEmitter()
  res.statusCode = 0; res.payload = undefined
  res.writeHead = (c: number) => { res.statusCode = c; return res }
  res.end = (t?: string) => { res.payload = t === undefined ? undefined : JSON.parse(t); return res }
  return res
}
async function get(handler: any, url: string) {
  const req = new EventEmitter() as any
  req.url = '/dashboard/api/reqboard' + url; req.method = 'GET'
  req[Symbol.asyncIterator] = async function* () { /* GET 无体 */ }
  const res = fakeRes()
  await handler(req, res)
  return res
}

describe('REQ-a33899 · 会话顶部每节点 token（无节点快照时用执行差值兜底）', () => {
  it('implementing 节点用任务执行差值兜底 → 会话顶部能显示数字', async () => {
    const handler = createReqboardHandler({ taskStore: taskStoreAt(dir), store, now: () => Date.now() })
    const res = await get(handler, '/session/' + SID + '/progress')
    expect(res.statusCode).toBe(200)
    const nodes = res.payload.data.nodes
    const impl = nodes.find((n: any) => n.key === 'implementing')
    expect(impl.tokens.total).toBe(39) // B(3) 三桶和
    const draft = nodes.find((n: any) => n.key === 'draft')
    expect(draft.tokens).toBeUndefined() // 无数据 → 不输出「0」噪音
  })

  it('无任何执行差值时，所有节点都不输出 tokens（诚实：没有可算的数据）', async () => {
    await store.replaceAll('seed2', ledger())
    // 原判据 = 台账 `tasks: []`（没有任务）；v9 下台账已无 tasks 通道，等价判据 = **队列里那张卡没有执行差值**：
    // 本条要验的是"没有可算的执行差值时不输出 0 噪音"，清掉 `executions` 即为该语义。
    // ⚠️ 不用 `mutate(reqId, () => [])`：那会命中 `QueueTaskStore.mutate` 的
    // "纯删除不产生 changed → 提前返回不写盘"取舍（已在汇报中报 Lead 为 src 侧缺陷），
    // 于是队列文件根本不变、断言假红。
    await taskStoreAt(dir).mutate('REQ-abc123', (tasks) => tasks.map(t => ({ ...t, executions: [] })))
    const handler = createReqboardHandler({ taskStore: taskStoreAt(dir), store, now: () => Date.now() })
    const res = await get(handler, '/session/' + SID + '/progress')
    const nodes = res.payload.data.nodes
    expect(nodes.every((n: any) => n.tokens === undefined)).toBe(true)
  })
})
