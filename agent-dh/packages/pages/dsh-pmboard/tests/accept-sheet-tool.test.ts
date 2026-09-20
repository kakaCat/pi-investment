/**
 * reqboard_accept_sheet 单测（REQ-2e9473 W6 补口）：弹框逐项验收 → 直接落库裁决
 * （系统见证，无需 agent 转述）→ 未过项自动返工；分批 + 断点续验；降级。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { defineVerifySubmitTool, defineAcceptSheetTool } from './helpers/tool-deps.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-as-001'
let dir: string
let store: ReqboardStore

/**
 * 假弹框：answers 为批次队列（每次 ask 消费一批）；'delegated'/'abort' 为异常路径。
 * 队列耗尽后返回空答复（模拟用户未作答）。
 */
function sheetTool(answers: any[] | any[][] | 'delegated' | 'abort' | undefined) {
  const queue: any[][] = Array.isArray(answers) && Array.isArray((answers as any[])[0])
    ? [...(answers as any[][])]
    : (Array.isArray(answers) ? [answers as any[]] : [])
  const ask = async () => {
    if (answers === 'delegated') throw Object.assign(new Error('owned child'), { code: 'DELEGATED_CALLER' })
    if (answers === 'abort') throw Object.assign(new Error('aborted'), { code: 'ASK_ABORTED' })
    const batch = queue.shift() ?? []
    return { answers: batch }
  }
  const deps = {
    store, now: () => Date.now(),
    ...(answers !== undefined ? { userQuestions: () => ({ ask }) } : {}),
  } as never
  return defineAcceptSheetTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
}
const verifyTool = () => defineVerifySubmitTool({ store, now: () => Date.now() } as never) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
const run = (tool: any, args: unknown) => tool.execute(args, { agent: { id: W } })

beforeEach(async () => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-sheettool-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  const r = {
    id: 'REQ-as0001', title: '验收弹框', description: '', status: 'implementing', category: 'feature',
    blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => {
    l.requirements.push(r)
    for (let i = 1; i <= 3; i++) {
      l.tasks.push({
        id: 't-as000' + i, requirementId: r.id, title: '任务' + i, description: '', phase: 'implement', side: 'backend',
        dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: '验收标准 ' + i, implementation: '改 x' + i,
        context: '', status: 'done', blocked: false, executions: [], comments: [], version: 1,
        createdAt: 1, updatedAt: 1, createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
      } as never)
    }
    return { requirements: [r] }
  })
  await run(verifyTool(), { summary: '交付', evidence: ['npx vitest run 全绿'] })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

const sheetOf = () => store.snapshot().requirements[0].verification!.sheet!

describe('reqboard_accept_sheet', () => {
  it('分批：batch_size=2 → 本批记 2 项，剩 2 项（3 任务+1 需求级）继续', async () => {
    const sheet = sheetOf()
    const ids = sheet.items.map(i => i.id)
    const out = await run(sheetTool([
      { id: ids[0], selected: ['✅ 通过'] },
      { id: ids[1], selected: ['✅ 通过'] },
    ]), { batch_size: 2 })
    expect(out.recorded).toBe(2)
    expect(out.pending).toBe(2)
    expect(out.note).toMatch(/断点继续/)
    expect(store.snapshot().requirements[0].status).toBe('accepting')
  })

  it('选"改进"+自定义意见 → 记 failed，并**自动回退实施 + 建返工卡**（REQ-308b9a FR-8，推翻 REQ-a8d582 FR-2）', async () => {
    const ids = sheetOf().items.map(i => i.id)
    const out = await run(sheetTool([
      { id: ids[0], selected: ['✅ 通过'] },
      { id: ids[1], selected: ['🛠 改进（需修改）'], custom: '边界没覆盖' },
      { id: ids[2], selected: ['❓ 其他'], custom: '需补充文档' },
    ]), { batch_size: 5 })
    expect(out.failed).toBe(2)
    expect(out.rework_tasks).toHaveLength(2)
    const snap = store.snapshot()
    expect(snap.requirements[0].status).toBe('implementing')
    expect(snap.tasks).toHaveLength(5) // 原有 3 张 + 2 张返工卡
    expect(out.note).toMatch(/自动回退/)
    // 验收项裁决留痕
    const item = sheetOf().items.find(i => i.id === ids[1])!
    expect(item.status).toBe('failed')
    expect(item.opinion).toBe('边界没覆盖')
    expect(item.decidedBy?.kind).toBe('human')
  })

  it('未作答的项保持 pending（挂起点）', async () => {
    const ids = sheetOf().items.map(i => i.id)
    await run(sheetTool([{ id: ids[0], selected: ['✅ 通过'] }]), { batch_size: 3 })
    const s = sheetOf()
    expect(s.items).toHaveLength(4) // 3 任务 + 1 需求级
    expect(s.items.filter(i => i.status === 'pending')).toHaveLength(3)
    expect(s.items.find(i => i.id === ids[0])!.status).toBe('passed')
    expect(s.items.find(i => i.id === ids[3])!.status).toBe('pending')
  })

  it('闭环返回值字段均在输出 schema 声明内（防 additionalProperties:false 拒收）', async () => {
    const ids = sheetOf().items.map(i => i.id)
    const out = await run(sheetTool([
      ids.map(id => ({ id, selected: ['✅ 通过'] })),
      [{ id: 'final-pass', selected: ['✅ 验收通过并归档'] }],
    ]), { batch_size: 10 })
    const declared = new Set(['success', 'requirement_id', 'sheet_version', 'recorded', 'pending', 'passed', 'failed', 'rework_tasks', 'archived', 'status', 'fallback', 'note'])
    for (const k of Object.keys(out)) expect(declared.has(k), k).toBe(true)
  })

  it('弹框不可用 → fallback=board；subagent → fallback=board', async () => {
    const out1 = await run(sheetTool(undefined), {})
    expect(out1.fallback).toBe('board')
    const out2 = await run(sheetTool('delegated'), {})
    expect(out2.fallback).toBe('board')
  })

  it('用户取消 → 中性返回不记录', async () => {
    const out = await run(sheetTool('abort'), {})
    expect(out.success).toBe(false)
    expect(sheetOf().items.every(i => i.status === 'pending')).toBe(true)
  })

  it('全部通过后直接弹「验收通过」确认 → 同意即归档（闭环，用户要求）', async () => {
    const ids = sheetOf().items.map(i => i.id)
    const out = await run(sheetTool([
      // 第一批：逐项全过
      ids.map(id => ({ id, selected: ['✅ 通过'] })),
      // 第二批：最终确认
      [{ id: 'final-pass', selected: ['✅ 验收通过并归档'] }],
    ]), { batch_size: 10 })
    expect(out.archived).toBe(true)
    expect(out.status).toBe('archived')
    expect(out.note).toMatch(/已归档/)
    const req = store.snapshot().requirements[0]
    expect(req.status).toBe('archived')
    expect(req.verification!.decision).toBe('pass')
    expect(req.verification!.reviewedBy?.kind).toBe('human')
  })

  it('最终确认选「暂不归档」→ 保持验收态', async () => {
    const ids = sheetOf().items.map(i => i.id)
    const out = await run(sheetTool([
      ids.map(id => ({ id, selected: ['✅ 通过'] })),
      [{ id: 'final-pass', selected: ['暂不归档'] }],
    ]), { batch_size: 10 })
    expect(out.archived).toBeUndefined()
    expect(out.note).toMatch(/保持验收态/)
    expect(store.snapshot().requirements[0].status).toBe('accepting')
  })
})
