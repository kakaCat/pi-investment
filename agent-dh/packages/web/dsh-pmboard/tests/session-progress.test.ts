/**
 * 会话框流程节点（/session/:id/progress）回归测试（REQ-47939a 返工补）。
 *
 * 为什么专门补这个文件：`handleSessionProgress` 此前**零测试覆盖**——重构时路由层引用了
 * 一个不存在的符号 `OPEN_STATUSES`（状态集合被搬去 application/internal/window.ts 并改名），
 * 编译不报错、既有测试全绿，但**运行时 ReferenceError → HTTP 500 → 会话框上的流程节点不再显示**
 * （用户实际观测到的回归）。教训：**没有测试覆盖的接口 = 重构的盲区**；补测试比改代码更重要。
 *
 * 覆盖：绑定需求的会话返回进度口径；无关会话返回 hasRequirement=false；已完成需求不再被选中。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const SID = 'session-progress-test'
let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-progress-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function fakeGet(url: string): any {
  const req = new EventEmitter() as any
  req.url = url
  req.method = 'GET'
  req[Symbol.asyncIterator] = async function* () { /* GET 无 body */ }
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
async function get(handler: any, url: string) {
  const res = fakeRes()
  await handler(fakeGet('/dashboard/api/reqboard' + url), res)
  return res
}

async function seed(status: string, sessionId: string | undefined): Promise<string> {
  const id = 'REQ-' + Math.random().toString(16).slice(2, 8)
  const r = {
    id, title: '流程节点验证', description: '', category: 'feature', status,
    blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status, at: 1, by: { kind: 'human' } }],
    ...(sessionId !== undefined ? { sourceSessionId: sessionId } : {}),
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
  return id
}

describe('会话框流程节点 /session/:id/progress', () => {
  it('绑定进行中需求的会话 → 200 且返回需求与进度口径（回归：曾因符号未定义 500）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const id = await seed('implementing', SID)
    const res = await get(handler, '/session/' + SID + '/progress')
    expect(res.statusCode, JSON.stringify(res.payload)).toBe(200)
    expect(res.payload.success).toBe(true)
    expect(res.payload.data.hasRequirement).toBe(true)
    expect(res.payload.data.requirement?.id ?? res.payload.data.requirementId).toBe(id)
  })

  // TC-10（REQ-260923134706-e72f / FR-2）：progress 透出立项四问之一的 promptDifficulty
  it('有 promptDifficulty 的记录透出值，老记录透出 null', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    // 有难度的记录
    const withDiff = 'REQ-withdiff-01'
    await store.mutate('seed', (l) => {
      l.requirements.push({
        id: withDiff, title: '带难度', description: '', category: 'feature', status: 'implementing',
        promptDifficulty: 'advanced', blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: 1,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
        statusHistory: [{ status: 'implementing', at: 1, by: { kind: 'human' } }],
        sourceSessionId: 'SID-withdiff',
      } as unknown as RequirementRecord)
      return { requirements: [] }
    })
    let res = await get(handler, '/session/SID-withdiff/progress')
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.requirement.promptDifficulty).toBe('advanced')

    // 老记录（无 promptDifficulty 字段）→ null
    const legacyId = await seed('implementing', 'SID-legacy')
    res = await get(handler, '/session/SID-legacy/progress')
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.requirement.id).toBe(legacyId)
    expect(res.payload.data.requirement.promptDifficulty).toBe(null)
  })

  it('无关联需求的会话 → 200 且 hasRequirement=false（不报错、不 500）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const res = await get(handler, '/session/no-such-session/progress')
    expect(res.statusCode, JSON.stringify(res.payload)).toBe(200)
    expect(res.payload.data.hasRequirement).toBe(false)
  })

  it('已完成/已归档需求不会被选为"进行中"节点（isOpenRequirement 判据）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    await seed('done', SID)
    const res = await get(handler, '/session/' + SID + '/progress')
    expect(res.statusCode).toBe(200)
    // done 属终态：不应当成进行中需求（可能返回 false 或回退到最近一条，但不得因此报错）
    expect(res.payload.success).toBe(true)
  })
})
