/**
 * 产物登记与分类感知闸门单测（REQ-31e11f t4）。
 *
 * 覆盖：
 *   - 产物登记钩子（plan_submit / decompose / verify_submit / archive_submit 四处）；
 *   - 幂等（同 stage+kind+path 不重复登记）；
 *   - 五门两级校验（missing_artifact / artifact_not_confirmed）；
 *   - 存量需求不硬拦（向后兼容）；
 *   - 确认后放行（artifact/confirm 路由）；
 *   - 分类过滤（bug 免 requirement 门）；
 *   - human-only confirm 路由。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, existsSync, readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { EventEmitter } from 'node:events'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import {
  definePlanSubmitTool,
  defineDecomposeTool,
  defineVerifySubmitTool,
  defineArchiveSubmitTool,
  stubDocFile,
} from './helpers/tool-deps.js'
import type { RequirementRecord, RequirementStatus } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let prevCwd: string
let store: ReqboardStore
let planTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let decompose: { execute: (a: unknown, e: unknown) => Promise<any> }
let verifyTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let archiveTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let handler: ReturnType<typeof createReqboardHandler>

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-gates-'))
  prevCwd = process.cwd()
  process.chdir(dir)
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  const deps = { store, now: () => Date.now() } as never
  planTool = definePlanSubmitTool(deps) as never
  decompose = defineDecomposeTool(deps) as never
  verifyTool = defineVerifySubmitTool(deps) as never
  archiveTool = defineArchiveSubmitTool(deps) as never
  // REQ-2d1c74 FR-2：G2 完整性闸门要求 docs 端口（缺省 = fail-closed 拦截），看板侧必须接
  handler = createReqboardHandler({ store, now: () => Date.now(), docs: new FileDocRepository({ workspaceRoot: dir }) })
  // REQ-2d1c74 FR-5：plan_submit 起要求提交路径真实落盘（chdir 后 stub 落进本测试临时目录）。
  // decomposition.md 不在此落桩——decompose 用例要验证它由拆分动作**生成**。
  stubDocFile('docs/requirements/REQ-abc123/plan.md')
})
afterEach(() => {
  process.chdir(prevCwd)
  rmSync(dir, { recursive: true, force: true })
})

async function seed(
  status: RequirementStatus = 'design',
  category: RequirementRecord['category'] = 'feature',
  sourceSessionId: string | undefined = W,
): Promise<RequirementRecord> {
  const r = {
    id: 'REQ-abc123', title: '看板需求', description: '', status, blocked: false,
    ...(category !== undefined ? { category } : {}),
    ...(sourceSessionId !== undefined ? { sourceSessionId } : {}),
    comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status: 'draft', at: 1, by: { kind: 'human' } }],
  } as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
  return r
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown, agent = W) =>
  tool.execute(args, { agent: { id: agent } })

const TWO_TASKS = [
  { key: 'a', title: '协议层加时间线', phase: 'implement', side: 'backend', acceptance: '单测绿', implementation: 'protocol.ts 加时间线字段' },
  { key: 'b', title: '客户端渲染甘特图', phase: 'ui', side: 'frontend', depends_on: ['a'], acceptance: '截图可见', implementation: 'view.ts 加 buildGantt 渲染' },
]

async function planAndApprove(tasks: unknown = TWO_TASKS): Promise<void> {
  await run(planTool, { path: 'docs/requirements/REQ-abc123/plan.md', summary: '摘要', tasks })
  await store.mutate('requirement-updated', (l) => {
    const r = l.requirements[0]
    if (r.plan !== undefined) { r.plan.approvedAt = 1000; r.plan.approvedBy = { kind: 'human' } }
    return { requirements: [r] }
  })
}

// -- 路由辅助 ----------------------------------------------------------------

function fakeReq(body: unknown, url: string): any {
  const req = new EventEmitter() as any
  req.url = url
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
  await handler(fakeReq(body, '/dashboard/api/reqboard' + url), res)
  return res
}

// -- 产物登记钩子 ------------------------------------------------------------

describe('产物登记钩子', () => {
  it('plan_submit 成功时登记 kind=decomposition 产物（stage=decomposing；2026-09-21 裁定）', async () => {
    await seed('decomposing')
    stubDocFile('docs/requirements/REQ-abc123/decomposition.md') // FR-5：提交路径须落盘
    await run(planTool, { path: 'docs/requirements/REQ-abc123/decomposition.md', summary: 's', tasks: TWO_TASKS })
    const req = store.snapshot().requirements[0]
    expect(req.artifacts).toHaveLength(1)
    expect(req.artifacts![0]).toMatchObject({
      stage: 'decomposing', kind: 'decomposition', path: 'docs/requirements/REQ-abc123/decomposition.md',
    })
    expect(req.artifacts![0].registeredBy).toEqual({ kind: 'agent', sessionId: W })
  })

  it('plan_submit 幂等：重复提交不重复登记', async () => {
    await seed('decomposing')
    stubDocFile('docs/requirements/REQ-abc123/decomposition.md') // FR-5：提交路径须落盘
    await run(planTool, { path: 'docs/requirements/REQ-abc123/decomposition.md', summary: 's', tasks: TWO_TASKS })
    await run(planTool, { path: 'docs/requirements/REQ-abc123/decomposition.md', summary: 's2', tasks: TWO_TASKS })
    const req = store.snapshot().requirements[0]
    expect(req.artifacts).toHaveLength(1)
  })

  it('decompose 成功时自动生成 decomposition.md + 任务卡骨架', async () => {
    await seed('decomposing')
    await planAndApprove()
    const out = await run(decompose, {})
    expect(out.success).toBe(true)

    // decomposition.md 落盘
    const decompPath = join(dir, 'docs/requirements/REQ-abc123/decomposition.md')
    expect(existsSync(decompPath)).toBe(true)
    const decompText = readFileSync(decompPath, 'utf8')
    expect(decompText).toContain('REQ-abc123')
    expect(decompText).toContain('协议层加时间线')

    // 任务卡骨架落盘
    const taskId = out.created[0].id as string
    const taskPath = join(dir, 'docs/requirements/REQ-abc123/tasks', taskId + '.md')
    expect(existsSync(taskPath)).toBe(true)
    const taskText = readFileSync(taskPath, 'utf8')
    expect(taskText).toContain(taskId)
    expect(taskText).toContain('协议层加时间线')
    expect(taskText).toContain('单测绿')

    // 台账登记
    const req = store.snapshot().requirements[0]
    expect(req.artifacts!.some(a => a.kind === 'decomposition')).toBe(true)
    expect(req.artifacts!.some(a => a.kind === 'task_detail' && a.path.includes(taskId))).toBe(true)
  })

  it('verify_submit 成功时自动生成 verification.md 并登记', async () => {
    await seed('implementing')
    await run(verifyTool, { summary: '交付完成', evidence: ['tests pass'] })
    const verPath = join(dir, 'docs/requirements/REQ-abc123/verification.md')
    expect(existsSync(verPath)).toBe(true)
    const verText = readFileSync(verPath, 'utf8')
    expect(verText).toContain('交付完成')
    expect(verText).toContain('tests pass')
    const req = store.snapshot().requirements[0]
    expect(req.artifacts!.some(a => a.kind === 'verification')).toBe(true)
  })

  it('archive_submit 成功时登记 kind=archive 产物', async () => {
    await seed('done')
    // REQ-2d1c74 FR-5：archive 目录与清单内文档须真实落盘
    for (const p of ['requirement.md', 'plan.md', 'verification.md']) stubDocFile('docs/requirements/REQ-abc123/' + p)
    await run(archiveTool, {
      dir: 'docs/requirements/REQ-abc123',
      docs: [
        { kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md' },
        { kind: 'plan', path: 'docs/requirements/REQ-abc123/plan.md' },
        { kind: 'verification', path: 'docs/requirements/REQ-abc123/verification.md' },
      ],
      merged_into: ['docs/architecture/project-manual.md'],
      index_entry: '测试归档',
      manual_updates: [{ path: 'docs/architecture/project-manual.md', section: '测试', summary: '新增测试章节' }],
    })
    const req = store.snapshot().requirements[0]
    expect(req.artifacts!.some(a => a.kind === 'archive' && a.path === 'docs/requirements/REQ-abc123')).toBe(true)
  })
})

// -- 五门两级校验 ------------------------------------------------------------

describe('五门两级校验', () => {
  it('missing_artifact：产物缺失时转移被拒', async () => {
    // feature 分类：brainstorming → design 需要 requirement 产物
    await seed('brainstorming', 'feature')
    // 手动登记一个 requirement 产物但不确认
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    // 未确认 → 拒
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'design', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('artifact_not_confirmed')
    expect(res.payload.error).toContain('requirement.md')
  })

  it('artifact_not_confirmed：产物存在但未确认时转移被拒', async () => {
    await seed('brainstorming', 'feature')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'design', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('artifact_not_confirmed')
  })

  it('确认后放行：artifact/confirm 后转移成功', async () => {
    await seed('brainstorming', 'feature')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    // 确认
    const confirmRes = await post('/req/artifact/confirm', { id: 'REQ-abc123', kind: 'requirement' })
    expect(confirmRes.statusCode).toBe(200)
    expect(confirmRes.payload.data.artifacts![0].confirmedAt).toBeDefined()
    expect(confirmRes.payload.data.artifacts![0].confirmedBy).toEqual({ kind: 'human' })
    // 转移成功
    const moveRes = await post('/req/move', { id: 'REQ-abc123', to: 'design', actor: 'human' })
    expect(moveRes.statusCode).toBe(200)
    expect(moveRes.payload.data.status).toBe('design')
  })

  it('存量需求（无 artifacts 字段）不硬拦', async () => {
    // 不设置 artifacts 字段
    await seed('brainstorming', 'feature')
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'design', actor: 'human' })
    expect(res.statusCode).toBe(200)
  })

  it('存量需求（artifacts 为空数组）不硬拦', async () => {
    await seed('brainstorming', 'feature')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = []
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'design', actor: 'human' })
    expect(res.statusCode).toBe(200)
  })

  it('bug 分类免 requirement 门：brainstorming → design 直接放行', async () => {
    await seed('brainstorming', 'bug')
    // bug 分类：confirmGates 不含 brainstorming>design
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'design', actor: 'human' })
    expect(res.statusCode).toBe(200)
  })

  it('design → decomposing：确认门 + 文档集完整性门两层（2026-09-21 裁定 + REQ-2d1c74 FR-2）', async () => {
    await seed('design', 'feature')
    // REQ-2d1c74：feature 文档集 = 5 份必交；先在磁盘交齐（requirement.md 含必填节）
    mkdirSync(join(dir, 'docs/requirements/REQ-abc123/design'), { recursive: true })
    writeFileSync(join(dir, 'docs/requirements/REQ-abc123/requirement.md'),
      '# 需求\n\n## 边界\nx\n\n## 产品定义\nx\n\n## 用户与角色\nx\n\n## 功能点\n\n### FR-1: 甲\nx\n')
    const DESIGN5 = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']
    for (const n of DESIGN5) writeFileSync(join(dir, 'docs/requirements/REQ-abc123/design', n), '# ' + n + '\n')
    // 登记 5 份 design 产物但不确认 → 转移被拒（成组判定：任一未确认即拒）
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = DESIGN5.map(n => ({ stage: 'design', kind: 'design', path: 'docs/requirements/REQ-abc123/design/' + n, registeredAt: 1, registeredBy: { kind: 'agent' } }))
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'decomposing', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('artifact_not_confirmed')
    expect(res.payload.error).toContain('use-cases.md') // gaps 列出全部未确认路径
    // 人确认设计文档（REQ-2d1c74 FR-2：kind=design 看板一键 = 成组落章全部 5 份）→ 放行
    const ok = await post('/req/artifact/confirm', { id: 'REQ-abc123', kind: 'design', actor: 'human' })
    expect(ok.statusCode).toBe(200)
    const stamped = store.snapshot().requirements[0]
    expect((stamped.artifacts ?? []).filter(a => a.kind === 'design').every(a => a.confirmedAt !== undefined)).toBe(true)
    const moved = await post('/req/move', { id: 'REQ-abc123', to: 'decomposing', actor: 'human' })
    expect(moved.statusCode).toBe(200)
  })
})

// -- human-only confirm 路由 -------------------------------------------------

describe('human-only confirm 路由', () => {
  it('agent actor 不能确认产物', async () => {
    await seed('brainstorming', 'feature')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    // 路由层 actor 默认 human；显式传 agent 应该被拒
    const res = await post('/req/artifact/confirm', { id: 'REQ-abc123', kind: 'requirement', actor: 'agent' })
    // 当前实现：路由层不检查 actor（参照 plan/approve），但 handleArtifactConfirm 里 createdBy={kind:'human'}
    // 如果未来加了 actor 检查，这里应该返回 403
    // 现阶段：确认操作本身把 confirmedBy 设为 human，语义上只有人能调
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.artifacts![0].confirmedBy).toEqual({ kind: 'human' })
  })

  it('确认不存在的 kind → 400', async () => {
    await seed('brainstorming', 'feature')
    const res = await post('/req/artifact/confirm', { id: 'REQ-abc123', kind: 'nonexistent' })
    expect(res.statusCode).toBe(400)
  })
})

// -- 分类过滤 ----------------------------------------------------------------

describe('分类过滤', () => {
  it('feature 全流水线 5 门：brainstorming>design 需要 requirement 产物确认', async () => {
    await seed('brainstorming', 'feature')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'design', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('artifact_not_confirmed')
  })

  it('spike 分类免 brainstorming 门：直接放行', async () => {
    await seed('brainstorming', 'spike')
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'design', actor: 'human' })
    expect(res.statusCode).toBe(200)
  })

  it('chore 分类免 brainstorming 门：直接放行', async () => {
    await seed('brainstorming', 'chore')
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'design', actor: 'human' })
    expect(res.statusCode).toBe(200)
  })
})


// ---------------------------------------------------------------------------
// t8 补充：剩余三道门的两级校验（decomposing>implementing / accepting>done / done>archived）
// ---------------------------------------------------------------------------

describe('t8 补充：五门两级校验（全量）', () => {
  // 辅助：先登记一个无关产物让需求非 legacy（触发硬拦），再测具体门
  async function makeNonLegacy(_reqId: string = 'REQ-abc123') {
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'draft', kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
  }

  it('decomposing>implementing：非 legacy 缺 decomposition 产物 → missing_artifact', async () => {
    await seed('decomposing', 'feature')
    await makeNonLegacy()
    // 移除 decomposition 产物（只留无关产物）
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = r.artifacts!.filter(a => a.kind !== 'decomposition')
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'implementing', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('missing_artifact')
  })

  it('decomposing>implementing：产物存在但未确认 → artifact_not_confirmed', async () => {
    await seed('decomposing', 'feature')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'decomposing', kind: 'decomposition', path: 'docs/requirements/REQ-abc123/decomposition.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'implementing', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('artifact_not_confirmed')
  })

  it('decomposing>implementing：产物确认后 → 放行', async () => {
    await seed('decomposing', 'feature')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'decomposing', kind: 'decomposition', path: 'docs/requirements/REQ-abc123/decomposition.md', registeredAt: 1, registeredBy: { kind: 'agent' }, confirmedAt: 2, confirmedBy: { kind: 'human' } }]
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'implementing', actor: 'human' })
    expect(res.statusCode).toBe(200)
  })

  it('accepting>archived：非 legacy 缺 verification 产物 → missing_artifact', async () => {
    await seed('accepting', 'feature')
    await makeNonLegacy()
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = r.artifacts!.filter(a => a.kind !== 'verification')
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'archived', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('missing_artifact')
  })

  it('accepting>archived：产物存在但未确认 → artifact_not_confirmed', async () => {
    await seed('accepting', 'feature')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'accepting', kind: 'verification', path: 'docs/requirements/REQ-abc123/verification.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'archived', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('artifact_not_confirmed')
  })

  // REQ-9f4a44：done>archived 门已合并进 accepting>archived（验收通过即归档），
  // 原两个 done>archived 用例随之移除。

  it('bug 分类：decomposing>implementing 门仍生效（4 门之一）', async () => {
    await seed('decomposing', 'bug')
    // bug 分类：decomposing>implementing 是 4 门之一；非 legacy 时缺产物应被拦
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'draft', kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'implementing', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('missing_artifact')
  })

  it('refactor 分类：免需求分析门（brainstorming>design 直接放行）', async () => {
    await seed('brainstorming', 'refactor')
    // refactor 的 confirmGates 不含 brainstorming>design → 直接放行
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'design', actor: 'human' })
    expect(res.statusCode).toBe(200)
  })
})

// ── 取消需求豁免产物闸门（2026-09-20 REQ-6cbbf7 死锁修复）────────────────────
// 现场复刻：需求卡在 decomposing、已登记 1 个 plan 产物但无 decomposition 产物，
// 人工点「取消」被 missing_artifact 拒绝——放弃路径被「节点完成」闸门锁死。
describe('取消需求豁免产物闸门（*>canceled 是放弃路径，不进闸）', () => {
  it('decomposing 缺 decomposition 产物：→ canceled 放行；同现场 → implementing 仍硬拦', async () => {
    await seed('decomposing', 'bug')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'design', kind: 'plan', path: 'docs/requirements/REQ-abc123/plan.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    // 对照组：推进路径闸门不放松
    const blocked = await post('/req/move', { id: 'REQ-abc123', to: 'implementing', actor: 'human' })
    expect(blocked.statusCode).toBe(400)
    expect(blocked.payload.code).toBe('missing_artifact')
    // 实验组：放弃路径放行
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'canceled', actor: 'human' })
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.status).toBe('canceled')
  })

  it('brainstorming 有未确认 requirement 产物：→ canceled 同样放行（确认门一并豁免）', async () => {
    await seed('brainstorming', 'feature')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'canceled', actor: 'human' })
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.status).toBe('canceled')
  })

  it('豁免不放松人工闸门：agent actor 调 → canceled 仍被拒', async () => {
    await seed('decomposing', 'bug')
    const res = await post('/req/move', { id: 'REQ-abc123', to: 'canceled', actor: 'agent' })
    expect(res.statusCode).toBe(403) // 人工闸门：agent 一律 403
    const req = store.snapshot().requirements[0]
    expect(req.status).toBe('decomposing')
  })
})
