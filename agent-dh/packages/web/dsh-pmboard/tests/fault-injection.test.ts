/**
 * 故障注入回归（REQ-2e9473 t15）：REQ-6f39b5 复盘暴露的事故逐条复现，验证硬门拦住。
 *
 * A 弹框确认后节点不推进     → reqboard_ask_confirm 原子完成（落章+推进）
 * B 重复拆分产生幽灵任务     → decompose 幂等守卫生效（任务数不变）
 * C 25ms 速通假完成          → done 凭证门拒绝（无汇报 / 批量关闭）
 * D 改了源码没构建           → 页面插件任务 done 被 STALE_BUILD 拒
 * E 过程文件不进文档         → 目录落盘即产物（autoDiscovered）
 * F 拆分卡是薄卡（无实施卡）  → plan_submit/decompose 拒绝
 * G 计划任务表前向引用        → plan_submit 提交时打回
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import {
  definePlanSubmitTool, defineDecomposeTool, defineTaskMoveTool, defineTaskReportTool,
  defineAskConfirmTool, stubDocFile,
} from './helpers/tool-deps.js'
import { syncReqArtifacts, reqDirRel } from '../src/adapters/ArtifactSync.js'
import { recordToolTrace, type ToolTraceEntry } from '../src/adapters/SessionProbeAdapter.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-fi-001'
let root: string
let store: ReqboardStore
let planTool: any, decompose: any, taskMove: any, report: any
let trace: Map<string, ToolTraceEntry[]>

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'pmboard-faultinj-'))
  store = new ReqboardStore({ file: join(root, 'dsh-reqboard.json') })
  trace = new Map()
  const deps = { store, now: () => Date.now(), toolTrace: trace, doneThrottleMs: 60_000, workspaceRoot: root } as never
  planTool = definePlanSubmitTool(deps)
  decompose = defineDecomposeTool(deps)
  taskMove = defineTaskMoveTool(deps)
  report = defineTaskReportTool(deps)
  // REQ-2d1c74 FR-5：plan_submit 起要求提交路径真实落盘
  stubDocFile('p.md', root)
})
afterEach(() => { rmSync(root, { recursive: true, force: true }) })

const REQ = 'REQ-fi0001'
const GOOD_TASKS = [
  { key: 'a', title: '任务A', acceptance: 'protocol.ts 单测绿', implementation: 'protocol.ts 加字段' },
  { key: 'b', title: '任务B', depends_on: ['a'], acceptance: '截图可见', implementation: 'view.ts 加渲染' },
]
const run = (tool: any, args: unknown, agent = W) => tool.execute(args, { agent: { id: agent } })

async function seed(status = 'design'): Promise<void> {
  const r = {
    id: REQ, title: '故障注入', description: '', status, category: 'feature', blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}
async function approvePlan(): Promise<void> {
  await store.mutate('approve', (l) => {
    const r = l.requirements[0]
    r.plan!.approvedAt = 1
    r.plan!.approvedBy = { kind: 'human' }
    return { requirements: [r] }
  })
}

describe('A 弹框确认后节点不推进 → ask_confirm 原子完成', () => {
  it('肯定答复 → 落章 + 推进一次调用完成', async () => {
    await seed('brainstorming')
    await store.mutate('artifact', (l) => {
      l.requirements[0].artifacts = [{
        stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/' + REQ + '/requirement.md',
        registeredAt: 1, registeredBy: { kind: 'agent' },
      } as never]
      return { requirements: [l.requirements[0]] }
    })
    const deps = {
      store, now: () => Date.now(),
      userQuestions: () => ({ ask: async () => ({ answers: [{ id: 'confirm', selected: ['确认，推进到下一阶段 (Recommended)'] }] }) }),
    } as never
    const tool = defineAskConfirmTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
    const out = await tool.execute(
      { target: 'artifact', kind: 'requirement', question: '是否进入设计？' },
      { agent: { id: W } },
    )
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(true)
    expect(store.snapshot().requirements[0].status).toBe('design')
    expect(store.snapshot().requirements[0].artifacts![0].confirmedAt).toBeDefined()
  })
})

describe('B 重复拆分 → 幂等守卫（任务数不变）', () => {
  it('二次 decompose 被拒且任务数保持 2', async () => {
    await seed('decomposing')
    await run(planTool, { path: 'p.md', summary: 's', tasks: GOOD_TASKS })
    await approvePlan()
    await run(decompose, {})
    await expect(run(decompose, {})).rejects.toThrow(/REQBOARD_ALREADY_DECOMPOSED/)
    expect(store.snapshot().tasks).toHaveLength(2)
  })
})

describe('C 25ms 速通假完成 → done 凭证门', () => {
  it('无汇报直接 done → REQBOARD_NO_REPORT', async () => {
    await seed('implementing')
    await store.mutate('task', (l) => {
      l.tasks.push({
        id: 't-fi0001', requirementId: REQ, title: '任务A', description: '', phase: 'implement', side: 'backend',
        dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: '单测绿', context: '',
        status: 'in_progress', blocked: false, executions: [], comments: [], version: 1,
        createdAt: 1, updatedAt: 1, createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
        claimedBy: W, claimedAt: 1,
      } as never)
      return { tasks: [l.tasks[l.tasks.length - 1]] }
    })
    await run(taskMove, { task_id: 't-fi0001', to: 'testing' })
    await run(taskMove, { task_id: 't-fi0001', to: 'in_review' })
    await expect(run(taskMove, { task_id: 't-fi0001', to: 'done' })).rejects.toThrow(/REQBOARD_NO_REPORT/)
  })
})

describe('D 改了源码没构建 → STALE_BUILD', () => {
  it('页面插件文件已改但未构建 → done 被拒', async () => {
    await seed('implementing')
    await store.mutate('task', (l) => {
      l.tasks.push({
        id: 't-fi0002', requirementId: REQ, title: '页面改', description: '', phase: 'implement', side: 'frontend',
        dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: '截图可见', implementation: 'view.ts',
        context: '', status: 'in_progress', blocked: false, executions: [], comments: [], version: 1,
        createdAt: 1, updatedAt: 1, createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
        claimedBy: W, claimedAt: 1,
      } as never)
      return { tasks: [l.tasks[l.tasks.length - 1]] }
    })
    recordToolTrace(trace, W, 'edit', Date.now())
    await run(report, {
      task_id: 't-fi0002', summary: '改了页面插件', completed: ['view.ts 已改'],
      files_changed: ['packages/pages/no-such-pkg/src/view.ts'],
    })
    for (const to of ['testing', 'in_review']) await run(taskMove, { task_id: 't-fi0002', to })
    await expect(run(taskMove, { task_id: 't-fi0002', to: 'done' })).rejects.toThrow(/REQBOARD_STALE_BUILD/)
  })
})

describe('E 过程文件不进文档 → 目录落盘即产物', () => {
  it('写入需求目录的 html 自动登记（autoDiscovered）', async () => {
    await seed('brainstorming')
    const abs = join(root, reqDirRel(REQ), 'prototype.html')
    mkdirSync(join(abs, '..'), { recursive: true })
    writeFileSync(abs, '<html></html>')
    const added = await syncReqArtifacts(store, REQ, root)
    expect(added).toBeGreaterThanOrEqual(1)
    const arts = store.snapshot().requirements[0].artifacts!
    const html = arts.find(a => a.path.includes('prototype.html'))!
    expect(html).toBeDefined()
    expect(html.autoDiscovered).toBe(true)
    expect(html.kind).toBe('notes')
    rmSync(join(root, reqDirRel(REQ)), { recursive: true, force: true })
  })
})

describe('F 薄卡（无实施卡）→ 拒落', () => {
  it('plan_submit 薄卡 → 缺实施方案', async () => {
    await seed('decomposing')
    await expect(run(planTool, {
      path: 'p.md', summary: 's',
      tasks: [{ key: 'a', title: 'x', acceptance: '单测绿' }],
    })).rejects.toThrow(/缺实施方案/)
  })
})

describe('G 计划前向引用 → 提交时打回', () => {
  it('依赖后定义 key → 前向引用', async () => {
    await seed('decomposing')
    await expect(run(planTool, {
      path: 'p.md', summary: 's',
      tasks: [
        { key: 'a', title: 'x', depends_on: ['b'], acceptance: '单测绿', implementation: '改 a.ts' },
        { key: 'b', title: 'y', acceptance: '截图可见', implementation: '改 b.ts' },
      ],
    })).rejects.toThrow(/前向引用/)
  })
})
