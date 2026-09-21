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
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { stubDocFile } from './helpers/tool-deps.js'

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
    await post(handler, '/req/move', { id: reqId, to: 'brainstorming', actor: 'human' })
    await post(handler, '/req/move', { id: reqId, to: 'design', actor: 'human' })
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

  it('decompose 后需求停在 decomposing（五门裁定：拆分清单须人确认）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const created = await post(handler, '/req/create', { title: '五门验证' })
    const reqId = created.payload.data.id
    // 给需求挂上 sourceSessionId（模拟窗口绑定）
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements.find(x => x.id === reqId)!
      r.sourceSessionId = 'session-test'
      return { requirements: [r] }
    })
    await post(handler, '/req/move', { id: reqId, to: 'brainstorming', actor: 'human' })
    await post(handler, '/req/move', { id: reqId, to: 'design', actor: 'human' })
    // 2026-09-21：拆分计划在拆分阶段提交（legacy 无产物 → 门不硬拦，可直接推进）
    await post(handler, '/req/move', { id: reqId, to: 'decomposing', actor: 'human' })
    // 提交计划并批准
    const { definePlanSubmitTool, defineDecomposeTool } = await import('./helpers/tool-deps.js')
    const planTool = definePlanSubmitTool({ store, now: () => Date.now() } as never)
    const decomposeTool = defineDecomposeTool({ store, now: () => Date.now() } as never)
    // REQ-2d1c74 FR-5：plan_submit 起要求提交路径真实落盘
    stubDocFile('docs/requirements/' + reqId + '/decomposition.md')
    await planTool.execute({
      path: 'docs/requirements/' + reqId + '/decomposition.md', summary: 's',
      tasks: [{ key: 'a', title: '任务A', phase: 'implement', side: 'backend', acceptance: '单测通过', implementation: '改 a.ts' }],
    }, { agent: { id: 'session-test' } })
    await post(handler, '/req/plan/approve', { id: reqId })
    const out = (await decomposeTool.execute({}, { agent: { id: 'session-test' } } as never)) as { requirement_status: string }
    expect(out.requirement_status).toBe('decomposing')
    // 五门裁定：decomposing>implementing 须人确认拆分清单
    const req = await store.read(l => l.requirements.find(r => r.id === reqId)!)
    expect(req.status).toBe('decomposing')
  })

  it('人工闸门仍把守：任务全 done 停在验收；验收通过即直接归档（REQ-9f4a44）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const created = await post(handler, '/req/create', { title: '闸门验证' })
    const reqId = created.payload.data.id
    for (const to of ['brainstorming', 'design', 'decomposing', 'implementing']) {
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
    // 验收通过是人工审核：agent 点不动，只有人能过；通过后直接 archived（无 done）
    const agentArchive = await post(handler, '/req/move', { id: reqId, to: 'archived', actor: 'agent' })
    expect(agentArchive.statusCode).toBe(403)
    expect(agentArchive.payload.code).toBe('human_gate')
    const archived = await post(handler, '/req/move', { id: reqId, to: 'archived', actor: 'human' })
    expect(archived.statusCode).toBe(200)
    expect((await store.read(l => l.requirements.find(r => r.id === reqId)!)).status).toBe('archived')
  })
})
