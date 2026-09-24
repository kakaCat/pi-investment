/**
 * 节点详情装配器与路由测试（REQ-31e11f t2）。
 * serves: FR-4（REQ-81aabd 设计节点逐份交付状态）。
 *
 * 覆盖：
 *   - 7 节点装配：每节点返回契约块（stage/enabled/artifacts/timeline/body 形状正确）；
 *   - 分类跳过：bug 类无 brainstorming 节点 → enabled:false + 空 body，不报错；
 *   - pendingConfirmation 标记：五门源头 stage 有产物未确认 → true；已确认 → false；
 *     分类未启用的门 → false；
 *   - implementing：tasks 带 executions/claimedBy，byWindow 按窗口码分组；
 *   - 路由：GET /requirements/:id/stage/:stage 200/400/404。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { assembleStageDetail } from '../src/application/query/index.js'
import type {
  ActorRef,
  RequirementRecord,
  StageKey,
  TaskRecord,
} from '../src/shared/protocol.js'

const HUMAN: ActorRef = { kind: 'human' }

/** 构造一个最小可用需求（默认 feature 分类，全流水线）。 */
function makeReq(overrides: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: 'REQ-a1b2c3',
    title: '节点详情测试需求',
    description: '测试描述',
    category: 'feature',
    status: 'implementing',
    blocked: false,
    comments: [],
    version: 1,
    createdAt: 1000,
    updatedAt: 2000,
    createdBy: HUMAN,
    updatedBy: HUMAN,
    statusHistory: [
      { status: 'draft', at: 1000, by: HUMAN, reason: '创建' },
      { status: 'brainstorming', at: 1100, by: HUMAN },
      { status: 'design', at: 1200, by: HUMAN },
      { status: 'decomposing', at: 1300, by: HUMAN },
      { status: 'implementing', at: 1400, by: HUMAN },
    ],
    ...overrides,
  }
}

/** 构造一个最小可用任务。 */
function makeTask(overrides: Partial<TaskRecord> = {}): TaskRecord {
  return {
    id: 't-111111',
    requirementId: 'REQ-a1b2c3',
    title: '任务一',
    description: '',
    phase: 'implement',
    side: 'backend',
    dependsOn: [],
    scope: { apis: [], tables: [], files: [] },
    acceptance: '单测绿',
    context: '',
    status: 'in_progress',
    blocked: false,
    executions: [],
    comments: [],
    version: 1,
    createdAt: 1500,
    updatedAt: 1500,
    createdBy: HUMAN,
    updatedBy: HUMAN,
    ...overrides,
  }
}

const LEDGER = { tasks: [] as TaskRecord[] }

// ---------------------------------------------------------------------------
// 7 节点装配
// ---------------------------------------------------------------------------

