/**
 * 接力实测（REQ-31e11f t8 核心）——验证 handoff 契约让新窗口零会话历史即可续作。
 *
 * 场景模拟（借鉴 Claude Code Task 模式）：
 *   1. 窗口 A 完成需求分析 + 设计 + 拆分（decompose 生成任务卡骨架 tasks/t-xxx.md）；
 *   2. 窗口 A 完成任务 t1 并 task_report 汇报；
 *   3. 窗口 B（新窗口/新 agent，零会话历史）仅凭任务卡 + 产物链接手任务 t2；
 *   4. 验证：任务卡自足（含验收标准+上游产出摘要）、task_report 追加后文件仍结构化、
 *      dependsSummary 反映依赖链。
 *
 * 验收标准对照：requirement.md §5.11「接力实测」。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, readFileSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import {
  definePlanSubmitTool,
  defineDecomposeTool,
  defineTaskMoveTool,
  defineTaskReportTool,
  stubDocFile,
} from './helpers/tool-deps.js'
import { assembleStageDetail } from '../src/application/query/index.js'
import type { RequirementRecord, RequirementStatus } from '../src/shared/protocol.js'

const WINDOW_A = 'session-aaaa1111-2222-3333-4444-555555555555'
const WINDOW_B = 'session-bbbb6666-7777-8888-9999-000000000000'

let dir: string
let prevCwd: string
let store: ReqboardStore
let planTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let decompose: { execute: (a: unknown, e: unknown) => Promise<any> }
let taskMove: { execute: (a: unknown, e: unknown) => Promise<any> }
let taskReport: { execute: (a: unknown, e: unknown) => Promise<any> }

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-handoff-'))
  prevCwd = process.cwd()
  process.chdir(dir)
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  const deps = { store, now: () => Date.now() } as never
  planTool = definePlanSubmitTool(deps) as never
  decompose = defineDecomposeTool(deps) as never
  taskMove = defineTaskMoveTool(deps) as never
  taskReport = defineTaskReportTool(deps) as never
  // REQ-2d1c74 FR-5：plan_submit 起要求提交路径真实落盘（chdir 后 stub 落进本测试临时目录）
  stubDocFile('docs/requirements/REQ-hand1/decomposition.md')
})
afterEach(() => {
  process.chdir(prevCwd)
  rmSync(dir, { recursive: true, force: true })
})

async function seed(status: RequirementStatus = 'design', sourceSessionId: string | undefined = WINDOW_A): Promise<RequirementRecord> {
  const r = {
    id: 'REQ-hand1', title: '接力测试需求', description: '验证 handoff 契约', status, blocked: false,
    category: 'feature',
    ...(sourceSessionId !== undefined ? { sourceSessionId } : {}),
    comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status: 'draft', at: 1, by: { kind: 'human' } }],
  } as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
  return r
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown, agent = WINDOW_A) =>
  tool.execute(args, { agent: { id: agent } })

const CHAIN_TASKS = [
  { key: 'proto', title: '协议层加时间线字段', phase: 'implement', side: 'backend', acceptance: 'protocol.ts 单测绿', implementation: 'protocol.ts 加时间线字段 + 单测' },
  { key: 'ui', title: '客户端渲染甘特图', phase: 'ui', side: 'frontend', depends_on: ['proto'], acceptance: '截图可见甘特图', implementation: 'view.ts 加甘特图渲染' },
  { key: 'test', title: '端到端回归测试', phase: 'test', side: 'backend', depends_on: ['ui'], acceptance: 'npx vitest run 全绿', implementation: 'tests/ 加回归用例并跑 npx vitest run' },
]

/** 窗口 A：完整走完需求分析 → 设计 → 拆分，返回任务 id 列表。
 *  2026-09-21：拆分计划在拆分阶段提交（设计阶段只写设计文档）。 */
async function windowACompletesSetup(): Promise<string[]> {
  await seed('decomposing')
  await run(planTool, { path: 'docs/requirements/REQ-hand1/decomposition.md', summary: '目标：加时间线；做法：协议→UI→测试', tasks: CHAIN_TASKS })
  await store.mutate('requirement-updated', (l) => {
    const r = l.requirements[0]
    if (r.plan !== undefined) { r.plan.approvedAt = 1000; r.plan.approvedBy = { kind: 'human' } }
    return { requirements: [r] }
  })
  const out = await run(decompose, {})
  return out.created.map((c: { id: string }) => c.id)
}

