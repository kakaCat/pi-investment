/**
 * reqboard_capture 单测（REQ-e3b6a0 t8 / FR-7 / AC-7.2）——立项三问 pm 专有弹框：一次调用一把梭。
 *
 * 覆盖：三问同批弹出 → 答案映射（自定义优先 / 缺项回落默认并记 defaults_used）→ 创建即立项
 * → 绑定本窗口 → 推进 brainstorming；通道不可用 → fallback=board **不伪造立项**；
 * 用户取消 → 中性失败；名称为空 → 响亮失败；窗口已绑定 → 拒绝（白弹一次框是最贵的浪费）。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { defineCaptureTool } from './helpers/tool-deps.js'
import {
  CAPTURE_QUESTION_IDS,
  buildCaptureQuestions,
  mapCaptureAnswers,
} from '../src/application/internal/capture-mapping.js'
import type { AskAnswer } from '../src/application/ports.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-capture-1'

let dir: string
let store: ReqboardStore

/** 假弹框服务：记录收到的问题，按给定作答返回（'abort' → 抛 ASK_ABORTED）。 */
function makeSvc(answers: readonly AskAnswer[] | 'abort') {
  const seen: { questions: unknown[] } = { questions: [] }
  return {
    seen,
    ask: async (req: { questions?: unknown[] }) => {
      seen.questions = req.questions ?? []
      if (answers === 'abort') throw Object.assign(new Error('aborted'), { code: 'ASK_ABORTED' })
      return { answers: [...answers] }
    },
  }
}

function makeTool(opts: { svc?: unknown } = {}) {
  const deps = {
    store,
    now: () => 1_700_000_000_000,
    ...(opts.svc !== undefined ? { userQuestions: () => opts.svc } : {}),
  } as never
  return defineCaptureTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown = {}) =>
  tool.execute(args, { agent: { id: W } })

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-capture-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seedBound(): Promise<void> {
  const r = {
    id: 'REQ-bound1', title: '在途需求', description: '', status: 'brainstorming', blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status: 'draft', at: 1, by: { kind: 'human' } }],
  } as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

const THREE: AskAnswer[] = [
  { id: CAPTURE_QUESTION_IDS.name, selected: ['候选名称'] },
  { id: CAPTURE_QUESTION_IDS.category, selected: ['bug'] },
  { id: CAPTURE_QUESTION_IDS.difficulty, selected: ['advanced'] },
]

describe('reqboard_capture · 三问口径', () => {
  it('buildCaptureQuestions：恰好三问，id 顺序 = 名称/类型/难度，选项首个即推荐位', () => {
    const qs = buildCaptureQuestions(['候选一', '候选二'])
    expect(qs.map(q => q.id)).toEqual(['name', 'category', 'difficulty'])
    expect(qs[0]!.options?.[0]).toMatchObject({ label: '候选一', description: '推荐' })
    expect(qs[1]!.options?.map(o => o.label)).toContain('feature')
    expect(qs[2]!.options?.map(o => o.label)).toEqual(['simple', 'standard', 'advanced', 'expert'])
    expect(qs[2]!.options?.find(o => o.description === '推荐')?.label).toBe('standard')
  })

  it('mapCaptureAnswers：名称自定义优先于选项；类型/难度取选项', () => {
    const m = mapCaptureAnswers([
      { id: 'name', selected: ['候选名称'], custom: '  用户自定义名称  ' },
      { id: 'category', selected: ['spike'] },
      { id: 'difficulty', selected: ['expert'] },
    ])
    expect(m.title).toBe('用户自定义名称')
    expect(m.category).toBe('spike')
    expect(m.difficulty).toBe('expert')
    expect(m.defaultsUsed).toEqual([])
  })

  it('mapCaptureAnswers：缺项/非法值 → 回落既有默认并记进 defaultsUsed（不静默猜）', () => {
    const m = mapCaptureAnswers([{ id: 'name', selected: ['只要名称'] }])
    expect(m.category).toBe('feature')
    expect(m.difficulty).toBe('standard')
    expect(m.defaultsUsed).toEqual(['category', 'difficulty'])
    const bad = mapCaptureAnswers([
      { id: 'name', selected: ['x'] },
      { id: 'category', selected: ['不存在的类型'] },
      { id: 'difficulty', selected: ['不存在的难度'] },
    ])
    expect(bad.category).toBe('feature')
    expect(bad.difficulty).toBe('standard')
    expect(bad.defaultsUsed).toEqual(['category', 'difficulty'])
  })
})

describe('reqboard_capture · 一次调用一把梭（AC-7.2）', () => {
  it('三问同批弹出 → 创建即立项 → 绑定本窗口 → 推进 brainstorming', async () => {
    const svc = makeSvc(THREE)
    const out = await run(makeTool({ svc }), { title_options: ['候选名称'] })
    // 三问同批
    expect(svc.seen.questions).toHaveLength(3)
    expect((svc.seen.questions as { id?: string }[]).map(q => q.id)).toEqual(['name', 'category', 'difficulty'])
    // 立项成功 + 绑定 + 推进
    expect(out.success).toBe(true)
    expect(out.requirement_id).toMatch(/^REQ-/)
    expect(out.status).toBe('brainstorming')
    expect(out.answers).toMatchObject({ title: '候选名称', category: 'bug', difficulty: 'advanced' })
    expect(out.defaults_used).toEqual([])
    const req = store.snapshot().requirements.find(r => r.id === out.requirement_id)!
    expect(req.sourceSessionId).toBe(W)
    expect(req.status).toBe('brainstorming')
    expect(req.category).toBe('bug')
    expect(req.promptDifficulty).toBe('advanced')
  })

  it('用户自定义名称优先（选项在场也不用它）', async () => {
    const svc = makeSvc([
      { id: 'name', selected: ['候选名称'], custom: '我自己起的名字' },
      { id: 'category', selected: ['doc'] },
      { id: 'difficulty', selected: ['simple'] },
    ])
    const out = await run(makeTool({ svc }), {})
    expect(out.answers.title).toBe('我自己起的名字')
    expect(store.snapshot().requirements[0]!.title).toBe('我自己起的名字')
  })

  it('弹框通道不可用 → fallback=board，且**不创建任何需求**', async () => {
    const out = await run(makeTool({}), {})
    expect(out.success).toBe(false)
    expect(out.requirement_id).toBe('')
    expect(out.fallback).toBe('board')
    expect(store.snapshot().requirements).toHaveLength(0)
  })

  it('用户取消（ASK_ABORTED）→ 中性失败，不创建需求', async () => {
    const out = await run(makeTool({ svc: makeSvc('abort') }), {})
    expect(out.success).toBe(false)
    expect(out.fallback).toBeUndefined()
    expect(out.note).toContain('未作答')
    expect(store.snapshot().requirements).toHaveLength(0)
  })

  it('名称为空 → 响亮失败（名称没有默认值，不猜不补）', async () => {
    const svc = makeSvc([{ id: 'category', selected: ['bug'] }, { id: 'difficulty', selected: ['expert'] }])
    const out = await run(makeTool({ svc }), {})
    expect(out.success).toBe(false)
    expect(out.note).toContain('需求名称')
    expect(store.snapshot().requirements).toHaveLength(0)
  })

  it('窗口已绑定进行中需求 → 拒绝（不白弹一次框）', async () => {
    await seedBound()
    const svc = makeSvc(THREE)
    await expect(run(makeTool({ svc }), {})).rejects.toMatchObject({ code: 'REQBOARD_WINDOW_BOUND' })
    expect(svc.seen.questions).toHaveLength(0) // 弹框根本没发生
  })
})
