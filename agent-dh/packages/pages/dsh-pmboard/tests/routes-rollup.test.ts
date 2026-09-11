/**
 * 路由层自动推进集成测试 —— 证明「自动推进」在 HTTP 全链路上真的生效
 * （不止纯函数正确）：任务状态落定后，所属需求被同一笔 mutate 推进到验收。
 * 用假 req/res 直连 createReqboardHandler（不起真服务器）。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { ReqboardStore } from '../src/host/store.js'
import { createReqboardHandler } from '../src/host/routes.js'

let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-routes-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

/** 假请求：带 url/method（分派器读），且可被 readBody 的 for await 消费。 */
function fakeReq(body: unknown, url: string): any {
  const req = new EventEmitter() as any
  req.url = url
  req.method = 'POST'
  req[Symbol.asyncIterator] = async function* () {
    if (body !== undefined) yield Buffer.from(JSON.stringify(body), 'utf8')
  }
  return req
}

/** 假响应：收集 status + JSON。 */
function fakeRes(): any {
  const res: any = new EventEmitter()
  res.statusCode = 0
  res.payload = undefined
  res.writeHead = (code: number) => { res.statusCode = code; return res }
  res.end = (text?: string) => { res.payload = text === undefined ? undefined : JSON.parse(text); return res }
  return res
}

async function post(handler: any, url: string, body: unknown) {
  const res = fakeRes()
  await handler(fakeReq(body, `/dashboard/api/reqboard${url}`), res)
  return res
}

describe('路由层自动推进（R2 实施完成 → 验收）', () => {
  it('全部任务 done 后，需求在同一笔 mutate 内自动进 accepting', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    // 建需求 → 手工推进到 implementing（人工闸门由 actor=human 满足）
    const created = await post(handler, '/req/create', { title: '自动推进验证' })
    const reqId = created.payload.data.id
    await post(handler, '/req/move', { id: reqId, to: 'reviewing', actor: 'human' })
    await post(handler, '/req/move', { id: reqId, to: 'decomposing', actor: 'human' })
    await post(handler, '/req/move', { id: reqId, to: 'implementing', actor: 'human' })

    const t1 = await post(handler, '/task/create', { requirementId: reqId, title: '任务一', phase: 'implement', side: 'backend', dependsOn: [], scope: { apis: [], tables: [], files: [] } })
    const t2 = await post(handler, '/task/create', { requirementId: reqId, title: '任务二', phase: 'test', side: 'backend', dependsOn: [], scope: { apis: [], tables: [], files: [] } })
    const task1 = t1.payload.data.id
    const task2 = t2.payload.data.id

    // 完成第一个任务：需求仍在 implementing（未全部完成）
    await post(handler, '/task/move', { id: task1, to: 'in_progress' })
    await post(handler, '/task/move', { id: task1, to: 'testing' })
    await post(handler, '/task/move', { id: task1, to: 'in_review' })
    await post(handler, '/task/move', { id: task1, to: 'done', actor: 'human' })
    let req = await store.read(l => l.requirements.find(r => r.id === reqId)!)
    expect(req.status).toBe('implementing')

    // 完成最后一个任务 → 派生推进自动发生（无需任何额外调用）
    await post(handler, '/task/move', { id: task2, to: 'in_progress' })
    await post(handler, '/task/move', { id: task2, to: 'testing' })
    await post(handler, '/task/move', { id: task2, to: 'in_review' })
    const res = await post(handler, '/task/move', { id: task2, to: 'done', actor: 'human' })
    expect(res.statusCode).toBe(200)

    req = await store.read(l => l.requirements.find(r => r.id === reqId)!)
    expect(req.status).toBe('accepting')
    expect(req.updatedBy.kind).toBe('system')
    expect(req.comments.some(c => c.body.includes('[自动推进] implementing → accepting'))).toBe(true)
  })

  it('人工闸门仍把守：任务全 done 也不会自动越到 done（验收必须人点）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const created = await post(handler, '/req/create', { title: '闸门验证' })
    const reqId = created.payload.data.id
    for (const to of ['reviewing', 'decomposing', 'implementing']) {
      await post(handler, '/req/move', { id: reqId, to, actor: 'human' })
    }
    const t = await post(handler, '/task/create', { requirementId: reqId, title: '唯一任务', phase: 'implement', side: 'doc', dependsOn: [], scope: { apis: [], tables: [], files: [] } })
    const taskId = t.payload.data.id
    for (const to of ['in_progress', 'testing', 'in_review']) {
      await post(handler, '/task/move', { id: taskId, to })
    }
    await post(handler, '/task/move', { id: taskId, to: 'done', actor: 'human' })

    const req = await store.read(l => l.requirements.find(r => r.id === reqId)!)
    expect(req.status).toBe('accepting') // 派生链停在验收
    // 人工闸门（取消/归档）仍代码级拒绝
    const cancel = await post(handler, '/req/move', { id: reqId, to: 'canceled', actor: 'system' })
    expect(cancel.statusCode).toBe(403)
    expect(cancel.payload.code).toBe('human_gate')
    // agent 可自行完成验收（用户裁定：不需要人点中间步骤）
    const done = await post(handler, '/req/move', { id: reqId, to: 'done', actor: 'agent' })
    expect(done.statusCode).toBe(200)
    expect((await store.read(l => l.requirements.find(r => r.id === reqId)!)).status).toBe('done')
  })
})