describe('接力实测：任务卡自足（新窗口零会话历史可续作）', () => {
  it('任务卡骨架含业务三要素/上游摘要/executorHint——新窗口不读历史即可开工', async () => {
    const [t1] = await windowACompletesSetup()

    // 读任务卡文件（模拟新窗口读文件）
    const cardPath = join(dir, 'docs/requirements/REQ-hand1/tasks', t1 + '.md')
    expect(existsSync(cardPath)).toBe(true)
    const card = readFileSync(cardPath, 'utf8')

    // 自足性断言：开工必需信息全部在卡上
    expect(card).toContain('协议层加时间线字段')       // 目标（标题）
    expect(card).toContain('## 解决什么问题')          // 解决什么问题（业务三要素之二）
    expect(card).toContain('protocol.ts 单测绿')       // 验收标准
    expect(card).toContain('## 上游产出摘要')          // 上游节
    expect(card).toContain('（无依赖）')               // t1 无上游
    expect(card).toContain('executorHint')             // 执行方式提示

    // 三要素节必须**都在且正文非空**（REQ-640a55 FR-2：骨架直出；空节等于没写）
    for (const h of ['## 在做什么', '## 解决什么问题', '## 得到什么结果']) {
      const i = card.indexOf(h)
      expect(i, '缺少骨架节 ' + h).toBeGreaterThanOrEqual(0)
      const rest = card.slice(i + h.length)
      const stop = rest.indexOf('\n## ')
      expect((stop >= 0 ? rest.slice(0, stop) : rest).trim().length, h + ' 的正文为空').toBeGreaterThan(0)
    }
    // 任务卡双角色注释（开工说明书 + 完工记录）
    expect(card).toContain('reqboard_task_report')
  })

  it('下游任务卡含上游产出摘要（dependsSummary 反映依赖链）', async () => {
    const [, t2, t3] = await windowACompletesSetup()

    // t2 依赖 t1，t3 依赖 t2
    const card2 = readFileSync(join(dir, 'docs/requirements/REQ-hand1/tasks', t2 + '.md'), 'utf8')
    const card3 = readFileSync(join(dir, 'docs/requirements/REQ-hand1/tasks', t3 + '.md'), 'utf8')

    // t2 的上游摘要列出 t1 标题
    expect(card2).toContain('协议层加时间线字段')
    // t3 的上游摘要列出 t2 标题
    expect(card3).toContain('客户端渲染甘特图')
  })

  it('StageDetail.decomposing 暴露 dependsOn 依赖链（handoff 数据锚点）', async () => {
    const ids = await windowACompletesSetup()
    const ledger = store.snapshot()
    const req = ledger.requirements[0]

    const detail = assembleStageDetail(req, { tasks: ledger.tasks }, 'decomposing')
    if (detail.stage !== 'decomposing') throw new Error('narrow')
    expect(detail.body.tasks).toHaveLength(3)

    // t2 依赖 t1（dependsOn 反映依赖链）
    const t2 = detail.body.tasks.find(t => t.id === ids[1])
    expect(t2?.dependsOn).toContain(ids[0])

    // t3 依赖 t2
    const t3 = detail.body.tasks.find(t => t.id === ids[2])
    expect(t3?.dependsOn).toContain(ids[1])

    // t1 无依赖
    const t1 = detail.body.tasks.find(t => t.id === ids[0])
    expect(t1?.dependsOn).toHaveLength(0)
  })

  it('PlanTask.executorHint 协议级字段存在（类型契约）', async () => {
    // 验证 PlanTask 类型含 executorHint 字段（协议级契约）
    const planTask: import('../src/shared/protocol.js').PlanTask = {
      key: 'a', title: 'A', phase: 'implement', side: 'backend', acceptance: '单测通过', implementation: '改 a.ts',
      executorHint: 'fresh-window',
    }
    expect(planTask.executorHint).toBe('fresh-window')
  })
})

