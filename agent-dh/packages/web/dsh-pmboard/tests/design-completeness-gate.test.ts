/**
 * G2 文档集完整性闸门单测（REQ-2d1c74 T-2 · serves FR-2, FR-6）
 *
 * 验收口径（设计 test-cases.md §1 / 任务卡 acceptance）：
 *  - 缺文档（如 use-cases.md）→ design→decomposing 四条转移路径全拒，
 *    错误为 design_doc_incomplete 且 gaps 含缺失文档；
 *  - 任一 design 产物未确认（含"磁盘有但确认后新落的"）→ 拒，gaps 含未确认路径；
 *  - 全交齐且全确认 → 四路径放行；isLegacy 存量需求 → 放行（FR-6）；
 *  - sides/design_exempt front-matter 策略参与①（UC-2）；assertArtifactGates 成组判定（UC-4）。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { EventEmitter } from 'node:events'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { defineMoveTool, defineAskConfirmTool } from './helpers/tool-deps.js'
import { assertArtifactGates } from '../src/application/internal/artifact-gates.js'
import type { RequirementRecord, StageArtifact } from '../src/shared/protocol.js'

const W = 'session-g2-001'
const REQ = 'REQ-g20001'
const DESIGN5 = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']
const DESIGN4 = DESIGN5.slice(0, 4) // 缺 use-cases.md
const DESIGN_DIR = 'docs/requirements/' + REQ + '/design'

let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-g2-gate-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function reqDoc(fmLine?: string): string {
  return '---\nreq: ' + REQ + '\n' + (fmLine === undefined ? '' : fmLine + '\n') + '---\n\n# 需求\n\n## 边界\n不做范围外的事。\n\n## 产品定义\nx\n\n## 用户与角色\nx\n\n## 功能点\n\n### FR-1: 甲\nx\n'
}

function writeDocset(designNames: readonly string[], fmLine?: string): void {
  mkdirSync(join(dir, 'docs/requirements', REQ, 'design'), { recursive: true })
  writeFileSync(join(dir, 'docs/requirements', REQ, 'requirement.md'), reqDoc(fmLine))
  for (const n of designNames) writeFileSync(join(dir, DESIGN_DIR, n), '# ' + n + '\n')
}

interface SeedOpts { status?: string; registered: readonly string[]; unconfirmed?: readonly string[]; noArtifacts?: boolean }

async function seed(opts: SeedOpts): Promise<void> {
  const unconfirmed = new Set(opts.unconfirmed ?? [])
  const artifacts: StageArtifact[] = opts.noArtifacts === true
    ? []
    : opts.registered.map(name => ({
        stage: 'design', kind: 'design', path: DESIGN_DIR + '/' + name,
        registeredAt: 1, registeredBy: { kind: 'agent', sessionId: W },
        ...(unconfirmed.has(name) ? {} : { confirmedAt: 1, confirmedBy: { kind: 'human' } }),
      }) as StageArtifact)
  const r = {
    id: REQ, title: '完整性闸门', description: '', category: 'feature',
    status: opts.status ?? 'design', blocked: false, sourceSessionId: W,
    comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    ...(opts.noArtifacts === true ? {} : { artifacts }),
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown) =>
  tool.execute(args, { agent: { id: W } })

function moveTool() {
  return defineMoveTool({ store, now: () => 1000, workspaceRoot: dir } as never) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
}

function askTool() {
  const deps = {
    store, now: () => 1000, workspaceRoot: dir,
    userQuestions: () => ({ ask: async () => ({ answers: [{ id: 'confirm', selected: ['确认，进入拆分'] }] }) }),
  } as never
  return defineAskConfirmTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
}

const ASK_ARGS = { target: 'artifact', kind: 'design', question: '设计文档已完成，是否确认进入拆分？', options: ['确认，进入拆分', '需要修改'] }

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

function board() {
  return createReqboardHandler({
    store,
    now: () => 1000,
    docs: new FileDocRepository({ workspaceRoot: dir }),
    agents: () => ({ get: () => ({ id: W, session: {} }) }),
  })
}

async function post(handler: ReturnType<typeof board>, url: string, body: unknown): Promise<any> {
  const res = fakeRes()
  await handler(fakeReq('POST', url, body), res)
  return res
}

describe('缺文档（use-cases.md 未交）→ 四条转移路径全拒 design_doc_incomplete', () => {
  beforeEach(async () => {
    writeDocset(DESIGN4)
    await seed({ registered: DESIGN4 })
  })

  it('路径① 会话 reqboard_move → 拒，消息点名 use-cases.md', async () => {
    await expect(run(moveTool(), { to: 'decomposing' })).rejects.toThrow(/design_doc_incomplete/)
    await expect(run(moveTool(), { to: 'decomposing' })).rejects.toThrow(/use-cases\.md 未交/)
  })

  it('路径② 会话弹框确认后自动推进 → 拦，gate_failure 带缺口（落章保留）', async () => {
    const out = await run(askTool(), ASK_ARGS)
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(false)
    expect(out.gate_failure?.code).toBe('design_doc_incomplete')
    expect((out.gate_failure?.gaps ?? []).join(' ')).toContain('use-cases.md 未交')
    expect(store.snapshot().requirements[0].status).toBe('design')
  })

  it('路径③ 看板移动端点 → 400 design_doc_incomplete', async () => {
    const res = await post(board(), '/dashboard/api/reqboard/req/move', { id: REQ, to: 'decomposing', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('design_doc_incomplete')
    expect(res.payload.error).toContain('use-cases.md 未交')
  })

  it('路径④ 看板确认后自动推进 → 拦，gate_failure 带缺口（落章保留）', async () => {
    const res = await post(board(), '/dashboard/api/reqboard/req/artifact/confirm', { id: REQ, kind: 'design' })
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.advanced).toBe(false)
    expect(res.payload.data.gate_failure?.code).toBe('design_doc_incomplete')
    expect((res.payload.data.gate_failure?.gaps ?? []).join(' ')).toContain('use-cases.md 未交')
    expect(store.snapshot().requirements[0].status).toBe('design')
  })
})

describe('任一 design 产物未确认 → 拒（UC-4：磁盘有但无确认章）', () => {
  it('四路径全拒，gaps 含未确认路径', async () => {
    // 5 份落盘但只登记并确认了 4 份——第 5 份（use-cases.md）是确认后新落盘的
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN4 })

    await expect(run(moveTool(), { to: 'decomposing' })).rejects.toThrow(/design_doc_incomplete/)
    await expect(run(moveTool(), { to: 'decomposing' })).rejects.toThrow(/use-cases\.md 未确认/)

    const out = await run(askTool(), ASK_ARGS)
    expect(out.advanced).toBe(false)
    expect((out.gate_failure?.gaps ?? []).join(' ')).toContain('use-cases.md 未确认')

    const mv = await post(board(), '/dashboard/api/reqboard/req/move', { id: REQ, to: 'decomposing', actor: 'human' })
    expect(mv.statusCode).toBe(400)
    expect(mv.payload.code).toBe('design_doc_incomplete')

    const cf = await post(board(), '/dashboard/api/reqboard/req/artifact/confirm', { id: REQ, kind: 'design' })
    expect(cf.payload.data.advanced).toBe(false)
    expect((cf.payload.data.gate_failure?.gaps ?? []).join(' ')).toContain('use-cases.md 未确认')
  })

  it('已登记但未确认 → assertArtifactGates 成组判定先拦（artifact_not_confirmed，gaps 列未确认路径）', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN5, unconfirmed: ['interfaces.md', 'use-cases.md'] })
    const req = store.snapshot().requirements[0]
    const failure = assertArtifactGates(req, 'design', 'decomposing')
    expect(failure?.code).toBe('artifact_not_confirmed')
    expect(failure?.gaps?.join(' ')).toContain('interfaces.md')
    expect(failure?.gaps?.join(' ')).toContain('use-cases.md')
    // 会话 move 走同一判定（先于完整性闸门；工具侧错误码带 REQBOARD_ 前缀）
    await expect(run(moveTool(), { to: 'decomposing' })).rejects.toThrow(/REQBOARD_ARTIFACT_NOT_CONFIRMED/)
  })
})

describe('全交齐且全确认 → 放行', () => {
  it('会话 move 放行', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN5 })
    const out = await run(moveTool(), { to: 'decomposing' })
    expect(out.success).toBe(true)
    expect(out.to).toBe('decomposing')
  })

  it('看板 move 放行', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN5 })
    const res = await post(board(), '/dashboard/api/reqboard/req/move', { id: REQ, to: 'decomposing', actor: 'human' })
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.status).toBe('decomposing')
  })

  it('弹框确认补齐最后一份的章 → 自动推进放行', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN5, unconfirmed: ['architecture.md'] }) // 首份无章 → 弹框落章补齐
    const out = await run(askTool(), ASK_ARGS)
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(true)
    expect(out.gate_failure).toBeUndefined()
    expect(store.snapshot().requirements[0].status).toBe('decomposing')
  })

  it('看板确认补齐首份的章 → 自动推进放行', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN5, unconfirmed: ['architecture.md'] })
    const res = await post(board(), '/dashboard/api/reqboard/req/artifact/confirm', { id: REQ, kind: 'design' })
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.advanced).toBe(true)
    expect(store.snapshot().requirements[0].status).toBe('decomposing')
  })
})

describe('front-matter 策略参与①（UC-2）', () => {
  it('sides=frontend → frontend.md 必交，缺则拒并点名', async () => {
    writeDocset(DESIGN5, 'sides: frontend')
    await seed({ registered: DESIGN5 })
    await expect(run(moveTool(), { to: 'decomposing' })).rejects.toThrow(/design\/frontend\.md 未交/)
  })

  it('sides=frontend 且交齐 frontend.md → 放行（backend.md 不要求）', async () => {
    writeDocset([...DESIGN5, 'frontend.md'], 'sides: frontend')
    await seed({ registered: [...DESIGN5, 'frontend.md'] })
    const out = await run(moveTool(), { to: 'decomposing' })
    expect(out.success).toBe(true)
  })

  it('design_exempt 有效 → 缺 use-cases.md 也放行', async () => {
    writeDocset(DESIGN4, 'design_exempt: use-cases.md=纯内部工具无用户场景')
    await seed({ registered: DESIGN4 })
    const out = await run(moveTool(), { to: 'decomposing' })
    expect(out.success).toBe(true)
  })

  it('design_exempt 空理由 → 豁免无效，仍拒并注明', async () => {
    writeDocset(DESIGN4, 'design_exempt: use-cases.md=')
    await seed({ registered: DESIGN4 })
    await expect(run(moveTool(), { to: 'decomposing' })).rejects.toThrow(/豁免无效：理由为空/)
  })
})

describe('isLegacy 存量需求 → 全部新闸门放行（FR-6）', () => {
  it('无 artifacts 字段 → 会话 move 放行', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: [], noArtifacts: true })
    const out = await run(moveTool(), { to: 'decomposing' })
    expect(out.success).toBe(true)
  })

  it('无 artifacts 字段 → 看板 move 放行', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: [], noArtifacts: true })
    const res = await post(board(), '/dashboard/api/reqboard/req/move', { id: REQ, to: 'decomposing', actor: 'human' })
    expect(res.statusCode).toBe(200)
  })
})
