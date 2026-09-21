/**
 * reqboard_task_report 单测（REQ-31e11f t3）。
 *
 * 覆盖：
 *   - 汇报追加落盘 + 产物登记（文件不存在 → 写骨架头；存在 → 追加段落）；
 *   - 越权拒绝（任务不存在 / 任务不属于本窗口绑定需求）；
 *   - 幂等（同 task_id 重复汇报 → 追加新段落但不重复登记 artifact）；
 *   - 评论留痕（[任务汇报] 前缀）。
 *
 * 写盘位置：测试在临时 cwd 下进行（process.chdir），docs/requirements/<REQ>/tasks/
 * 落盘到临时目录，afterEach 递归清理。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, readFileSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { defineTaskReportTool, defineDecomposeTool, definePlanSubmitTool, stubDocFile } from './helpers/tool-deps.js'
import type { RequirementRecord, RequirementStatus } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let prevCwd: string
let store: ReqboardStore
let report: { execute: (a: unknown, e: unknown) => Promise<any> }
let decompose: { execute: (a: unknown, e: unknown) => Promise<any> }
let planTool: { execute: (a: unknown, e: unknown) => Promise<any> }

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-report-'))
  prevCwd = process.cwd()
  process.chdir(dir)
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  const deps = { store, now: () => Date.now() } as never
  report = defineTaskReportTool(deps) as never
  decompose = defineDecomposeTool(deps) as never
  planTool = definePlanSubmitTool(deps) as never
  // REQ-2d1c74 FR-5：plan_submit 起要求提交路径真实落盘（chdir 后 stub 落进本测试临时目录）
  stubDocFile('docs/requirements/REQ-abc123/plan.md')
})
afterEach(() => {
  process.chdir(prevCwd)
  rmSync(dir, { recursive: true, force: true })
})

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

/** 造一个已落库的任务（decompose 走通），返回任务 id。 */
async function seedTask(): Promise<string> {
  await seed('decomposing')
  await planAndApprove()
  const out = await run(decompose, {})
  return out.created[0].id as string
}

describe('reqboard_task_report 汇报落盘 + 登记', () => {
  it('首次汇报：写骨架头 + 追加汇报段 + 登记 task_detail 产物 + 评论留痕', async () => {
    const taskId = await seedTask()
    const out = await run(report, {
      task_id: taskId,
      summary: '完成协议层时间线字段',
      completed: ['加 StatusEvent', '加 recordStatus'],
      files_changed: ['packages/pages/dsh-pmboard/src/shared/protocol.ts'],
      next_step: '客户端渲染',
    })
    expect(out.success).toBe(true)
    expect(out.task_id).toBe(taskId)
    expect(out.requirement_id).toBe('REQ-abc123')
    expect(out.doc_path).toBe('docs/requirements/REQ-abc123/tasks/' + taskId + '.md')
    expect(out.artifact_registered).toBe(true)
    expect(out.report_index).toBe(1)

    // 落盘校验：骨架头 + 汇报段（decompose 生成的骨架是 markdown 格式）
    const docAbs = join(dir, out.doc_path)
    expect(existsSync(docAbs)).toBe(true)
    const text = readFileSync(docAbs, 'utf8')
    expect(text).toContain('# ' + taskId + ' 协议层加时间线')
    expect(text).toContain('单测绿')
    expect(text).toContain('## 汇报 1')
    expect(text).toContain('完成协议层时间线字段')
    expect(text).toContain('- 加 StatusEvent')
    expect(text).toContain('- `packages/pages/dsh-pmboard/src/shared/protocol.ts`')
    expect(text).toContain('客户端渲染')

    // 台账校验：artifact 登记 + 评论（decompose 会登记 plan/decomposition/task_detail，这里只查 task_detail）
    const req = store.snapshot().requirements.find(r => r.id === 'REQ-abc123')!
    const taskDetail = req.artifacts!.find(a => a.kind === 'task_detail' && a.path === out.doc_path)
    expect(taskDetail).toBeDefined()
    expect(taskDetail!.stage).toBe('implementing')
    expect(taskDetail!.registeredBy).toEqual({ kind: 'agent', sessionId: W })
    expect(req.comments.some(c => c.body.startsWith('[任务汇报]') && c.body.includes(taskId))).toBe(true)
  })

  it('tasks/ 子目录递归创建（旧需求无该目录）', async () => {
    const taskId = await seedTask()
    const out = await run(report, { task_id: taskId, summary: 'x' })
    expect(existsSync(join(dir, 'docs/requirements/REQ-abc123/tasks'))).toBe(true)
    expect(existsSync(join(dir, out.doc_path))).toBe(true)
  })

  it('可选字段缺省（completed/files_changed/next_step 不传）不报错', async () => {
    const taskId = await seedTask()
    const out = await run(report, { task_id: taskId, summary: '仅摘要' })
    expect(out.success).toBe(true)
    const text = readFileSync(join(dir, out.doc_path), 'utf8')
    expect(text).toContain('## 汇报 1')
    expect(text).not.toContain('### 完成项')
    expect(text).not.toContain('### 改动文件')
    expect(text).not.toContain('### 下一步')
  })
})

describe('reqboard_task_report 越权拒绝', () => {
  it('任务不存在 → REQBOARD_TASK_NOT_FOUND', async () => {
    await seed('implementing')
    await expect(run(report, { task_id: 't-ffffff', summary: 'x' }))
      .rejects.toThrow(/REQBOARD_TASK_NOT_FOUND/)
  })

  it('任务属于他窗口需求 → REQBOARD_NOT_BOUND_TO_WINDOW', async () => {
    const taskId = await seedTask()
    await expect(run(report, { task_id: taskId, summary: 'x' }, 'session-other'))
      .rejects.toThrow(/REQBOARD_NOT_BOUND_TO_WINDOW/)
  })

  it('summary 为空 → REQBOARD_INVALID_INPUT', async () => {
    const taskId = await seedTask()
    await expect(run(report, { task_id: taskId, summary: '' }))
      .rejects.toThrow(/REQBOARD_INVALID_INPUT/)
  })
})

describe('reqboard_task_report 幂等', () => {
  it('同 task_id 重复汇报：追加新段落，artifact 不重复登记', async () => {
    const taskId = await seedTask()
    const first = await run(report, { task_id: taskId, summary: '第一次汇报' })
    expect(first.report_index).toBe(1)
    expect(first.artifact_registered).toBe(true)

    const second = await run(report, {
      task_id: taskId,
      summary: '第二次汇报',
      completed: ['补单测'],
    })
    expect(second.report_index).toBe(2)
    expect(second.artifact_registered).toBe(true) // 产物已存在（decompose 时登记或首次汇报登记）
    expect(second.doc_path).toBe(first.doc_path)

    // 文档：两段汇报
    const text = readFileSync(join(dir, first.doc_path), 'utf8')
    expect(text).toContain('## 汇报 1')
    expect(text).toContain('## 汇报 2')
    expect(text).toContain('第一次汇报')
    expect(text).toContain('第二次汇报')

    // 同 path 的 artifact 只有一条（幂等）；TWO_TASKS 有 2 个任务所以共 2 条 task_detail
    const req = store.snapshot().requirements.find(r => r.id === 'REQ-abc123')!
    const taskArtifacts = req.artifacts!.filter(a => a.kind === 'task_detail' && a.path === first.doc_path)
    expect(taskArtifacts).toHaveLength(1)
  })
})
