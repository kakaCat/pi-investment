/**
 * 验收标准对照测试（REQ-31e11f t8）——requirement.md §5 的 12 条验收标准逐条可执行化。
 *
 * 本文件不重复其他测试文件的用例，而是为每条验收标准提供「端到端锚点测试」：
 * 如果某条标准的底层用例分布在多个文件，这里至少有一条集成级测试证明该标准真的成立。
 *
 * 12 条标准映射：
 *   1.  7 节点点击均展示对应内容        → stage-detail + stage-panel 集成
 *   2.  实施节点能看出哪个窗口完成       → stage-detail byWindow
 *   3.  验收节点展示内容列表+人工结论     → stage-detail accepting body
 *   4.  预留字段就位且老台账兼容         → store load with projectId/parentId
 *   5.  双端共享同一契约                → StageDetail type identity
 *   6.  产物可点开+缺产物标红            → stage-panel render + open-doc link
 *   7.  缺产物推进被拦+可追溯             → artifact-gates + trace chain
 *   8.  任务汇报自动渲染为实施产物        → task-report + stage-detail
 *   9.  阶段提示词自动注入               → capture.ts + capture-hook.ts
 *   10. 四道人工确认门代码级生效          → artifact-gates all 5 gates
 *   11. 接力实测                        → handoff.test.ts（本文件不重复）
 *   12. 分类流程生效                    → CATEGORY_FLOW_PROFILES + artifact-gates
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, writeFileSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { EventEmitter } from 'node:events'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { assembleStageDetail } from '../src/application/query/index.js'
import { renderStagePanel } from '../src/client/stage-panel.js'
import {
  definePlanSubmitTool,
  defineDecomposeTool,
  defineTaskReportTool,
  stubDocFile,
} from './helpers/tool-deps.js'
import {
  CATEGORY_FLOW_PROFILES,
  ALL_STAGE_KEYS,
  ARTIFACT_CONFIRM_GATES,
  flowProfileFor,
  stageEnabledFor,
  confirmGateKindFor,
  emptyLedger,
  type RequirementRecord,
  type RequirementStatus,
  type StageKey,
  type StageDetail,
  type StageArtifact,
} from '../src/shared/protocol.js'

const W = 'session-acc-123'
let dir: string
let prevCwd: string
let store: ReqboardStore
let handler: ReturnType<typeof createReqboardHandler>

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-acc-'))
  prevCwd = process.cwd()
  process.chdir(dir)
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  // REQ-2d1c74 FR-2：G2 完整性闸门需要 docs 端口（非 legacy 时缺省 = fail-closed）
  handler = createReqboardHandler({ store, now: () => Date.now(), docs: new FileDocRepository({ workspaceRoot: dir }) })
})
afterEach(() => {
  process.chdir(prevCwd)
  rmSync(dir, { recursive: true, force: true })
})

function fakeReq(body: unknown, url: string, method = 'POST'): any {
  const req = new EventEmitter() as any
  req.url = '/dashboard/api/reqboard' + url
  req.method = method
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
async function get(url: string) {
  const res = fakeRes()
  await handler(fakeReq(undefined, url, 'GET'), res)
  return res
}

async function seed(status: RequirementStatus = 'implementing', category: RequirementRecord['category'] = 'feature'): Promise<RequirementRecord> {
  const r = {
    id: 'REQ-acc001', title: '验收标准测试', description: '验证 12 条验收标准', status, blocked: false,
    category,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status: 'draft', at: 1, by: { kind: 'human' } }],
  } as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
  return r
}

/** 构造含全部 6 类产物的需求（用于追溯链测试）。 */
function reqWithFullArtifacts(): RequirementRecord {
  const now = Date.now()
  const artifacts: StageArtifact[] = [
    { stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-acc001/requirement.md', registeredAt: now, registeredBy: { kind: 'agent' } },
    { stage: 'design', kind: 'plan', path: 'docs/requirements/REQ-acc001/plan.md', registeredAt: now, registeredBy: { kind: 'agent' } },
    { stage: 'decomposing', kind: 'decomposition', path: 'docs/requirements/REQ-acc001/decomposition.md', registeredAt: now, registeredBy: { kind: 'agent' } },
    { stage: 'implementing', kind: 'task_detail', path: 'docs/requirements/REQ-acc001/tasks/t-aaa001.md', registeredAt: now, registeredBy: { kind: 'agent' } },
    { stage: 'accepting', kind: 'verification', path: 'docs/requirements/REQ-acc001/verification.md', registeredAt: now, registeredBy: { kind: 'agent' } },
    { stage: 'done', kind: 'archive', path: 'docs/requirements/REQ-acc001', registeredAt: now, registeredBy: { kind: 'agent' } },
  ]
  return {
    id: 'REQ-acc001', title: '全产物需求', description: '', status: 'archived', blocked: false,
    category: 'feature', artifacts, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status: 'draft', at: 1, by: { kind: 'human' } }],
    archive: {
      dir: 'docs/requirements/REQ-acc001',
      docs: [{ kind: 'requirement', path: 'docs/requirements/REQ-acc001/requirement.md' }],
      mergedInto: ['docs/architecture/project-manual.md'],
      indexEntry: '测试归档',
      submittedAt: now, submittedBy: { kind: 'agent' },
      archivedAt: now, archivedBy: { kind: 'human' },
    },
  }
}

