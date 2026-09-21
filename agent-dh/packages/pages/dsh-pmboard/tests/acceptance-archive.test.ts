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
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { defineVerifySubmitTool, defineArchiveSubmitTool, stubDocFile } from './helpers/tool-deps.js'
import {
  ARCHIVE_DOC_RULES,
  assertArchiveMaterials,
  type RequirementRecord,
  type RequirementStatus,
} from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let verifyTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let archiveTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let handler: ReturnType<typeof createReqboardHandler>

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-verify-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  const deps = { store, now: () => Date.now() } as never
  verifyTool = defineVerifySubmitTool(deps) as never
  archiveTool = defineArchiveSubmitTool(deps) as never
  handler = createReqboardHandler({ store, now: () => Date.now() })
  // REQ-2d1c74 FR-5：archive 目录与清单内文档须真实落盘（agent-dh/ 前缀为仓库根相对形态）
  for (const p of ['requirement.md', 'plan.md', 'verification.md']) stubDocFile('agent-dh/docs/requirements/REQ-abc123/' + p)
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
  it('agent 不能自己把验收点过（accepting>archived 是人工闸门）', async () => {
    await seed('accepting')
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'archived', actor: 'agent' })
    expect(res.statusCode).toBe(403)
    expect(res.payload.code).toBe('human_gate')
    expect(store.snapshot().requirements[0].status).toBe('accepting')
  })

  it('没有验收材料时人也不能过（先要证据）', async () => {
    await seed('accepting')
    const res = await post('/req/verify/pass', { id: 'REQ-abc123' })
    expect(res.statusCode).toBe(400)
    // REQ-a8d582 FR-4（REQ-f0579a t1 更新断言口径）：无材料 = 不合规通过，
    // 报文统一为 verify_override_required——人仍可以过，但必须带 confirm_override 显式覆盖留痕，
    // 「先要证据」的默认拒绝语义不变（旧断言只匹配旧文案「还没有验收材料」，与现行契约脱节）。
    expect(res.payload.code).toBe('verify_override_required')
    expect(res.payload.error).toContain('尚无验收材料')
  })

  it('agent 提交验收材料 → 待人工审核 → 人逐项裁决全过 → 人点通过 → 直接 archived（时间线留痕，REQ-9f4a44）', async () => {
    await seed('accepting')
    const out = await run(verifyTool, { summary: '时间线/甘特图已上线', evidence: ['pnpm vitest run → 168 passed', '截图 /tmp/board.png'] })
    expect(out.status).toBe('accepting')

    // REQ-a8d582 FR-4（REQ-f0579a t1 补裁决步）：提交材料会生成逐项验收单（含需求级项，初始 pending），
    // 未裁决 = 不合规通过（须覆盖）。快乐路径必须先逐项裁决全过，再点「验收通过」。
    const sheet = store.snapshot().requirements[0]!.verification!.sheet!
    const verdicts = await post('/req/verdicts', {
      id: 'REQ-abc123', version: sheet.version,
      verdicts: sheet.items.map(i => ({ itemId: i.id, status: 'passed' })),
    })
    expect(verdicts.statusCode).toBe(200)

    const pass = await post('/req/verify/pass', { id: 'REQ-abc123' })
    expect(pass.statusCode).toBe(200)
    // REQ-9f4a44：验收通过 → 直接归档（无 done 中转）
    expect(pass.payload.data.status).toBe('archived')
    expect(pass.payload.data.verification.decision).toBe('pass')
    expect(pass.payload.data.verification.reviewedBy.kind).toBe('human')
    expect(pass.payload.data.statusHistory.map((e: { status: string }) => e.status)).toEqual(['accepting', 'archived'])
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
    manual_updates: [
      { path: 'docs/architecture/project-manual.md', section: '关键概念（术语表）', summary: '新增"需求看板/计划模式"两个术语的指针' },
    ],
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

  it('归档材料：agent 在 archived 下补齐 → archivePath 落库（REQ-9f4a44 自动归档）', async () => {
    // 验收通过即已 archived（无 done 中转），agent 随后补材料
    await seed('archived')
    const out = await run(archiveTool, goodArchive)
    expect(out.success).toBe(true)
    expect(out.required_docs).toEqual(['requirement', 'plan', 'verification'])

    const req = store.snapshot().requirements[0]
    expect(req.archive?.dir).toBe('agent-dh/docs/requirements/REQ-abc123')
    expect(req.archivePath).toBe('agent-dh/docs/requirements/REQ-abc123')
    expect(req.archive?.mergedInto).toEqual(['agent-dh/docs/architecture/requirement-board.md'])
  })

  it('材料不合规当场被拒（合并去向超出本类型允许位置）', async () => {
    await seed('archived')
    await expect(run(archiveTool, { ...goodArchive, merged_into: ['docs/known-issues/x.md'] }))
      .rejects.toThrow(/不在本类型允许的位置/)
  })

  it('未完成（implementing）的需求不能准备归档材料', async () => {
    await seed('implementing')
    await expect(run(archiveTool, goodArchive)).rejects.toThrow(/REQBOARD_BAD_STATUS/)
  })
})