describe('接力实测：task_report 追加后文件仍结构化', () => {
  it('窗口 A 汇报后，任务卡仍保持 markdown 结构（## 节标题不被破坏）', async () => {
    const [t1] = await windowACompletesSetup()

    // 窗口 A 完成任务并汇报
    await run(taskReport, {
      task_id: t1,
      summary: '完成协议层时间线字段',
      completed: ['加 StatusEvent 接口', '加 recordStatus 函数'],
      files_changed: ['src/shared/protocol.ts'],
      next_step: '窗口 B 接手客户端渲染',
    })

    const cardPath = join(dir, 'docs/requirements/REQ-hand1/tasks', t1 + '.md')
    const card = readFileSync(cardPath, 'utf8')

    // 结构保持：骨架节仍在
    expect(card).toContain('## 在做什么')
    expect(card).toContain('## 得到什么结果')
    expect(card).toContain('## 上游产出摘要')
    // 汇报节追加
    expect(card).toContain('## 汇报 1')
    expect(card).toContain('完成协议层时间线字段')
    expect(card).toContain('窗口 ' + WINDOW_A)
  })

  it('窗口 B 读任务卡 + 产物链可定位上游产出（追溯链完整）', async () => {
    const [t1, t2] = await windowACompletesSetup()

    // 窗口 A 完成 t1 并汇报
    await run(taskReport, {
      task_id: t1,
      summary: '协议层完成',
      completed: ['StatusEvent', 'recordStatus'],
      files_changed: ['src/shared/protocol.ts'],
      next_step: 'UI 渲染',
    })

    // 窗口 B 读 t2 任务卡，从上游摘要知道 t1 做了什么
    const card2 = readFileSync(join(dir, 'docs/requirements/REQ-hand1/tasks', t2 + '.md'), 'utf8')
    expect(card2).toContain('协议层加时间线字段')

    // 窗口 B 从 StageDetail 读产物链（requirement → plan → decomposition → task_detail）
    const ledger = store.snapshot()
    const req = ledger.requirements[0]
    const detail = assembleStageDetail(req, { tasks: ledger.tasks }, 'implementing')
    if (detail.stage !== 'implementing') throw new Error('narrow')

    // 产物链包含 task_detail（t1 的汇报产物）
    const taskArtifacts = detail.artifacts.filter(a => a.kind === 'task_detail')
    expect(taskArtifacts.length).toBeGreaterThanOrEqual(1)
    expect(taskArtifacts[0].path).toContain(t1)
  })

  it('窗口 B 可推进任务（task_move 绑定新 sessionId）+ 汇报', async () => {
    const [, t2] = await windowACompletesSetup()

    // 需求先进入 implementing（模拟人确认拆分清单）
    await store.mutate('human-confirm', (l) => {
      const r = l.requirements.find(x => x.id === 'REQ-hand1')!
      r.status = 'implementing'
      return { requirements: [r] }
    })

    // 模拟接力：需求重新绑定到窗口 B（新窗口接手）
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements.find(x => x.id === 'REQ-hand1')!
      r.sourceSessionId = WINDOW_B
      return { requirements: [r] }
    })

    // 窗口 B 开工 t2
    const started = await run(taskMove, { task_id: t2, to: 'in_progress', reason: '窗口 B 接手' }, WINDOW_B)
    expect(started.success).toBe(true)

    // 验证 claimedBy = 窗口 B
    const task = store.snapshot().tasks.find(t => t.id === t2)!
    expect(task.claimedBy).toBe(WINDOW_B)

    // 窗口 B 汇报
    const report = await run(taskReport, {
      task_id: t2,
      summary: '客户端甘特图渲染完成',
      completed: ['甘特图组件', '状态着色'],
      files_changed: ['src/client/gantt.ts'],
      next_step: '端到端测试',
    }, WINDOW_B)
    expect(report.success).toBe(true)
    expect(report.report_index).toBe(1) // t2 的第一段汇报

    // 文件包含窗口 B 的汇报
    const card = readFileSync(join(dir, 'docs/requirements/REQ-hand1/tasks', t2 + '.md'), 'utf8')
    expect(card).toContain('窗口 ' + WINDOW_B)
    expect(card).toContain('客户端甘特图渲染完成')
  })

  it('多次汇报后文件仍结构化（段落递增，骨架不丢）', async () => {
    const [t1] = await windowACompletesSetup()

    // 第一次汇报
    await run(taskReport, { task_id: t1, summary: '第一次进度', completed: ['草稿'] })
    // 第二次汇报
    await run(taskReport, { task_id: t1, summary: '第二次进度', completed: ['修订'] })

    const card = readFileSync(join(dir, 'docs/requirements/REQ-hand1/tasks', t1 + '.md'), 'utf8')
    // 骨架节仍在
    expect(card).toContain('## 在做什么')
    expect(card).toContain('## 得到什么结果')
    // 两段汇报
    expect(card).toContain('## 汇报 1')
    expect(card).toContain('## 汇报 2')
    expect(card).toContain('第一次进度')
    expect(card).toContain('第二次进度')
  })
})