describe('assembleStageDetail：7 节点装配', () => {
  const STAGES: StageKey[] = ['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived']

  it.each(STAGES)('节点 %s 返回契约块（stage/enabled/artifacts/timeline）', (stage) => {
    const detail = assembleStageDetail(makeReq(), LEDGER, stage)
    expect(detail.stage).toBe(stage)
    expect(detail.enabled).toBe(true)
    expect(Array.isArray(detail.artifacts)).toBe(true)
    expect(Array.isArray(detail.timeline)).toBe(true)
    expect(typeof detail.pendingConfirmation).toBe('boolean')
  })

  it('draft.body 含需求卡字段（标题/分类/描述/立项窗口/创建时间）', () => {
    const req = makeReq({ sourceSessionId: 'session-abcdef12-3456-7890-abcd-ef1234567890' })
    const detail = assembleStageDetail(req, LEDGER, 'draft')
    expect(detail.stage).toBe('draft')
    if (detail.stage !== 'draft') throw new Error('narrow')
    expect(detail.body.title).toBe('节点详情测试需求')
    expect(detail.body.category).toBe('feature')
    expect(detail.body.description).toBe('测试描述')
    expect(detail.body.sourceWindow).toBe('w-abcdef12')
    expect(detail.body.createdAt).toBe(1000)
  })

  it('brainstorming.body 含 requirementDoc（产物 path 优先）+ 评论', () => {
    const req = makeReq({
      artifacts: [{
        stage: 'brainstorming', kind: 'requirement',
        path: 'docs/requirements/REQ-a1b2c3/requirement.md',
        registeredAt: 1100, registeredBy: HUMAN,
      }],
      comments: [{ id: 'c-1', body: '需求边界已确认', createdAt: 1100, createdBy: HUMAN }],
    })
    const detail = assembleStageDetail(req, LEDGER, 'brainstorming')
    if (detail.stage !== 'brainstorming') throw new Error('narrow')
    expect(detail.body.requirementDoc).toBe('docs/requirements/REQ-a1b2c3/requirement.md')
    expect(detail.body.comments).toHaveLength(1)
  })

  it('design.body 含 PlanRecord（路径/任务表/批准留痕）', () => {
    const req = makeReq({
      plan: {
        path: 'docs/requirements/REQ-a1b2c3/plan.md',
        summary: '目标+做法',
        tasks: [{ key: 't1', title: '任务一', phase: 'implement', side: 'backend', acceptance: '单测绿' }],
        submittedAt: 1200,
        submittedBy: HUMAN,
        approvedAt: 1250,
        approvedBy: HUMAN,
      },
    })
    const detail = assembleStageDetail(req, LEDGER, 'design')
    if (detail.stage !== 'design') throw new Error('narrow')
    expect(detail.body.plan?.path).toBe('docs/requirements/REQ-a1b2c3/plan.md')
    expect(detail.body.plan?.tasks).toHaveLength(1)
    expect(detail.body.plan?.approvedAt).toBe(1250)
  })

  it('design.body 含设计文档逐份交付状态（已交/未交；纯展示不参与推进）', () => {
    const req = makeReq({
      artifacts: [{
        stage: 'design', kind: 'design',
        path: 'docs/requirements/REQ-a1b2c3/design/architecture.md',
        registeredAt: 1, registeredBy: HUMAN,
      }],
    })
    const detail = assembleStageDetail(req, LEDGER, 'design')
    if (detail.stage !== 'design') throw new Error('narrow')
    const docs = detail.body.designDocs ?? []
    expect(docs.map(d => d.name)).toEqual(['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md'])
    expect(docs.find(d => d.name === 'architecture.md')?.submitted).toBe(true)
    expect(docs.filter(d => d.submitted)).toHaveLength(1)
  })

  it('design.body：分类模板无设计文档时为空（bug 类）', () => {
    const detail = assembleStageDetail(makeReq({ category: 'bug' }), LEDGER, 'design')
    if (detail.stage !== 'design') throw new Error('narrow')
    expect(detail.body.designDocs).toEqual([])
  })

  it('design.body：策略注入——frontend.md 带 conditional=frontend、豁免项带理由（REQ-2d1c74 FR-1）', () => {
    const detail = assembleStageDetail(makeReq({}), LEDGER, 'design', {
      designDocPolicy: { sides: ['frontend'], exempt: { 'use-cases.md': '纯内部工具无用户场景' } },
    })
    if (detail.stage !== 'design') throw new Error('narrow')
    const docs = detail.body.designDocs ?? []
    expect(docs.find(d => d.name === 'frontend.md')?.conditional).toBe('frontend')
    expect(docs.find(d => d.name === 'backend.md')).toBeUndefined() // 未声明 backend → 不要求
    expect(docs.find(d => d.name === 'use-cases.md')?.exempted).toBe('纯内部工具无用户场景')
  })

  it('decomposing.body 含 decompositionDoc + 任务 DAG + planTasks 对照', () => {
    const task = makeTask({ dependsSummary: '上游产出摘要', cardDoc: 'tasks/t-111111.md', executorHint: 'fresh-window' })
    const req = makeReq({
      artifacts: [{
        stage: 'decomposing', kind: 'decomposition',
        path: 'docs/requirements/REQ-a1b2c3/decomposition.md',
        registeredAt: 1300, registeredBy: HUMAN,
      }],
      plan: {
        path: 'docs/requirements/REQ-a1b2c3/plan.md', summary: 's',
        tasks: [{ key: 't1', title: '任务一', phase: 'implement', side: 'backend', acceptance: '单测绿' }],
        submittedAt: 1200, submittedBy: HUMAN,
      },
    })
    const detail = assembleStageDetail(req, { tasks: [task] }, 'decomposing')
    if (detail.stage !== 'decomposing') throw new Error('narrow')
    expect(detail.body.decompositionDoc).toBe('docs/requirements/REQ-a1b2c3/decomposition.md')
    expect(detail.body.tasks).toHaveLength(1)
    expect(detail.body.tasks[0]?.dependsSummary).toBe('上游产出摘要')
    expect(detail.body.tasks[0]?.cardDoc).toBe('tasks/t-111111.md')
    expect(detail.body.tasks[0]?.executorHint).toBe('fresh-window')
    expect(detail.body.planTasks).toHaveLength(1)
  })

  it('cardDoc 回填（REQ-e72f 断链修复）：任务记录缺 cardDoc 时从 task_detail 产物按约定路径找回（decomposing + implementing）', () => {
    // 存量数据形态：2026-09-24 前 decompose 只登记 task_detail 产物、不写 TaskRecord.cardDoc
    const task = makeTask({})
    const req = makeReq({
      artifacts: [{
        stage: 'implementing', kind: 'task_detail',
        path: 'docs/requirements/REQ-a1b2c3/tasks/t-111111.md',
        registeredAt: 1300, registeredBy: HUMAN,
      }],
    })
    const d1 = assembleStageDetail(req, { tasks: [task] }, 'decomposing')
    if (d1.stage !== 'decomposing') throw new Error('narrow')
    expect(d1.body.tasks[0]?.cardDoc).toBe('docs/requirements/REQ-a1b2c3/tasks/t-111111.md')
    const d2 = assembleStageDetail(req, { tasks: [task] }, 'implementing')
    if (d2.stage !== 'implementing') throw new Error('narrow')
    expect(d2.body.tasks[0]?.cardDoc).toBe('docs/requirements/REQ-a1b2c3/tasks/t-111111.md')
  })

  it('cardDoc 回填不臆造：无对应 task_detail 产物时保持缺失（空态诚实）', () => {
    const detail = assembleStageDetail(makeReq(), { tasks: [makeTask({})] }, 'implementing')
    if (detail.stage !== 'implementing') throw new Error('narrow')
    expect(detail.body.tasks[0]?.cardDoc).toBeUndefined()
  })

  it('implementing.body：tasks 带 executions/claimedBy，byWindow 按窗口码分组', () => {
    const sessionId = 'session-abcdef12-3456-7890-abcd-ef1234567890'
    const task = makeTask({
      claimedBy: sessionId,
      executions: [{
        id: 'e-1', sessionId, trigger: 'manual',
        startedAt: 1500, endedAt: 1600, outcome: 'succeeded', evidence: ['tests/out.txt'],
      }],
    })
    const detail = assembleStageDetail(makeReq(), { tasks: [task] }, 'implementing')
    if (detail.stage !== 'implementing') throw new Error('narrow')
    expect(detail.body.tasks).toHaveLength(1)
    expect(detail.body.tasks[0]?.claimedBy).toBe(sessionId)
    expect(detail.body.tasks[0]?.executions).toHaveLength(1)
    expect(detail.body.tasks[0]?.executions[0]?.outcome).toBe('succeeded')
    // byWindow：claimedBy 窗口码 → 任务 id
    expect(detail.body.byWindow['w-abcdef12']).toEqual(['t-111111'])
  })

  it('accepting.body 含 VerificationRecord（证据 + 人工结论）', () => {
    const req = makeReq({
      status: 'accepting',
      verification: {
        summary: '交付完成', evidence: ['npx vitest run: 188 passed'],
        submittedAt: 2000, submittedBy: { kind: 'agent', sessionId: 'session-abc' },
        reviewedAt: 2100, reviewedBy: HUMAN, decision: 'pass',
      },
    })
    const detail = assembleStageDetail(req, LEDGER, 'accepting')
    if (detail.stage !== 'accepting') throw new Error('narrow')
    expect(detail.body.verification?.decision).toBe('pass')
    expect(detail.body.verification?.evidence).toEqual(['npx vitest run: 188 passed'])
  })

  // REQ-9f4a44：done 节点已移除，原「done.body 含 completedAt + verificationDecision」用例随之删除

  it('archived.body 含 ArchiveRecord（目录/文档清单/合并去向/索引）', () => {
    const req = makeReq({
      status: 'archived',
      archive: {
        dir: 'docs/requirements/REQ-a1b2c3',
        docs: [{ kind: 'requirement', path: 'docs/requirements/REQ-a1b2c3/requirement.md' }],
        mergedInto: ['docs/architecture/project-manual.md'],
        indexEntry: '节点详情接口落地',
        submittedAt: 2000, submittedBy: HUMAN,
        archivedAt: 2100, archivedBy: HUMAN,
      },
    })
    const detail = assembleStageDetail(req, LEDGER, 'archived')
    if (detail.stage !== 'archived') throw new Error('narrow')
    expect(detail.body.archive?.dir).toBe('docs/requirements/REQ-a1b2c3')
    expect(detail.body.archive?.indexEntry).toBe('节点详情接口落地')
  })
})

