/**
 * 真拆分与任务推进的**边界**测试（正常路径见 plan-mode.test.ts）。
 *
 * 计划模式下 decompose 只落库"已批准的计划"，所以本文件的重点是闸门与越权边界：
 *   - 立项态不能提交计划（方案还没谈）；
 *   - decompose 只能落库本窗口需求；
 *   - tasks 与批准计划不一致 → 拒绝；
 *   - task_move：跨窗口越权、任务不存在、取消任务（人工闸门）一律拒绝；
 *   - 开工自动开执行段、离开 in_progress 自动结算。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { definePlanSubmitTool, defineDecomposeTool, defineTaskMoveTool, defineVerifySubmitTool, defineTaskReportTool, stubDocFile } from './helpers/tool-deps.js'
import { recordToolTrace, type ToolTraceEntry } from '../src/adapters/SessionProbeAdapter.js'
import type { RequirementRecord, RequirementStatus } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let planTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let decompose: { execute: (a: unknown, e: unknown) => Promise<any> }
let taskMove: { execute: (a: unknown, e: unknown) => Promise<any> }
let verifySubmit: { execute: (a: unknown, e: unknown) => Promise<any> }
let reportTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let trace: Map<string, ToolTraceEntry[]>

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-decompose-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  trace = new Map()
  const deps = { store, now: () => Date.now(), toolTrace: trace, doneThrottleMs: 60_000 }
  depsRef = deps
  planTool = definePlanSubmitTool(deps) as never
  decompose = defineDecomposeTool(deps) as never
  taskMove = defineTaskMoveTool(deps) as never
  verifySubmit = defineVerifySubmitTool(deps) as never
  reportTool = defineTaskReportTool(deps) as never
  // REQ-2d1c74 FR-5：plan_submit 起要求提交路径真实落盘——本文件的占位路径统一在文档根落桩
  for (const p of ['p.md', 'docs/requirements/REQ-abc123/plan.md', 'docs/requirements/REQ-abc123/decomposition.md']) stubDocFile(p)
})

let depsRef: { doneThrottleMs?: number }

/** done 凭证门（t06）时代的诚实关账：留干活痕迹 + 汇报，再转 done。返回 done 转移的返回体。 */
async function honestClose(taskId: string) {
  recordToolTrace(trace, W, 'edit', Date.now())
  await run(reportTool, { task_id: taskId, summary: '完成实施', completed: ['改动已落地并自测'], files_changed: [] })
  return run(taskMove, { task_id: taskId, to: 'done' })
}
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seed(status: RequirementStatus = 'decomposing', sourceSessionId: string | undefined = W): Promise<RequirementRecord> {
  const r = {
    id: 'REQ-abc123', title: '看板需求', description: '', status, blocked: false,
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
  { key: 'a', title: '协议层加时间线', phase: 'implement', side: 'backend', acceptance: 'npx vitest run tests/reqboard.test.ts 全绿', implementation: 'protocol.ts 加字段 + 单测验证' },
  { key: 'b', title: '客户端渲染甘特图', phase: 'ui', side: 'frontend', depends_on: ['a'], acceptance: 'npx vitest run tests/client-view.test.ts 全绿', implementation: 'view.ts 加 buildGantt() 渲染' },
]

/** 提交计划并**直接以人身份批准**（本文件不测裁决路径，那在 plan-mode.test.ts）。 */
async function planAndApprove(tasks: unknown = TWO_TASKS): Promise<void> {
  const out = await run(planTool, { path: 'docs/requirements/REQ-abc123/plan.md', summary: '摘要', tasks })
  expect(out.plan_status).toBe('pending_approval')
  await store.mutate('requirement-updated', (l) => {
    const r = l.requirements[0]
    if (r.plan !== undefined) { r.plan.approvedAt = 1000; r.plan.approvedBy = { kind: 'human' } }
    return { requirements: [r] }
  })
}

describe('reqboard_decompose 边界', () => {
  it('立项态不能提交计划（方案还没谈），decompose 也被拒', async () => {
    await seed('draft')
    await expect(run(planTool, { path: 'p.md', summary: 's', tasks: TWO_TASKS })).rejects.toThrow(/REQBOARD_BAD_STATUS/)
    await expect(run(decompose, {})).rejects.toThrow(/REQBOARD_BAD_STATUS/) // 先是状态闸，再是计划闸
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('越权：不能拆别的窗口的需求', async () => {
    await seed('decomposing')
    await planAndApprove()
    await expect(run(decompose, {}, 'session-other')).rejects.toThrow(/REQBOARD_NO_BOUND_REQ/)
    await expect(run(decompose, { requirement_id: 'REQ-ffffff' })).rejects.toThrow(/REQBOARD_NOT_BOUND_TO_WINDOW/)
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('传与批准计划不一致的 tasks → 拒绝且不写库', async () => {
    await seed('decomposing')
    await planAndApprove()
    await expect(run(decompose, { tasks: [{ key: 'x', title: '计划外' }] })).rejects.toThrow(/REQBOARD_PLAN_MISMATCH/)
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('幂等守卫（REQ-2e9473 t01）：重复拆分被拒且任务数不变（事故 B 故障注入）', async () => {
    await seed('decomposing')
    await planAndApprove()
    const first = await run(decompose, {})
    expect(first.created).toHaveLength(2)
    // 第一次拆分后需求已被 rollup 推进到 decomposing → 第二次拆分撞状态守卫
    await expect(run(decompose, {})).rejects.toThrow(/REQBOARD_ALREADY_DECOMPOSED/)
    // 台账任务数不变：不产生幽灵任务
    expect(store.snapshot().tasks).toHaveLength(2)
  })

  it('幂等守卫：状态停在 design 但已有未取消任务时，拒绝并返回已有清单', async () => {
    await seed('decomposing')
    await planAndApprove()
    await run(decompose, {})
    // 模拟状态异常：任务已落库但需求状态被外部改回 design（绕过状态守卫，考验任务清单防线）
    await store.mutate('manual-rollback', (l) => {
      const r = l.requirements[0]
      r.status = 'design'
      return { requirements: [r] }
    })
    await expect(run(decompose, {})).rejects.toThrow(/REQBOARD_ALREADY_DECOMPOSED/)
    await expect(run(decompose, {})).rejects.toThrow(/禁止重复拆分/)
    expect(store.snapshot().tasks).toHaveLength(2)
  })

  it('回归（2026-09-17）：批准计划后自动进入 decomposing 且尚无任务 —— 必须允许拆分', async () => {
    // 事故现场：reqboard_ask_confirm(target=plan) 批准后自动 design → decomposing，
    // 紧接着调 decompose 被"状态=decomposing 即视为已拆过"的守卫拒死（REQBOARD_ALREADY_DECOMPOSED），
    // 而台账里一个任务都没有 —— 审批流水线自锁。
    await seed('decomposing')
    await store.mutate('seed-plan', (l) => {
      const r = l.requirements[0]
      r.plan = { path: 'p.md', summary: 's', tasks: [], submittedAt: 1, approvedAt: 1000, approvedBy: { kind: 'human' } } as never
      return { requirements: [r] }
    })
    const out = await run(decompose, {
      tasks: [
        { key: 't1', title: '协议层加时间线', phase: 'implement', side: 'backend', acceptance: 'npx vitest run tests/reqboard.test.ts 全绿', implementation: 'src/shared/protocol.ts 加字段并由 tests/reqboard.test.ts 验证' },
        { key: 't2', title: '客户端渲染甘特图', phase: 'ui', side: 'frontend', depends_on: ['t1'], acceptance: 'tests/client-view.test.ts 全绿', implementation: 'src/client/view.ts 加 buildGantt() 并由 tests/client-view.test.ts 断言' },
      ],
    })
    expect(out.created).toHaveLength(2)
    expect(store.snapshot().tasks).toHaveLength(2)
    // 拆完后重复拆分仍被拒（防线②）：无幽灵任务
    await expect(run(decompose, { tasks: [{ key: 't1', title: 'x' }] })).rejects.toThrow(/REQBOARD_ALREADY_DECOMPOSED/)
    expect(store.snapshot().tasks).toHaveLength(2)
  })

  it('幂等守卫：implementing/accepting 状态一律拒绝重复拆分', async () => {
    for (const st of ['implementing', 'accepting'] as const) {
      await seed(st)
      await store.mutate('seed-plan', (l) => {
        const r = l.requirements[l.requirements.length - 1]
        r.plan = { path: 'p.md', summary: 's', tasks: [], submittedAt: 1, approvedAt: 1000, approvedBy: { kind: 'human' } } as never
        return { requirements: [r] }
      })
      await expect(run(decompose, {})).rejects.toThrow(/REQBOARD_ALREADY_DECOMPOSED/)
      // 清理本条 seed，避免互相影响
      await store.mutate('cleanup', (l) => { l.requirements.length = 0; return { requirements: [] } })
    }
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('按计划落库：key 映射成真实 id、依赖成链、任务验收标准来自计划', async () => {
    await seed('decomposing')
    await planAndApprove()
    const out = await run(decompose, {})
    expect(out.created).toHaveLength(2)
    expect(out.created[0].id).toMatch(/^t-[0-9a-f]{6}$/)
    expect(out.created[1].depends_on).toEqual([out.created[0].id])
    expect(out.requirement_status).toBe('decomposing')
    const ledger = store.snapshot()
    // 迁移（REQ-d3e61a T-9）：占位验收标准换成**可照着验**的真实标准——本断言验的是
    // "计划任务表正确落库"（语义不变），只是值随门禁要求一起升级。
    expect(ledger.tasks.map(t => t.acceptance)).toEqual(['npx vitest run tests/reqboard.test.ts 全绿', 'npx vitest run tests/client-view.test.ts 全绿'])
    expect(ledger.tasks[0].statusHistory?.[0]?.by.kind).toBe('agent')
    // cardDoc 随落库写死（REQ-260923134706-e72f 断链修复）：任务卡文档路径 = docs/requirements/<REQ>/tasks/<id>.md
    for (const t of ledger.tasks) {
      expect(t.cardDoc).toBe('docs/requirements/' + t.requirementId + '/tasks/' + t.id + '.md')
    }
    // 2026-09-21：拆分计划在拆分阶段提交，decompose 不再承担 design>decomposing 推进
    expect(ledger.requirements[0].status).toBe('decomposing')
    expect(ledger.requirements[0].statusHistory?.map(e => e.status)).toEqual(['draft'])
  })
})

describe('plan_submit 三重校验（REQ-2e9473 t03）', () => {
  const GOOD = [
    { key: 'a', title: '协议层改', acceptance: 'protocol.ts 单测绿', implementation: 'protocol.ts 加字段' },
    { key: 'b', title: '客户端改', depends_on: ['a'], acceptance: '截图可见', implementation: 'view.ts 加渲染' },
  ]

  it('缺 implementation 的任务表被拒', async () => {
    await seed('decomposing')
    await expect(run(planTool, {
      path: 'p.md', summary: 's',
      tasks: [{ key: 'a', title: 'x', acceptance: '单测绿' }],
    })).rejects.toThrow(/缺实施方案/)
  })

  it('验收标准空话（功能正常）被拒', async () => {
    await seed('decomposing')
    await expect(run(planTool, {
      path: 'p.md', summary: 's',
      tasks: [{ key: 'a', title: 'x', acceptance: '功能正常', implementation: '改 x.ts' }],
    })).rejects.toThrow(/空话/)
  })

  it('验收标准缺可验证锚点被拒', async () => {
    await seed('decomposing')
    await expect(run(planTool, {
      path: 'p.md', summary: 's',
      tasks: [{ key: 'a', title: 'x', acceptance: '做完就行了', implementation: '改 x.ts' }],
    })).rejects.toThrow(/锚点/)
  })

  it('前向引用被拒（事故 G：依赖后定义的 key）', async () => {
    await seed('decomposing')
    await expect(run(planTool, {
      path: 'p.md', summary: 's',
      tasks: [
        { key: 'a', title: 'x', depends_on: ['b'], acceptance: '单测绿', implementation: '改 x.ts' },
        { key: 'b', title: 'y', acceptance: '截图可见', implementation: '改 y.ts' },
      ],
    })).rejects.toThrow(/前向引用/)
  })

  it('依赖不存在的 key 被拒（原有语义保持）', async () => {
    await seed('decomposing')
    await expect(run(planTool, {
      path: 'p.md', summary: 's',
      tasks: [{ key: 'a', title: 'x', depends_on: ['ghost'], acceptance: '单测绿', implementation: '改 x.ts' }],
    })).rejects.toThrow(/不存在的 key/)
  })

  it('合法任务表通过且 implementation 落库', async () => {
    await seed('decomposing')
    const out = await run(planTool, { path: 'p.md', summary: 's', tasks: GOOD })
    expect(out.plan_status).toBe('pending_approval')
    const plan = store.snapshot().requirements[0].plan!
    expect(plan.tasks.map(t => t.implementation)).toEqual(['protocol.ts 加字段', 'view.ts 加渲染'])
  })
})

describe('实施卡透传与开工送达（REQ-2e9473 t04）', () => {
  it('decompose 把 implementation 透传进 TaskRecord 与任务卡文件', async () => {
    await seed('decomposing')
    await planAndApprove()
    const out = await run(decompose, {})
    const ledger = store.snapshot()
    expect(ledger.tasks.map(t => t.implementation)).toEqual(['protocol.ts 加字段 + 单测验证', 'view.ts 加 buildGantt() 渲染'])
    expect(out.thin_cards).toBeUndefined()
  })

  it('历史批准的薄卡计划：decompose 不硬拦（人批过）但返回 thin_cards 警告', async () => {
    await seed('decomposing')
    // 模拟规则生效前批准的存量计划：无 implementation
    await store.mutate('legacy-plan', (l) => {
      const r = l.requirements[0]
      r.plan = {
        path: 'p.md', summary: 's', submittedAt: 1, submittedBy: { kind: 'agent' },
        approvedAt: 2, approvedBy: { kind: 'human' },
        tasks: [{ key: 'a', title: '旧任务', acceptance: '单测绿' }],
      } as never
      return { requirements: [r] }
    })
    const out = await run(decompose, {})
    expect(out.success).toBe(true)
    expect(out.thin_cards).toHaveLength(1)
    expect(out.warning).toMatch(/薄卡/)
  })

  it('task_move→in_progress 返回任务卡全文（开工说明书送达）', async () => {
    await seed('decomposing')
    await planAndApprove()
    const out = await run(decompose, {})
    await store.mutate('human-confirm', (l) => {
      const r = l.requirements[0]
      r.status = 'implementing'
      return { requirements: [r] }
    })
    const start = await run(taskMove, { task_id: out.created[0].id, to: 'in_progress' })
    expect(start.task_card).toBeDefined()
    expect(start.task_card.implementation).toBe('protocol.ts 加字段 + 单测验证')
    expect(start.task_card.acceptance).toBe('npx vitest run tests/reqboard.test.ts 全绿')
    expect(start.task_card.doc_path).toMatch(/tasks\/t-/)
    // 非开工转移不带任务卡
    const next = await run(taskMove, { task_id: out.created[0].id, to: 'testing' })
    expect(next.task_card).toBeUndefined()
  })
})

describe('rollup 阻塞 blockers 显式化（REQ-2e9473 t02）', () => {
  /** 落库 2 任务并把需求推进到 implementing（模拟拆分确认门已过）。 */
  async function seedImplementingTwoTasks() {
    await seed('decomposing')
    await planAndApprove()
    const out = await run(decompose, {})
    await store.mutate('human-confirm', (l) => {
      const r = l.requirements[0]
      r.status = 'implementing'
      return { requirements: [r] }
    })
    return out.created.map((c: { id: string }) => c.id)
  }

  it('task_move：任务 a 完成但 b 仍 todo（幽灵场景）→ 返回 blockers + warning', async () => {
    const [a] = await seedImplementingTwoTasks()
    for (const to of ['in_progress', 'testing', 'in_review']) await run(taskMove, { task_id: a, to })
    const out = await honestClose(a)
    expect(out.blockers).toHaveLength(1)
    expect(out.blockers[0].status).toBe('todo')
    expect(out.warning).toMatch(/未进验收/)
    expect(out.requirement_status).toBe('implementing')
  })

  it('verify_submit：有未完成任务时返回显式 blockers，status 停 implementing 且 note 改写', async () => {
    const [a] = await seedImplementingTwoTasks()
    for (const to of ['in_progress', 'testing', 'in_review']) await run(taskMove, { task_id: a, to })
    await honestClose(a)
    const out = await run(verifySubmit, { summary: '交付完成', evidence: ['npx vitest run：393 通过'] })
    expect(out.blockers).toHaveLength(1)
    expect(out.blockers[0].status).toBe('todo')
    expect(out.warning).toMatch(/rollup 阻塞/)
    expect(out.status).toBe('implementing')
    expect(out.note).toMatch(/停在 implementing/)
  })

  it('全部任务 done → 无 blockers，R2 正常推进到 accepting', async () => {
    depsRef.doneThrottleMs = 0 // 本用例验 rollup 不验节流（节流有专属故障注入用例）
    const [a, b] = await seedImplementingTwoTasks()
    for (const to of ['in_progress', 'testing', 'in_review']) await run(taskMove, { task_id: a, to })
    await honestClose(a)
    for (const to of ['in_progress', 'testing', 'in_review']) await run(taskMove, { task_id: b, to })
    await honestClose(b)
    const out = await run(verifySubmit, { summary: '交付完成', evidence: ['npx vitest run：全绿'] })
    expect(out.blockers).toBeUndefined()
    expect(out.warning).toBeUndefined()
    expect(out.status).toBe('accepting')
    expect(out.note).toMatch(/逐项审核/)
  })
})

describe('done 凭证门（REQ-2e9473 t06/W2，事故 C/D 故障注入）', () => {
  /** 开工到 in_review 的任务（未汇报、无痕迹）。 */
  async function taskInReview() {
    await seed('decomposing')
    await planAndApprove()
    const out = await run(decompose, {})
    await store.mutate('human-confirm', (l) => {
      const r = l.requirements[0]
      r.status = 'implementing'
      return { requirements: [r] }
    })
    const id = out.created[0].id as string
    for (const to of ['in_progress', 'testing', 'in_review']) await run(taskMove, { task_id: id, to })
    return id
  }

  it('无汇报 → REQBOARD_NO_REPORT（25ms 速通拦截）', async () => {
    const id = await taskInReview()
    await expect(run(taskMove, { task_id: id, to: 'done' })).rejects.toThrow(/REQBOARD_NO_REPORT/)
    expect(store.snapshot().tasks[0].status).toBe('in_review')
  })

  it('汇报证据为空（completed/files_changed 都空）→ REQBOARD_NO_REPORT', async () => {
    const id = await taskInReview()
    await run(reportTool, { task_id: id, summary: '做完了' })
    await expect(run(taskMove, { task_id: id, to: 'done' })).rejects.toThrow(/REQBOARD_NO_REPORT/)
  })

  it('有汇报但开工以来无工具痕迹且无文件证据 → REQBOARD_NO_EVIDENCE', async () => {
    const id = await taskInReview()
    await run(reportTool, { task_id: id, summary: '完成', completed: ['改了代码'], files_changed: ['no/such/file.ts'] })
    await expect(run(taskMove, { task_id: id, to: 'done' })).rejects.toThrow(/REQBOARD_NO_EVIDENCE/)
  })

  it('60s 内连续关闭两个任务 → 第二个被 REQBOARD_BULK_CLOSE 节流（事故 C 复现）', async () => {
    await seed('decomposing')
    await planAndApprove()
    const out = await run(decompose, {})
    await store.mutate('human-confirm', (l) => {
      const r = l.requirements[0]
      r.status = 'implementing'
      return { requirements: [r] }
    })
    const [a, b] = out.created.map((c: { id: string }) => c.id)
    for (const to of ['in_progress', 'testing', 'in_review']) await run(taskMove, { task_id: a, to })
    await honestClose(a)
    for (const to of ['in_progress', 'testing', 'in_review']) await run(taskMove, { task_id: b, to })
    recordToolTrace(trace, W, 'edit', Date.now())
    await run(reportTool, { task_id: b, summary: '完成', completed: ['改动落地'] })
    await expect(run(taskMove, { task_id: b, to: 'done' })).rejects.toThrow(/REQBOARD_BULK_CLOSE/)
  })

  it('页面插件任务未构建 → REQBOARD_STALE_BUILD（事故 D）', async () => {
    const id = await taskInReview()
    recordToolTrace(trace, W, 'edit', Date.now())
    await run(reportTool, {
      task_id: id, summary: '改了页面插件源码', completed: ['view.ts 已改'],
      files_changed: ['packages/pages/no-such-pkg/src/view.ts'],
    })
    await expect(run(taskMove, { task_id: id, to: 'done' })).rejects.toThrow(/REQBOARD_STALE_BUILD/)
  })

  it('诚实路径全通：痕迹+汇报+非批量 → done 放行', async () => {
    const id = await taskInReview()
    const out = await honestClose(id)
    expect(out.to).toBe('done')
  })
})

describe('reqboard_task_move 边界', () => {
  it('越权/不存在/人工闸门一律拒绝', async () => {
    await seed('decomposing')
    await planAndApprove()
    const out = await run(decompose, {})
    const a = out.created[0].id
    await expect(run(taskMove, { task_id: a, to: 'canceled' })).rejects.toThrow(/REQBOARD_HUMAN_GATE/)
    await expect(run(taskMove, { task_id: 't-ffffff', to: 'in_progress' })).rejects.toThrow(/REQBOARD_TASK_NOT_FOUND/)
    await expect(run(taskMove, { task_id: a, to: 'in_progress' }, 'session-other')).rejects.toThrow(/REQBOARD_NOT_BOUND_TO_WINDOW/)
    await expect(run(taskMove, { task_id: a, to: 'done' })).rejects.toThrow(/invalid_transition/)
  })

  it('开工自动开执行段，离开 in_progress 自动结算；全部完成后需求进验收', async () => {
    await seed('decomposing')
    await planAndApprove()
    const out = await run(decompose, {})
    const [a, b] = out.created.map((c: { id: string }) => c.id)

    const start = await run(taskMove, { task_id: a, to: 'in_progress', reason: '开工' })
    // 2026-09-14 五门裁定：任务开工不再自动 decomposing>implementing（拆分清单须人确认），
    // 需求停在拆分态；模拟人确认拆分清单后推进到 implementing，再验证 R2 rollup。
    expect(start.requirement_status).toBe('decomposing')
    let t = store.snapshot().tasks.find(x => x.id === a)!
    expect(t.executions).toHaveLength(1)
    expect(t.executions[0].outcome).toBe('running')
    expect(t.claimedBy).toBe(W)

    depsRef.doneThrottleMs = 0 // 本用例验执行段结算不验节流
    for (const to of ['testing', 'in_review']) await run(taskMove, { task_id: a, to })
    await honestClose(a)
    t = store.snapshot().tasks.find(x => x.id === a)!
    expect(t.executions[0].endedAt).toBeDefined()
    expect(t.executions[0].outcome).toBe('succeeded')
    expect(t.statusHistory?.map(e => e.status)).toEqual(['todo', 'in_progress', 'testing', 'in_review', 'done'])
    expect(store.snapshot().requirements[0].status).toBe('decomposing')

    // 模拟人确认拆分清单（human gate 通过），需求进入实施态
    await store.mutate('human-confirm', (l) => {
      const r = l.requirements.find(x => x.id === 'REQ-abc123')!
      r.status = 'implementing'
      return { requirements: [r] }
    })

    for (const to of ['in_progress', 'testing', 'in_review']) await run(taskMove, { task_id: b, to })
    await honestClose(b)
    expect(store.snapshot().requirements[0].status).toBe('accepting')
  })
})