describe('接力实测：handoff 契约——新窗口不读历史对话即可续作', () => {
  it('完整链路：A 拆 → A 做 t1 → B 读卡做 t2 → B 汇报 → 产物链完整', async () => {
    const [t1, t2, t3] = await windowACompletesSetup()

    // ── 窗口 A：做 t1 ──
    await run(taskReport, {
      task_id: t1, summary: '协议层完成',
      completed: ['StatusEvent'], files_changed: ['src/protocol.ts'], next_step: 'UI',
    })

    // ── 窗口 B：零会话历史，仅凭任务卡 + StageDetail 接手 t2 ──
    // B 读 StageDetail.implementing 拿到产物链和任务列表
    const ledgerBefore = store.snapshot()
    const reqBefore = ledgerBefore.requirements[0]
    const detail = assembleStageDetail(reqBefore, { tasks: ledgerBefore.tasks }, 'implementing')
    if (detail.stage !== 'implementing') throw new Error('narrow')

    // B 从 detail 找到 t2（cardDoc 路径由任务 id 推导：tasks/<task_id>.md）
    const t2Ref = detail.body.tasks.find(t => t.id === t2)
    expect(t2Ref).toBeDefined()
    const cardDocPath = 'docs/requirements/REQ-hand1/tasks/' + t2 + '.md'

    // B 读任务卡文件（从磁盘读，不读会话历史）
    const cardAbs = join(dir, cardDocPath)
    expect(existsSync(cardAbs)).toBe(true)
    const cardContent = readFileSync(cardAbs, 'utf8')
    // B 从卡上读到：目标、验收标准、上游产出摘要
    expect(cardContent).toContain('客户端渲染甘特图')
    expect(cardContent).toContain('截图可见甘特图')
    expect(cardContent).toContain('协议层加时间线字段')

    // B 开工 + 汇报
    await store.mutate('human-confirm', (l) => {
      const r = l.requirements.find(x => x.id === 'REQ-hand1')!
      r.status = 'implementing'
      return { requirements: [r] }
    })
    // 模拟接力：需求重新绑定到窗口 B
    await store.mutate('requirement-updated', (l) => {
      const r = l.requirements.find(x => x.id === 'REQ-hand1')!
      r.sourceSessionId = WINDOW_B
      return { requirements: [r] }
    })
    await run(taskMove, { task_id: t2, to: 'in_progress', reason: 'B 接手' }, WINDOW_B)
    await run(taskReport, {
      task_id: t2, summary: '甘特图完成',
      completed: ['组件'], files_changed: ['src/gantt.ts'], next_step: '测试',
    }, WINDOW_B)

    // ── 验证产物链完整：从 implementing StageDetail 可追溯到全部产物 ──
    const ledgerAfter = store.snapshot()
    const reqAfter = ledgerAfter.requirements[0]
    const finalDetail = assembleStageDetail(reqAfter, { tasks: ledgerAfter.tasks }, 'implementing')
    if (finalDetail.stage !== 'implementing') throw new Error('narrow')

    // implementing 阶段的产物：task_detail（t1/t2 的汇报产物）
    const kinds = finalDetail.artifacts.map(a => a.kind)
    expect(kinds).toContain('task_detail')
    // 完整产物链从需求记录追溯：decomposition（拆分计划，2026-09-21 起替代旧 plan 产物）→ task_detail
    const allArtifacts = reqAfter.artifacts ?? []
    const allKinds = allArtifacts.map(a => a.kind)
    expect(allKinds).toContain('decomposition')
    expect(allKinds).toContain('task_detail')

    // byWindow 显示上下文分担：窗口 A 和窗口 B 都可见
    expect(Object.keys(finalDetail.body.byWindow).length).toBeGreaterThanOrEqual(1)

    // t3 未开工 → unassigned
    expect(finalDetail.body.byWindow['unassigned']).toContain(t3)
  })
})
