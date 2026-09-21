/**
 * 看板「确认产物」通道纳入切面（REQ-e3b6a0 t9 / FR-9 / AC-9.1 · AC-9.2 · AC-9.3）。
 *
 * 锁三件事：
 *  ① 窗口在线 → 落章 + **确认即推进** + 触发后置链（返回体 advanced=true 且 delivered=true）；
 *  ② 窗口离线 → **只落章**（advanced=false，note 如实说明"窗口不在线"），不伪造推进成功；
 *  ③ 幂等：再次确认同一产物**不再推进**（护栏 = 确认的产物必须是该门要求的产物）。
 *
 * @module dsh-pmboard/tests/artifact-confirm-board
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { createGatePostChain } from '../src/application/gate/GatePostChain.js'
import { createPendingGateStore } from '../src/application/gate/PendingGate.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-board-001'
const REQ = 'REQ-bd0001'
const DOC = 'docs/requirements/REQ-bd0001/requirement.md'

let dir: string
let store: ReqboardStore

function fakeReq(method: string, url: string, body?: unknown): any {
  const req = new EventEmitter() as any
  req.url = url
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

/** 空 handler 链（只验证"被登记/被跑过"），配可窥探的登记表。 */
function chainSpy() {
  const pending = createPendingGateStore()
  const chain = createGatePostChain({ handlers: [], enabled: true, pending })
  return { chain, pending }
}

async function seed(status: string, withArtifact = true): Promise<void> {
  await store.mutate('seed', (l) => {
    const r = {
      id: REQ, title: '看板确认通道', description: '', category: 'feature', status,
      blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
      ...(withArtifact
        ? {
            artifacts: [{
              stage: 'brainstorming', kind: 'requirement', path: DOC,
              registeredAt: 1, registeredBy: { kind: 'agent', sessionId: W },
            }],
          }
        : {}),
    } as unknown as RequirementRecord
    l.requirements.push(r)
    return { requirements: [r] }
  })
}

function handler(online: boolean, chain: ReturnType<typeof chainSpy>['chain']) {
  return createReqboardHandler({
    store,
    now: () => 1000,
    gateChain: chain,
    agents: () => (online ? { get: () => ({ id: W, session: { fake: true } }) } : { get: () => undefined }),
  })
}

const CONFIRM = '/dashboard/api/reqboard/req/artifact/confirm'
const body = { id: REQ, kind: 'requirement' }

beforeEach(async () => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-board-confirm-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

describe('看板确认：确认即推进 + 链侧投递（AC-9.1）', () => {
  it('窗口在线 → advanced=true、delivered=true，状态已推进，且链路被登记', async () => {
    await seed('brainstorming')
    const { chain, pending } = chainSpy()
    const res = fakeRes()
    await handler(true, chain)(fakeReq('POST', CONFIRM, body), res)
    expect(res.statusCode).toBe(200)
    expect(res.payload.success).toBe(true)
    expect(res.payload.data.advanced).toBe(true)
    expect(res.payload.data.delivered).toBe(true)
    expect(store.snapshot().requirements[0]!.status).toBe('design')
    expect(pending.size()).toBe(0) // 已被 runPending 消费
    expect(chain.stats().executed).toBe(1)
    const comments = store.snapshot().requirements[0]!.comments.map(c => c.body).join(' | ')
    expect(comments).toContain('[自动推进]')
    expect(comments).toContain('[产物确认]')
  })
})

describe('看板确认：窗口离线不伪造（AC-9.2）', () => {
  it('agents.get 返回 undefined → 只落章、advanced=false，note 含「窗口不在线」', async () => {
    await seed('brainstorming')
    const { chain } = chainSpy()
    const res = fakeRes()
    await handler(false, chain)(fakeReq('POST', CONFIRM, body), res)
    expect(res.payload.data.advanced).toBe(false)
    expect(res.payload.data.delivered).toBe(false)
    expect(String(res.payload.data.note)).toContain('窗口不在线')
    expect(store.snapshot().requirements[0]!.status).toBe('brainstorming') // 未推进
    expect(chain.stats().executed).toBe(0)
    // 落章仍然发生（确认本身有效，只是推进与投递留给会话）
    expect(store.snapshot().requirements[0]!.artifacts![0]!.confirmedVia).toBe('board')
  })
})

describe('看板确认：幂等（AC-9.3）', () => {
  it('再次确认同一产物 → 不再推进（护栏：产物须是该门要求的产物）', async () => {
    await seed('brainstorming')
    const { chain } = chainSpy()
    const h = handler(true, chain)
    await h(fakeReq('POST', CONFIRM, body), fakeRes())
    expect(store.snapshot().requirements[0]!.status).toBe('design')
    const res2 = fakeRes()
    await h(fakeReq('POST', CONFIRM, body), res2)
    expect(res2.payload.data.advanced).toBe(false)
    expect(store.snapshot().requirements[0]!.status).toBe('design') // 没被推到 decomposing
  })

  it('未登记的产物 → 400 拒绝（既有语义不变）', async () => {
    await seed('brainstorming', false)
    const { chain } = chainSpy()
    const res = fakeRes()
    await handler(true, chain)(fakeReq('POST', CONFIRM, body), res)
    expect(res.statusCode).toBe(400)
    expect(res.payload.success).toBe(false)
  })
})