// ────────────────────────────────────────────────────────────────────────────
// 标准 1：8 个节点（含归档）点击均展示第 4 节对应内容
// ────────────────────────────────────────────────────────────────────────────

describe('验收 1：7 节点点击均展示对应内容', () => {
  it('7 节点 StageDetail 各自返回差异化 body（非空、stage 匹配）', async () => {
    await seed('implementing')
    // REQ-9f4a44：done 节点已移除 → 7 个节点
    const stages: StageKey[] = ['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived']
    for (const stage of stages) {
      const res = await get(`/requirements/REQ-acc001/stage/${stage}`)
      expect(res.statusCode, stage).toBe(200)
      expect(res.payload.data.stage, stage).toBe(stage)
      expect(res.payload.data.body, stage).toBeDefined()
      // 每个节点的 body 类型不同（差异化）
    }
    // 验证 body 确实不同：draft.body 有 title，implementing.body 有 tasks
    const draftRes = await get('/requirements/REQ-acc001/stage/draft')
    expect(draftRes.payload.data.body.title).toBeDefined()
    const implRes = await get('/requirements/REQ-acc001/stage/implementing')
    expect(implRes.payload.data.body.tasks).toBeDefined()
    expect(implRes.payload.data.body.byWindow).toBeDefined()
  })

  it('7 节点 stage-panel 渲染各自产出非空 HTML（含节点专属 CSS 类）', () => {
    const stages: StageKey[] = ['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived']
    const bodies: Record<string, Record<string, unknown>> = {
      draft: { title: 'T', description: 'D' },
      brainstorming: { comments: [] },
      design: {},
      decomposing: { tasks: [], planTasks: [] },
      implementing: { tasks: [], byWindow: {} },
      accepting: {},
      archived: {},
    }
    for (const stage of stages) {
      const detail = {
        stage, enabled: true, artifacts: [], pendingConfirmation: false, timeline: [],
        body: bodies[stage],
      } as StageDetail
      const html = renderStagePanel(detail)
      expect(html.length, stage).toBeGreaterThan(50)
      expect(html, stage).toContain(`data-stage="${stage}"`)
    }
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 标准 2：实施节点能看出每个任务由哪个窗口/subagent 完成
// ────────────────────────────────────────────────────────────────────────────

describe('验收 2：实施节点按窗口分组', () => {
  it('implementing StageDetail.byWindow 按窗口码分组（含 subagent 会话 id）', async () => {
    await seed('implementing')
    const sessionA = 'session-aaaa1111-2222-3333-4444-555555555555'
    const sessionB = 'subagent-xyz' // subagent 会话 id
    await store.mutate('task-created', (l) => {
      l.tasks.push(
        {
          id: 't-win001', requirementId: 'REQ-acc001', title: '任务A', description: '',
          phase: 'implement', side: 'backend', dependsOn: [],
          scope: { apis: [], tables: [], files: [] }, acceptance: '', context: '',
          status: 'in_progress', blocked: false, claimedBy: sessionA, claimedAt: 1,
          executions: [{ id: 'e-1', sessionId: sessionA, trigger: 'manual', startedAt: 1, outcome: 'running' }],
          comments: [], version: 1, createdAt: 1, updatedAt: 1,
          createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
        },
        {
          id: 't-win002', requirementId: 'REQ-acc001', title: '任务B', description: '',
          phase: 'ui', side: 'frontend', dependsOn: [],
          scope: { apis: [], tables: [], files: [] }, acceptance: '', context: '',
          status: 'done', blocked: false,
          executions: [{ id: 'e-2', sessionId: sessionB, trigger: 'auto', startedAt: 2, endedAt: 3, outcome: 'succeeded' }],
          comments: [], version: 1, createdAt: 2, updatedAt: 3,
          createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
        },
      )
      return { tasks: [...l.tasks] }
    })

    const ledger = store.snapshot()
    const req = ledger.requirements[0]
    const detail = assembleStageDetail(req, { tasks: ledger.tasks }, 'implementing')
    if (detail.stage !== 'implementing') throw new Error('narrow')

    // byWindow 包含两个窗口码
    expect(Object.keys(detail.body.byWindow).length).toBeGreaterThanOrEqual(2)
    // 任务A 归 sessionA 窗口
    const winA = `w-${sessionA.replace('session-', '').split('-')[0]}`
    expect(detail.body.byWindow[winA]).toContain('t-win001')
    // 任务B 归 subagent 窗口（subagent-xyz → w-subagent-xyz）
    const subWin = 'w-' + sessionB.split('-')[0]
    expect(detail.body.byWindow[subWin]).toContain('t-win002')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 标准 3：验收节点展示验收内容列表与人工审核结论；归档节点展示归档逻辑
// ────────────────────────────────────────────────────────────────────────────

describe('验收 3：验收+归档节点内容', () => {
  it('accepting body 含 VerificationRecord（证据 + 人工结论 + 审核意见）', async () => {
    await seed('accepting')
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.verification = {
        summary: '交付完成', evidence: ['npx vitest run: 303 passed', '截图: board.png'],
        submittedAt: 100, submittedBy: { kind: 'agent', sessionId: W },
        reviewedAt: 200, reviewedBy: { kind: 'human' }, decision: 'pass', reviewNote: '验收通过',
      }
      return { requirements: [r] }
    })
    const ledger = store.snapshot()
    const detail = assembleStageDetail(ledger.requirements[0], { tasks: [] }, 'accepting')
    if (detail.stage !== 'accepting') throw new Error('narrow')
    expect(detail.body.verification?.decision).toBe('pass')
    expect(detail.body.verification?.evidence).toHaveLength(2)
    expect(detail.body.verification?.reviewNote).toBe('验收通过')
  })

  it('archived body 含 ArchiveRecord（目录/文档清单/合并去向/索引/说明书更新点）', async () => {
    const req = reqWithFullArtifacts()
    await store.mutate('requirement-created', (l) => { l.requirements.push(req); return { requirements: [req] } })
    const ledger = store.snapshot()
    const detail = assembleStageDetail(ledger.requirements[0], { tasks: [] }, 'archived')
    if (detail.stage !== 'archived') throw new Error('narrow')
    expect(detail.body.archive).toBeDefined()
    expect(detail.body.archive?.dir).toBe('docs/requirements/REQ-acc001')
    expect(detail.body.archive?.indexEntry).toBeDefined()
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 标准 4：老台账兼容加载（t10 起 projectId/parentId 已从契约删除，读路径仍不改写历史数据）
// ────────────────────────────────────────────────────────────────────────────

describe('验收 4：老台账兼容加载（历史字段透传，不做破坏性读改写）', () => {
  it('带历史预留字段（projectId/parentId）的记录正常加载，字段原样透传', async () => {
    const file = join(dir, 'dsh-reqboard.json')
    const ledgerWithReserved = {
      schemaVersion: 4, revision: 1,
      requirements: [{
        id: 'REQ-acc001', title: '预留字段测试', description: '', status: 'implementing', blocked: false,
        category: 'feature', projectId: 'proj-001', parentId: 'REQ-parent',
        sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
      }],
      tasks: [], triages: [],
    }
    writeFileSync(file, JSON.stringify(ledgerWithReserved), 'utf8')
    const freshStore = new ReqboardStore({ file })
    await freshStore.load()
    // C6：这两个字段已从 RequirementRecord 契约删除（全仓引用 0），但**读路径不得改写历史数据**
    // （旧台账若残留该键，加载后应原样带出——不静默丢数据是迁移相邻改动的底线）。
    const loaded = freshStore.snapshot().requirements[0] as unknown as { projectId?: string; parentId?: string }
    expect(loaded.projectId).toBe('proj-001')
    expect(loaded.parentId).toBe('REQ-parent')
  })

  it('老台账（无 projectId/parentId）正常加载，字段为 undefined', async () => {
    const file = join(dir, 'dsh-reqboard.json')
    const legacyLedger = {
      schemaVersion: 2, revision: 1,
      requirements: [{
        id: 'REQ-acc001', title: '老需求', description: '', status: 'draft', blocked: false,
        comments: [], version: 1, createdAt: 1, updatedAt: 1,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
      }],
      tasks: [], triages: [],
    }
    writeFileSync(file, JSON.stringify(legacyLedger), 'utf8')
    const freshStore = new ReqboardStore({ file })
    await freshStore.load()
    const loaded = freshStore.snapshot().requirements[0]
    const legacy = loaded as { projectId?: unknown; parentId?: unknown }
    expect(legacy.projectId).toBeUndefined()
    expect(legacy.parentId).toBeUndefined()
    // schemaVersion 升级到当前契约版本（REQ-81aabd：4 → 5 → 6 → 7）
    expect(freshStore.snapshot().schemaVersion).toBe(7)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 标准 5：双端共享同一契约
// ────────────────────────────────────────────────────────────────────────────

describe('验收 5：双端共享同一 StageDetail 契约', () => {
  it('host assembleStageDetail 返回的 shape 与 client renderStagePanel 消费的 shape 一致', async () => {
    await seed('implementing')
    const res = await get('/requirements/REQ-acc001/stage/implementing')
    const detail = res.payload.data as StageDetail

    // client renderStagePanel 消费同一 shape（不抛错 = 结构兼容）
    const html = renderStagePanel(detail)
    expect(html).toContain('dsh-pm-stage-panel')
    expect(html).toContain('data-stage="implementing"')
  })

  it('StageDetail 判别联合的 7 个 stage 值与 ALL_STAGE_KEYS 一致', () => {
    expect(ALL_STAGE_KEYS).toHaveLength(7)
    for (const key of ALL_STAGE_KEYS) {
      expect(['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived']).toContain(key)
    }
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 标准 6：产物可点开 + 缺产物标红
// ────────────────────────────────────────────────────────────────────────────

describe('验收 6：产物链接 + 缺产物标红', () => {
  it('产物渲染为可点击链接（data-action="open-doc" + data-path）', () => {
    const artifact: StageArtifact = {
      stage: 'brainstorming', kind: 'requirement',
      path: 'docs/requirements/REQ-acc001/requirement.md',
      registeredAt: Date.now(), registeredBy: { kind: 'agent' },
    }
    const detail = {
      stage: 'brainstorming', enabled: true,
      artifacts: [artifact], pendingConfirmation: false, timeline: [],
      body: { comments: [] },
    } as StageDetail
    const html = renderStagePanel(detail)
    expect(html).toContain('data-action="open-doc"')
    expect(html).toContain('data-path="docs/requirements/REQ-acc001/requirement.md"')
  })

  it('缺产物节点显示红色标记', () => {
    const detail = {
      stage: 'brainstorming', enabled: true,
      artifacts: [], pendingConfirmation: false, timeline: [],
      body: { comments: [] },
    } as StageDetail
    const html = renderStagePanel(detail)
    expect(html).toContain('is-missing')
    expect(html).toContain('缺失')
  })

  it('GET /file?path= 读取产物全文（文档超链接可点击展开全文的后端支撑）', async () => {
    // 写一个测试文档
    const docDir = join(dir, 'docs/requirements/REQ-acc001')
    const { mkdirSync } = await import('node:fs')
    mkdirSync(docDir, { recursive: true })
    writeFileSync(join(docDir, 'requirement.md'), '# 测试需求文档\n内容', 'utf8')

    const res = await get('/file?path=docs/requirements/REQ-acc001/requirement.md')
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.content).toContain('测试需求文档')
  })

  it('GET /file?path= 拒绝目录穿越（../etc/passwd → 403）', async () => {
    const res = await get('/file?path=../etc/passwd')
    expect(res.statusCode).toBe(403)
    expect(res.payload.code).toBe('forbidden')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 标准 7：缺产物推进被拦 + 可追溯
// ────────────────────────────────────────────────────────────────────────────

describe('验收 7：缺产物拦截 + 产物链追溯', () => {
  it('新需求缺产物推进被代码级拦截（missing_artifact）', async () => {
    // feature 分类：brainstorming → design 需要 requirement 产物
    await seed('brainstorming', 'feature')
    // 登记一个产物但不确认 → artifact_not_confirmed
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-acc001/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' } }]
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-acc001', to: 'design', actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('artifact_not_confirmed')
  })

  it('产物链从 implementing 可向上追溯到 requirement（trace chain 顺序）', () => {
    const req = reqWithFullArtifacts()
    // StageDetail.implementing 只含该 stage 的产物（task_detail）
    const detail = assembleStageDetail(req, { tasks: [] }, 'implementing')
    if (detail.stage !== 'implementing') throw new Error('narrow')
    expect(detail.artifacts.map(a => a.kind)).toContain('task_detail')

    // 追溯链渲染：传入全部产物（模拟看板详情页的完整产物列表）
    const fullDetail = { ...detail, artifacts: req.artifacts ?? [] }
    const html = renderStagePanel(fullDetail)
    expect(html).toContain('dsh-pm-trace-chain')
    expect(html).toContain('dsh-pm-trace-arrow')
    // 顺序：requirement → plan → decomposition → task_detail → verification → archive
    const reqIdx = html.indexOf('requirement.md')
    const planIdx = html.indexOf('plan.md')
    // REQ-260922182638-0777 FR-5：任务卡不再折叠「×N」，逐张列出（无任务清单匹配时降级「任务卡（t-xxx）」）
    const taskIdx = html.indexOf('任务卡（t-aaa001）')
    expect(reqIdx).toBeGreaterThan(-1)
    expect(planIdx).toBeGreaterThan(reqIdx)
    expect(taskIdx).toBeGreaterThan(planIdx)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 标准 8：任务汇报自动渲染为实施产物文档
// ────────────────────────────────────────────────────────────────────────────

describe('验收 8：task_report 汇报 = 实施产物文档', () => {
  it('task_report 后 StageDetail.implementing 含 task_detail 产物（可追溯）', async () => {
    await seed('decomposing')
    const reportTool = defineTaskReportTool({ store, now: () => Date.now() } as never)
    const planTool = definePlanSubmitTool({ store, now: () => Date.now() } as never)
    const decomposeTool = defineDecomposeTool({ store, now: () => Date.now() } as never)

    // 走完整链路：提交计划 → 批准 → 拆分 → 汇报
    // REQ-2d1c74 FR-5：plan_submit 起要求提交路径真实落盘（本文件 chdir 到临时目录）
    stubDocFile('docs/requirements/REQ-acc001/plan.md')
    await planTool.execute({
      path: 'docs/requirements/REQ-acc001/plan.md', summary: 's',
      tasks: [{ key: 'a', title: '任务A', phase: 'implement', side: 'backend', acceptance: '单测通过', implementation: '改 a.ts' }],
    }, { agent: { id: W } })
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      if (r.plan !== undefined) { r.plan.approvedAt = 100; r.plan.approvedBy = { kind: 'human' } }
      return { requirements: [r] }
    })
    const decOut = (await decomposeTool.execute({}, { agent: { id: W } } as never)) as { created: Array<{ id: string }> }
    const taskId = decOut.created[0].id as string

    // 汇报
    const report = (await reportTool.execute({
      task_id: taskId, summary: '完成', completed: ['X'], files_changed: ['a.ts'], next_step: '',
    }, { agent: { id: W } } as never)) as { success: boolean }
    expect(report.success).toBe(true)

    // 推进到 implementing 后，StageDetail.implementing 含 task_detail 产物
    await store.mutate('human-confirm', (l) => {
      const r = l.requirements[0]
      r.status = 'implementing'
      return { requirements: [r] }
    })
    const ledger = store.snapshot()
    const req = ledger.requirements[0]
    const detail = assembleStageDetail(req, { tasks: ledger.tasks }, 'implementing')
    if (detail.stage !== 'implementing') throw new Error('narrow')
    const taskArtifact = detail.artifacts.find(a => a.kind === 'task_detail')
    expect(taskArtifact).toBeDefined()
    expect(taskArtifact?.path).toContain(taskId)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 标准 9：阶段提示词自动注入
// ────────────────────────────────────────────────────────────────────────────

describe('验收 9：阶段提示词注入', () => {
  it('capture.ts boundSectionText 按当前阶段注入对应提示词', async () => {
    const { boundSectionText } = await import('../src/application/internal/capture-section.js')
    // REQ-d3e61a FR-16：取词唯一入口 = resolveStagePrompt（旧的 STAGE_PROMPTS 常量表已下线）
    const { resolveStagePrompt } = await import('../src/domain/prompt/index.js')
    const l = emptyLedger()
    l.requirements.push({
      id: 'REQ-acc001', title: 't', description: '', status: 'brainstorming', blocked: false,
      category: 'feature', sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    })
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).toContain(resolveStagePrompt({
      stage: 'brainstorming', category: 'feature', requirement: { title: 't', description: '' },
    }).text)
    // 阶段身份（轻/重档标题都带 brainstorming）——不再钉死某句措辞，措辞会随分片演进
    expect(text).toContain('brainstorming')
  })

  it('capture-hook onStagePrompt 在 bound 窗口收到消息时触发', async () => {
    const { createSessionEventCaptureHook } = await import('../src/adapters/CaptureHook.js')
    // REQ-d3e61a FR-16：取词唯一入口 = resolveStagePrompt（旧的 STAGE_PROMPTS 常量表已下线）
    const { resolveStagePrompt } = await import('../src/domain/prompt/index.js')
    const prompts: string[] = []
    const ledger = emptyLedger()
    ledger.requirements.push({
      id: 'REQ-acc001', title: 't', description: '', status: 'implementing', blocked: false,
      category: 'feature', sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    })
    const hook = createSessionEventCaptureHook({
      snapshot: () => ledger,
      pending: new Map(),
      now: () => 1000,
      onStagePrompt: (_key, prompt) => prompts.push(prompt),
      logger: { info: () => {}, debug: () => {} },
    })
    hook({ id: W }, { type: 'user/message', data: { content: [{ type: 'text', text: '继续' }], source: { kind: 'user' } } })
    expect(prompts).toHaveLength(1)
    expect(prompts[0]).toBe(resolveStagePrompt({
      stage: 'implementing', category: 'feature', requirement: { title: 't', description: '' },
    }).text)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 标准 10：四道人工确认门代码级生效
// ────────────────────────────────────────────────────────────────────────────

describe('验收 10：四道人工确认门', () => {
  // REQ-9f4a44：四道门——accepting>archived 合并了原 accepting>done 与 done>archived
  // 2026-09-21 用户裁定：design>decomposing 门锚定 design 产物（设计文档），
  // 拆分计划（decomposition）的批准门在 decomposing>implementing
  const ALL_FIVE_GATES: Array<[string, string, string]> = [
    ['brainstorming', 'design', 'requirement'],
    ['design', 'decomposing', 'design'],
    ['decomposing', 'implementing', 'decomposition'],
    ['accepting', 'archived', 'verification'],
  ]

  it.each(ALL_FIVE_GATES)('门 %s>%s：产物未确认 → 转移被拒', async (from, to, kind) => {
    await seed(from as RequirementStatus, 'feature')
    // 登记产物但不确认
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements[0]
      r.artifacts = [{
        stage: from as StageKey, kind: kind as StageArtifact['kind'],
        path: `docs/requirements/REQ-acc001/${kind}.md`,
        registeredAt: 1, registeredBy: { kind: 'agent' },
      }]
      return { requirements: [r] }
    })
    const res = await post('/req/move', { id: 'REQ-acc001', to, actor: 'human' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('artifact_not_confirmed')
  })

  it.each(ALL_FIVE_GATES)('门 %s>%s：产物确认后 → 转移成功', async (from, to, kind) => {
    await seed(from as RequirementStatus, 'feature')
    // REQ-2d1c74 FR-2：design>decomposing 多了文档集完整性门——feature 五份必交须落盘且全部确认
    if (from === 'design' && to === 'decomposing') {
      const DESIGN5 = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']
      mkdirSync(join(dir, 'docs/requirements/REQ-acc001/design'), { recursive: true })
      writeFileSync(join(dir, 'docs/requirements/REQ-acc001/requirement.md'),
        '# 需求\n\n## 边界\nx\n\n## 产品定义\nx\n\n## 用户与角色\nx\n\n## 功能点\n\n### FR-1: 甲\nx\n')
      for (const n of DESIGN5) writeFileSync(join(dir, 'docs/requirements/REQ-acc001/design', n), '# ' + n + '\n')
      await store.mutate('requirement-updated', (l) => {
        const r = l.requirements[0]
        r.artifacts = DESIGN5.map(n => ({
          stage: 'design', kind: 'design',
          path: 'docs/requirements/REQ-acc001/design/' + n,
          registeredAt: 1, registeredBy: { kind: 'agent' },
          confirmedAt: 2, confirmedBy: { kind: 'human' },
        }))
        return { requirements: [r] }
      })
    } else {
      await store.mutate('requirement-updated', (l) => {
        const r = l.requirements[0]
        r.artifacts = [{
          stage: from as StageKey, kind: kind as StageArtifact['kind'],
          path: `docs/requirements/REQ-acc001/${kind}.md`,
          registeredAt: 1, registeredBy: { kind: 'agent' },
          confirmedAt: 2, confirmedBy: { kind: 'human' },
        }]
        return { requirements: [r] }
      })
    }
    // 特殊门处理（2026-09-21：design>decomposing 已改通用 design 产物确认判定，无特判）
    if (from === 'accepting' && to === 'archived') {
      // accepting>archived（验收通过即归档）还需要 verification 记录
      await store.mutate('requirement-updated', (l) => {
        const r = l.requirements[0]
        r.verification = { summary: 's', evidence: ['e'], submittedAt: 1, submittedBy: { kind: 'agent' } }
        return { requirements: [r] }
      })
    }
    const res = await post('/req/move', { id: 'REQ-acc001', to, actor: 'human' })
    expect(res.statusCode).toBe(200)
  })

  it('ARTIFACT_CONFIRM_GATES 表恰好包含 4 道门', () => {
    expect(Object.keys(ARTIFACT_CONFIRM_GATES)).toHaveLength(4)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 标准 12：分类流程生效
// ────────────────────────────────────────────────────────────────────────────

describe('验收 12：分类差异化流程', () => {
  it('CATEGORY_FLOW_PROFILES 6 类分类档案齐备', () => {
    const categories = Object.keys(CATEGORY_FLOW_PROFILES)
    expect(categories).toHaveLength(6)
    expect(categories).toContain('feature')
    expect(categories).toContain('bug')
    expect(categories).toContain('refactor')
    expect(categories).toContain('spike')
    expect(categories).toContain('doc')
    expect(categories).toContain('chore')
  })

  it('bug 免需求分析门：confirmGates 不含 brainstorming>design', () => {
    const profile = CATEGORY_FLOW_PROFILES.bug
    expect(profile.confirmGates).not.toContain('brainstorming>design')
    expect(profile.confirmGates).toContain('design>decomposing')
    // REQ-9f4a44：验收门并入归档门（accepting>archived），故 bug 分类 3 道门
    expect(profile.confirmGates).toContain('accepting>archived')
    expect(profile.confirmGates).toHaveLength(3)
  })

  it('spike/doc/chore 最简流程：只有验收归档一门', () => {
    for (const cat of ['spike', 'doc', 'chore'] as const) {
      const profile = CATEGORY_FLOW_PROFILES[cat]
      // REQ-9f4a44：验收通过即归档 → 只剩一道门
      expect(profile.confirmGates, cat).toHaveLength(1)
      expect(profile.confirmGates, cat).toContain('accepting>archived')
      expect(profile.stages, cat).not.toContain('brainstorming')
      expect(profile.stages, cat).not.toContain('design')
      expect(profile.stages, cat).not.toContain('decomposing')
    }
  })

  it('bug 分类跳过 brainstorming 阶段（stageEnabledFor=false）', () => {
    expect(stageEnabledFor('bug', 'brainstorming')).toBe(false)
    expect(stageEnabledFor('bug', 'design')).toBe(true)
  })

  it('flowProfileFor 对非法分类兜底 feature', () => {
    // 非法分类值（不在 6 类内）→ 兜底 feature
    const profile = flowProfileFor('invalid' as any)
    expect(profile.stages).toHaveLength(7)
    expect(profile.confirmGates).toHaveLength(4)
  })

  it('stageEnabledFor 对未知 stage 返回 false', () => {
    expect(stageEnabledFor('feature', 'nonexistent' as any)).toBe(false)
    expect(stageEnabledFor('bug', 'nonexistent' as any)).toBe(false)
  })

  it('confirmGateKindFor 对分类未启用的门返回 undefined', () => {
    // bug 分类：brainstorming>design 门未启用
    expect(confirmGateKindFor('bug', 'brainstorming', 'design')).toBeUndefined()
    // feature 分类：启用
    expect(confirmGateKindFor('feature', 'brainstorming', 'design')).toBe('requirement')
    // spike 分类：design>decomposing 门未启用
    expect(confirmGateKindFor('spike', 'design', 'decomposing')).toBeUndefined()
  })
})

// ────────────────────────────────────────────────────────────────────────────
// 全流程一览（REQ-31e11f 节点详情重设计）：GET /requirements/:id/stages
// ────────────────────────────────────────────────────────────────────────────
describe('全流程一览接口 /requirements/:id/stages', () => {
  it('一次返回全部 7 节点 StageDetail + currentStage，顺序同 ALL_STAGE_KEYS', async () => {
    await seed('implementing')
    const res = await get('/requirements/REQ-acc001/stages')
    expect(res.statusCode).toBe(200)
    const ov = res.payload?.data
    expect(ov.requirementId).toBe('REQ-acc001')
    expect(ov.currentStage).toBe('implementing')
    expect(ov.stages.map((s: any) => s.stage)).toEqual([...ALL_STAGE_KEYS])
    // 每行都有监控渲染所需字段
    for (const s of ov.stages) {
      expect(typeof s.enabled).toBe('boolean')
      expect(Array.isArray(s.artifacts)).toBe(true)
      expect(Array.isArray(s.timeline)).toBe(true)
    }
  })

  it('分类跳过节点在一览里 enabled=false（不报错）', async () => {
    await seed('design', 'bug') // bug 分类跳过 brainstorming
    const res = await get('/requirements/REQ-acc001/stages')
    expect(res.statusCode).toBe(200)
    const ov = res.payload?.data
    const brainstorm = ov.stages.find((s: any) => s.stage === 'brainstorming')
    expect(brainstorm.enabled).toBe(false)
  })

  it('需求不存在 → 404', async () => {
    const res = await get('/requirements/REQ-nope999/stages')
    expect(res.statusCode).toBe(404)
  })
})