// ---------------------------------------------------------------------------
// 分类跳过（bug 无 brainstorming 节点）
// ---------------------------------------------------------------------------

describe('assembleStageDetail：分类跳过', () => {
  it('bug 类跳过 brainstorming → enabled:false + 空 body，不报错', () => {
    const req = makeReq({ category: 'bug' })
    const detail = assembleStageDetail(req, LEDGER, 'brainstorming')
    expect(detail.stage).toBe('brainstorming')
    expect(detail.enabled).toBe(false)
    expect(detail.body).toEqual({})
  })

  it('bug 类启用 design → enabled:true', () => {
    const req = makeReq({ category: 'bug' })
    const detail = assembleStageDetail(req, LEDGER, 'design')
    expect(detail.enabled).toBe(true)
  })

  it('spike 类跳过 design/decomposing → enabled:false', () => {
    const req = makeReq({ category: 'spike' })
    for (const stage of ['design', 'decomposing'] as StageKey[]) {
      const detail = assembleStageDetail(req, LEDGER, stage)
      expect(detail.enabled).toBe(false)
      expect(detail.body).toEqual({})
    }
    // spike 启用 implementing
    expect(assembleStageDetail(req, LEDGER, 'implementing').enabled).toBe(true)
  })

  it('feature 类全节点启用', () => {
    const req = makeReq({ category: 'feature' })
    for (const stage of ['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived'] as StageKey[]) {
      expect(assembleStageDetail(req, LEDGER, stage).enabled).toBe(true)
    }
  })
})

