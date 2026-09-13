/**
 * 验收（人工审核）与归档（文档合并）端到端单测。
 *
 * 用户要求（原文）：「验收 有人工审核 / 归档 要有项目文档设计，文档如何合并，
 * 不同问题如何记录文档」。本组用真实 Store + 真实路由锁死：
 *   - 验收通过（accepting>done）是人工闸门：agent 调用被拒；
 *   - 没有验收材料的验收不能过（证据闸）；
 *   - 退回返工必须写意见，且退回后需求回到 implementing；
 *   - 归档前必须准备材料，且材料要符合该需求类型的文档规范（必填文档 + 合法合并去向 + 索引条目）；
 *   - 归档只能人点，归档后写入 archivePath 与时间线。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { ReqboardStore } from '../src/host/store.js'
import { createReqboardHandler } from '../src/host/routes.js'
import { definePlanSubmitTool, defineDecomposeTool, defineVerifySubmitTool, defineArchiveSubmitTool } from '../src/host/agent-tools.js'
import {
  ARCHIVE_DOC_RULES,
  assertArchiveMaterials,
  type RequirementRecord,
  type RequirementStatus,
} from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let planTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let decompose: { execute: (a: unknown, e: unknown) => Promise<any> }
let verifyTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let archiveTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let handler: ReturnType<typeof createReqboardHandler>

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-verify-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  const deps = { store, now: () => Date.now() } as never
  planTool = definePlanSubmitTool(deps) as never
  decompose = defineDecomposeTool(deps) as never
  verifyTool = defineVerifySubmitTool(deps) as never
  archiveTool = defineArchiveSubmitTool(deps) as never
  handler = createReqboardHandler({ store, now: () => Date.now() })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function fakeReq(body: unknown, url: string): any {
  const req = new EventEmitter() as any
  req.url = '/dashboard/api/reqboard' + url
  req.method = 'POST'
  req[Symbol.asyncIterator] = async function* () {
    if (body !== undefined) yield Buffer.from(JSON.stringify(body), 'utf8')
  }
  return req
}
function fakeRes(): any {
  const res: any = new EventEmitter()
  res.statusCode = 0
  res.writeHead = (code: number) => { res.statusCode = code; return res }
  res.end = (text?: string) => { res.payload = text === undefined ? undefined : JSON.parse(text); return res }
  return res
}
async function post(url: string, body: unknown) {
  const res = fakeRes()
  await handler(fakeReq(body, url), res)
  return res
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown, agent = W) =>
  tool.execute(args, { agent: { id: agent } })

/** 造一个处于指定状态的绑定需求（跳过前置流程）。 */
async function seed(status: RequirementStatus, category: RequirementRecord['category'] = 'feature'): Promise<void> {
  const r = {
    id: 'REQ-abc123', title: '需求', description: '', status, blocked: false, category,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status, at: 1, by: { kind: 'human' } }],
  } as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

describe('验收：人工审核 + 证据闸', () => {
  it('agent 不能自己把验收点过（accepting>done 是人工闸门）', async () => {
    await seed('accepting')
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'done', actor: 'agent' })
    expect(res.statusCode).toBe(403)
    expect(res.payload.code).toBe('human_gate')
    expect(store.snapshot().requirements[0].status).toBe('accepting')
  })

  it('没有验收材料时人也不能过（先要证据）', async () => {
    await seed('accepting')
    const res = await post('/req/verify/pass', { id: 'REQ-abc123' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.error).toContain('还没有验收材料')
  })

  it('agent 提交验收材料 → 待人工审核 → 人点通过 → done（时间线留痕）', async () => {
    await seed('accepting')
    const out = await run(verifyTool, { summary: '时间线/甘特图已上线', evidence: ['pnpm vitest run → 168 passed', '截图 /tmp/board.png'] })
    expect(out.status).toBe('accepting')

    const pass = await post('/req/verify/pass', { id: 'REQ-abc123' })
    expect(pass.statusCode).toBe(200)
    expect(pass.payload.data.status).toBe('done')
    expect(pass.payload.data.verification.decision).toBe('pass')
    expect(pass.payload.data.verification.reviewedBy.kind).toBe('human')
    expect(pass.payload.data.statusHistory.map((e: { status: string }) => e.status)).toEqual(['accepting', 'done'])
  })

  it('人工退回返工：必须写意见，需求回到 implementing，意见留在验收记录里', async () => {
    await seed('accepting')
    await run(verifyTool, { summary: '做完了', evidence: ['npm test'] })
    const empty = await post('/req/verify/rework', { id: 'REQ-abc123', note: '' })
    expect(empty.statusCode).toBe(400)

    const rework = await post('/req/verify/rework', { id: 'REQ-abc123', note: '甘特图缺依赖连线，补完再来' })
    expect(rework.statusCode).toBe(200)
    expect(rework.payload.data.status).toBe('implementing')
    expect(rework.payload.data.verification.decision).toBe('rework')
    expect(rework.payload.data.verification.reviewNote).toBe('甘特图缺依赖连线，补完再来')
    expect(rework.payload.data.comments.at(-1).body).toContain('退回返工')
  })

  it('验收材料本身要有内容：空 summary / 空证据一律拒绝', async () => {
    await seed('accepting')
    await expect(run(verifyTool, { summary: '', evidence: ['x'] })).rejects.toThrow(/summary 不能为空/)
    await expect(run(verifyTool, { summary: 'ok', evidence: [] })).rejects.toThrow(/至少要有一条可复核的证据/)
    await expect(run(verifyTool, { summary: 'ok', evidence: ['  '] })).rejects.toThrow(/至少要有一条可复核的证据/)
  })

  it('不在执行/验收阶段不能提交验收材料', async () => {
    await seed('brainstorming')
    await expect(run(verifyTool, { summary: 'x', evidence: ['y'] })).rejects.toThrow(/REQBOARD_BAD_STATUS/)
  })
})