describe('文档金字塔：归档让项目认知向上生长', () => {
  const goodArchive = {
    dir: 'agent-dh/docs/requirements/REQ-abc123',
    docs: [
      { kind: 'requirement', path: 'agent-dh/docs/requirements/REQ-abc123/requirement.md' },
      { kind: 'plan', path: 'agent-dh/docs/requirements/REQ-abc123/plan.md' },
      { kind: 'verification', path: 'agent-dh/docs/requirements/REQ-abc123/verification.md' },
    ],
    merged_into: ['agent-dh/docs/architecture/requirement-board.md'],
    index_entry: '一句话结论',
    manual_updates: [
      { path: 'docs/architecture/project-manual.md', section: '关键概念（术语表）', summary: '新增两个术语指针' },
    ],
  }

  it('改变项目级认知的类型（feature/refactor/spike）必须申报说明书更新点', () => {
    expect(ARCHIVE_DOC_RULES.feature.requireManual).toBe(true)
    expect(ARCHIVE_DOC_RULES.refactor.requireManual).toBe(true)
    expect(ARCHIVE_DOC_RULES.spike.requireManual).toBe(true)
    expect(ARCHIVE_DOC_RULES.bug.requireManual).toBe(false)
    const base = {
      dir: 'agent-dh/docs/requirements/REQ-abc123',
      docs: [{ kind: 'requirement' as const, path: 'a' }, { kind: 'plan' as const, path: 'b' }, { kind: 'verification' as const, path: 'c' }],
      mergedInto: ['docs/architecture/x.md'],
      indexEntry: 'i',
    }
    expect(() => assertArchiveMaterials('feature', base)).toThrow(/缺少项目说明书更新点/)
    expect(() => assertArchiveMaterials('feature', {
      ...base,
      manualUpdates: [{ path: 'docs/architecture/project-manual.md', section: '术语表', summary: '多了 X 认知' }],
    })).not.toThrow()
    // 更新点必须写全 path/section/summary
    expect(() => assertArchiveMaterials('feature', {
      ...base,
      manualUpdates: [{ path: '', section: 's', summary: 'x' }],
    })).toThrow(/必须写全 path \/ section \/ summary/)
    // 不改变认知的类型：不强制申报
    expect(() => assertArchiveMaterials('chore', {
      requiredForChore: true, dir: base.dir, docs: [{ kind: 'requirement', path: 'a' }, { kind: 'verification', path: 'c' }],
      mergedInto: ['docs/work-logs/2026-09/x.md'], indexEntry: 'i',
    } as never)).not.toThrow()
  })

  it('归档工具：feature 类不申报说明书更新点会被拒；申报后落库并在评论留痕', async () => {
    await seed('done')
    const noManual = {
      dir: goodArchive.dir,
      docs: goodArchive.docs,
      merged_into: goodArchive.merged_into,
      index_entry: goodArchive.index_entry,
    }
    await expect(run(archiveTool, noManual)).rejects.toThrow(/缺少项目说明书更新点/)

    const out = await run(archiveTool, goodArchive)
    expect(out.success).toBe(true)
    const req = store.snapshot().requirements[0]
    expect(req.archive?.manualUpdates?.[0]?.section).toBe('关键概念（术语表）')
    expect(req.comments.at(-1)?.body).toContain('说明书更新：docs/architecture/project-manual.md#关键概念（术语表）')
  })
})