// ---------------------------------------------------------------------------
// pendingConfirmation 标记
// ---------------------------------------------------------------------------

describe('assembleStageDetail：pendingConfirmation（四道人工确认门）', () => {
  it('brainstorming 有 requirement 产物未确认 → pendingConfirmation:true', () => {
    const req = makeReq({
      artifacts: [{
        stage: 'brainstorming', kind: 'requirement',
        path: 'docs/requirements/REQ-a1b2c3/requirement.md',
        registeredAt: 1100, registeredBy: HUMAN,
        // 未 confirmedAt
      }],
    })
    const detail = assembleStageDetail(req, LEDGER, 'brainstorming')
    expect(detail.pendingConfirmation).toBe(true)
  })

  it('产物已确认（confirmedAt 写入） → pendingConfirmation:false', () => {
    const req = makeReq({
      artifacts: [{
        stage: 'brainstorming', kind: 'requirement',
        path: 'docs/requirements/REQ-a1b2c3/requirement.md',
        registeredAt: 1100, registeredBy: HUMAN,
        confirmedAt: 1150, confirmedBy: HUMAN,
      }],
    })
    const detail = assembleStageDetail(req, LEDGER, 'brainstorming')
    expect(detail.pendingConfirmation).toBe(false)
  })

  it('无产物 → pendingConfirmation:false', () => {
    const req = makeReq()
    expect(assembleStageDetail(req, LEDGER, 'brainstorming').pendingConfirmation).toBe(false)
  })

  it('bug 类 brainstorming 门未启用 → 即使有产物也不算待确认', () => {
    const req = makeReq({
      category: 'bug',
      artifacts: [{
        stage: 'brainstorming', kind: 'requirement',
        path: 'docs/requirements/REQ-a1b2c3/requirement.md',
        registeredAt: 1100, registeredBy: HUMAN,
      }],
    })
    const detail = assembleStageDetail(req, LEDGER, 'brainstorming')
    expect(detail.enabled).toBe(false)
    expect(detail.pendingConfirmation).toBe(false)
  })

  it('accepting 有 verification 产物未确认 → pendingConfirmation:true（accepting>done 门）', () => {
    const req = makeReq({
      status: 'accepting',
      artifacts: [{
        stage: 'accepting', kind: 'verification',
        path: 'docs/requirements/REQ-a1b2c3/verification.md',
        registeredAt: 2000, registeredBy: HUMAN,
      }],
    })
    const detail = assembleStageDetail(req, LEDGER, 'accepting')
    expect(detail.pendingConfirmation).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// 路由：GET /requirements/:id/stage/:stage
// ---------------------------------------------------------------------------

describe('路由 GET /requirements/:id/stage/:stage', () => {
  let dir: string
  let store: ReqboardStore

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'pmboard-stage-'))
    store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  })
  afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

  function fakeReq(url: string): any {
    const req = new EventEmitter() as any
    req.url = url
    req.method = 'GET'
    req[Symbol.asyncIterator] = async function* () { /* no body */ }
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
    await handler(fakeReq(`/dashboard/api/reqboard${url}`), res)
    return res
  }

  it('7 节点 GET 均返回 200 + 契约块', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    // 建需求（默认 feature 分类，全流水线）
    const created = await (async () => {
      const req = new EventEmitter() as any
      req.url = '/dashboard/api/reqboard/req/create'
      req.method = 'POST'
      req[Symbol.asyncIterator] = async function* () { yield Buffer.from(JSON.stringify({ title: '路由测试需求' }), 'utf8') }
      const res = fakeRes()
      await handler(req, res)
      return res.payload.data as RequirementRecord
    })()
    const stages: StageKey[] = ['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived']
    for (const stage of stages) {
      const res = await get(handler, `/requirements/${created.id}/stage/${stage}`)
      expect(res.statusCode).toBe(200)
      expect(res.payload.success).toBe(true)
      expect(res.payload.data.stage).toBe(stage)
      expect(typeof res.payload.data.enabled).toBe('boolean')
      expect(Array.isArray(res.payload.data.artifacts)).toBe(true)
      expect(Array.isArray(res.payload.data.timeline)).toBe(true)
      expect(typeof res.payload.data.pendingConfirmation).toBe('boolean')
      expect(res.payload.data.body).toBeDefined()
    }
  })

  it('需求不存在 → 404 not_found', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const res = await get(handler, '/requirements/REQ-ffffff/stage/draft')
    expect(res.statusCode).toBe(404)
    expect(res.payload.code).toBe('not_found')
  })

  it('stage 非法 → 400 invalid_input', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    // 先建一个需求
    const req = new EventEmitter() as any
    req.url = '/dashboard/api/reqboard/req/create'
    req.method = 'POST'
    req[Symbol.asyncIterator] = async function* () { yield Buffer.from(JSON.stringify({ title: 'x' }), 'utf8') }
    const res1 = fakeRes()
    await handler(req, res1)
    const id = res1.payload.data.id as string

    const res = await get(handler, `/requirements/${id}/stage/not-a-stage`)
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('invalid_input')
  })

  it('design 节点路由：读 requirement.md front-matter 注入策略（conditional/exempted 进投影）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now(), cwd: dir })
    mkdirSync(join(dir, 'docs/requirements/REQ-a1b2c3'), { recursive: true })
    writeFileSync(join(dir, 'docs/requirements/REQ-a1b2c3/requirement.md'),
      '---\nsides: frontend\ndesign_exempt: use-cases.md=纯内部工具无用户场景\n---\n\n# 需求\n')
    await store.mutate('requirement-created', (l) => {
      l.requirements.push(makeReq({ status: 'design' }))
      return { requirements: [l.requirements[l.requirements.length - 1]!] }
    })
    const res = await get(handler, '/requirements/REQ-a1b2c3/stage/design')
    expect(res.statusCode).toBe(200)
    const docs = res.payload.data.body.designDocs as Array<{ name: string; conditional?: string; exempted?: string }>
    expect(docs.find(d => d.name === 'frontend.md')?.conditional).toBe('frontend')
    expect(docs.find(d => d.name === 'use-cases.md')?.exempted).toBe('纯内部工具无用户场景')
  })

  it('分类跳过态经路由返回 enabled:false（bug 类 brainstorming）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    // 建 bug 类需求（直接写库，绕过默认创建）
    await store.mutate('requirement-created', (l) => {
      l.requirements.push(makeReq({ id: 'REQ-bug001', category: 'bug', status: 'design' }))
      return { requirements: [l.requirements[l.requirements.length - 1]!] }
    })
    const res = await get(handler, '/requirements/REQ-bug001/stage/brainstorming')
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.enabled).toBe(false)
    expect(res.payload.data.body).toEqual({})
  })
})