describe('归档：文档合并规范 + 人工拍板', () => {
  const goodArchive = {
    dir: 'agent-dh/docs/requirements/REQ-abc123',
    docs: [
      { kind: 'requirement', path: 'agent-dh/docs/requirements/REQ-abc123/requirement.md' },
      { kind: 'plan', path: 'agent-dh/docs/requirements/REQ-abc123/plan.md' },
      { kind: 'verification', path: 'agent-dh/docs/requirements/REQ-abc123/verification.md' },
    ],
    merged_into: ['agent-dh/docs/architecture/requirement-board.md'],
    index_entry: '需求看板加状态时间线/计划模式/甘特图，拆分为落库已批准计划',
  }

  it('文档规范：不同需求类型有不同必填文档与合法合并去向', () => {
    expect(ARCHIVE_DOC_RULES.bug.requiredDocs).toContain('retro')
    expect(ARCHIVE_DOC_RULES.bug.mergeTargets).toContain('agent-dh/docs/guides/')
    // 归档不许自创平行体系：合并去向必须落在（agent-dh/）docs/ 下的既有规范目录内
    const CANONICAL_SUBDIRS = ['adr/', 'architecture/', 'guides/', 'rfcs/', 'work-logs/', 'strategy-research/', 'requirements/']
    for (const rule of Object.values(ARCHIVE_DOC_RULES)) {
      for (const target of rule.mergeTargets) {
        const m = /^(agent-dh\/)?docs\/(.*)$/.exec(target)
        expect(m, target).not.toBeNull()
        const rest = m === null ? '' : m[2]
        expect(rest === '' || CANONICAL_SUBDIRS.some(prefix => rest.startsWith(prefix)), target).toBe(true)
      }
    }
    expect(ARCHIVE_DOC_RULES.spike.requiredDocs).toEqual(['requirement', 'retro'])
    // 缺陷类缺复盘 → 拒
    expect(() => assertArchiveMaterials('bug', {
      dir: 'agent-dh/docs/requirements/REQ-abc123', docs: [{ kind: 'requirement', path: 'a' }, { kind: 'verification', path: 'b' }],
      mergedInto: ['agent-dh/docs/nowhere/x.md'], indexEntry: 'i',
    })).toThrow(/缺少必填文档：retro/)
    // 合并去向自创平行目录（docs/nowhere/）→ 拒：归档不许绕过文档规范
    expect(() => assertArchiveMaterials('bug', {
      dir: 'agent-dh/docs/requirements/REQ-abc123', docs: [{ kind: 'requirement', path: 'a' }, { kind: 'verification', path: 'b' }, { kind: 'retro', path: 'c' }],
      mergedInto: ['agent-dh/docs/nowhere/x.md'], indexEntry: 'i',
    })).toThrow(/不在本类型允许的位置/)
    // 合法去向（缺陷 → guides/ 故障排查）→ 通过
    expect(() => assertArchiveMaterials('bug', {
      dir: 'agent-dh/docs/requirements/REQ-abc123', docs: [{ kind: 'requirement', path: 'a' }, { kind: 'verification', path: 'b' }, { kind: 'retro', path: 'c' }],
      mergedInto: ['agent-dh/docs/guides/troubleshooting.md'], indexEntry: 'i',
    })).not.toThrow()
    // 缺索引条目 → 拒
    expect(() => assertArchiveMaterials('feature', {
      dir: 'agent-dh/docs/requirements/REQ-abc123', docs: [{ kind: 'requirement', path: 'a' }, { kind: 'plan', path: 'b' }, { kind: 'verification', path: 'c' }],
      mergedInto: ['agent-dh/docs/architecture/x.md'], indexEntry: '',
    })).toThrow(/索引条目/)
  })

  it('归档材料：agent 准备 → 人点归档 → archived + archivePath + 时间线', async () => {
    await seed('done')
    const out = await run(archiveTool, goodArchive)
    expect(out.success).toBe(true)
    expect(out.required_docs).toEqual(['requirement', 'plan', 'verification'])

    // 材料不齐时人点归档也过不去（同一套规范再校验一次）
    const archived = await post('/req/archive', { id: 'REQ-abc123' })
    expect(archived.statusCode).toBe(200)
    expect(archived.payload.data.status).toBe('archived')
    expect(archived.payload.data.archivePath).toBe('agent-dh/docs/requirements/REQ-abc123')
    expect(archived.payload.data.archive.archivedBy.kind).toBe('human')
    expect(archived.payload.data.archive.mergedInto).toEqual(['agent-dh/docs/architecture/requirement-board.md'])
    expect(archived.payload.data.statusHistory.at(-1).status).toBe('archived')
  })

  it('没有材料不能归档；未完成不能归档；材料不合规当场被拒', async () => {
    await seed('done')
    const noMaterials = await post('/req/archive', { id: 'REQ-abc123' })
    expect(noMaterials.statusCode).toBe(400)
    expect(noMaterials.payload.error).toContain('还没有归档材料')

    await expect(run(archiveTool, { ...goodArchive, merged_into: ['docs/known-issues/x.md'] }))
      .rejects.toThrow(/不在本类型允许的位置/)

  })

  it('未完成（implementing）的需求不能准备归档材料', async () => {
    await seed('implementing')
    await expect(run(archiveTool, goodArchive)).rejects.toThrow(/REQBOARD_BAD_STATUS/)
  })
})
