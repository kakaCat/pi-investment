/**
 * H3 注入器测试（REQ-e3b6a0 t6 / FR-4 / AC-4.1 · AC-4.2 · AC-8.1）。
 *
 * 最关键的一条：**G1 确认后注入的是 design 档，不是 brainstorming 档**——这正是"作答后所处阶段"
 * 时序要求的可证伪判据（用真实取词入口算出期望，再断言实际注入与之一致）。
 *
 * @module dsh-pmboard/tests/h3-inject
 */
import { describe, it, expect } from 'vitest'
import { makeHarness, req } from './application/harness.js'
import { createH3InjectHandler } from '../src/application/gate/handlers/h3-inject.js'
import { resolveStagePrompt } from '../src/domain/prompt/index.js'
import type { ConfirmContext } from '../src/domain/gate/GateSpec.js'
import type { ChainScratch } from '../src/application/gate/GatePostChain.js'
import type { ResolvedPrompt } from '../src/domain/prompt/index.js'
import type { InjectionLogInput } from '../src/application/internal/injection-log.js'

const WINDOW = 'session-w-001'
const REQ_ID = 'REQ-000001'

function ctx(over: Partial<ConfirmContext> = {}): ConfirmContext {
  return {
    windowKey: WINDOW, gate: 'G1', from: 'brainstorming', to: 'design',
    requirementId: REQ_ID, verdict: 'affirmative', answers: [], decidedAt: 1000,
    ...over,
  }
}

function seeded(over: Partial<Parameters<typeof req>[0]> = {}) {
  return makeHarness({ requirements: [req({ id: REQ_ID, status: 'design', sourceSessionId: WINDOW, ...over })] })
}

/** 捕获留痕的假端口。 */
function logSink() {
  const entries: InjectionLogInput[] = []
  return { entries, port: { record: (e: InjectionLogInput) => { entries.push(e) } } }
}

describe('H3 注入：时序与内容（AC-4.1）', () => {
  it('G1 确认（brainstorming→design）后注入 design 档，且不含 brainstorming 档', async () => {
    const h = seeded()
    const handler = createH3InjectHandler({ repo: h.repo, docs: h.docs, clock: h.clock } as never)
    const scratch: ChainScratch = {}
    const outcome = await handler.run({ ctx: ctx(), session: {}, scratch })
    expect(outcome).toEqual({ kind: 'continue' })

    // 期望由真实取词入口算出（同一入口，避免测试自造第二套口径）
    const expected = resolveStagePrompt({
      stage: 'design', category: 'feature',
      requirement: { title: '需求', description: 'd' },
    })
    expect(scratch.promptText).toBe(expected.text)
    expect(expected.fragmentIds.some(id => id.startsWith('design/'))).toBe(true)
    expect(expected.fragmentIds.some(id => id.startsWith('brainstorming/'))).toBe(false)
  })

  it('取词阶段由 ctx.to 决定（to=decomposing 时取 decomposing 档）', async () => {
    const h = seeded()
    const handler = createH3InjectHandler({ repo: h.repo } as never)
    const scratch: ChainScratch = {}
    await handler.run({ ctx: ctx({ to: 'decomposing' }), scratch })
    const expected = resolveStagePrompt({ stage: 'decomposing', category: 'feature', requirement: { title: '需求', description: 'd' } })
    expect(scratch.promptText).toBe(expected.text)
  })

  it('按 INV-6 写注入留痕（十字段与取词结果一致）', async () => {
    const h = seeded()
    const sink = logSink()
    const handler = createH3InjectHandler({ repo: h.repo, injectionLog: sink.port } as never)
    await handler.run({ ctx: ctx(), scratch: {} })
    expect(sink.entries).toHaveLength(1)
    const e = sink.entries[0]!
    expect(e.windowKey).toBe(WINDOW)
    expect(e.stage).toBe('design')
    expect(e.category).toBe('feature')
    expect(e.fragmentIds.length).toBeGreaterThan(0)
    expect(e.routeKey.startsWith('design/')).toBe(true)
  })
})

describe('H3 注入：条件不满足 → skip（AC-4.2）', () => {
  it('to 不是可注入阶段（draft）→ not_prompt_stage', async () => {
    const h = seeded()
    const handler = createH3InjectHandler({ repo: h.repo } as never)
    const outcome = await handler.run({ ctx: ctx({ to: 'draft' }), scratch: {} })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'not_prompt_stage' })
  })

  it('无归属需求 → no_requirement', async () => {
    const h = makeHarness({ requirements: [] })
    const handler = createH3InjectHandler({ repo: h.repo } as never)
    const outcome = await handler.run({ ctx: ctx(), scratch: {} })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'no_requirement' })
  })

  it('分类档案跳过该阶段（bug 不走 brainstorming）→ stage_disabled', async () => {
    const h = seeded({ category: 'bug' })
    const handler = createH3InjectHandler({ repo: h.repo } as never)
    const outcome = await handler.run({ ctx: ctx({ to: 'brainstorming' }), scratch: {} })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'stage_disabled' })
  })
})

describe('H3 注入：失败态 → degraded 与难度透传', () => {
  const resolved = (text: string): ResolvedPrompt => ({
    text, fragmentIds: ['x'], routeKey: 'design/light/feature', hitLevel: 1, charCount: text.length, trimmed: [],
  })

  it('取词结果为空 → degraded: empty_prompt', async () => {
    const h = seeded()
    const handler = createH3InjectHandler({ repo: h.repo, resolve: () => resolved('') } as never)
    const outcome = await handler.run({ ctx: ctx(), scratch: {} })
    expect(outcome).toMatchObject({ kind: 'degraded', code: 'empty_prompt' })
  })

  it('取词入口抛错 → degraded: h3_threw（不冒泡）', async () => {
    const h = seeded()
    const handler = createH3InjectHandler({ repo: h.repo, resolve: () => { throw new Error('prompt lib down') } } as never)
    const outcome = await handler.run({ ctx: ctx(), scratch: {} })
    expect(outcome).toMatchObject({ kind: 'degraded', code: 'h3_threw' })
    expect(JSON.stringify(outcome)).toContain('prompt lib down')
  })

  it('声明难度透传为 declaredDifficulty（expert→heavy / simple→light / 未声明→不传）', async () => {
    const seen: Array<string | undefined> = []
    const spyResolve = (r: { declaredDifficulty?: string }) => { seen.push(r.declaredDifficulty); return resolved('T') }

    const hExpert = seeded({ promptDifficulty: 'expert' })
    const h1 = createH3InjectHandler({ repo: hExpert.repo, resolve: spyResolve } as never)
    await h1.run({ ctx: ctx(), scratch: {} })
    expect(seen[0]).toBe('heavy')

    const hSimple = seeded({ promptDifficulty: 'simple' })
    const h2 = createH3InjectHandler({ repo: hSimple.repo, resolve: spyResolve } as never)
    await h2.run({ ctx: ctx(), scratch: {} })
    expect(seen[1]).toBe('light')

    const hNone = seeded()
    const h3 = createH3InjectHandler({ repo: hNone.repo, resolve: spyResolve } as never)
    await h3.run({ ctx: ctx(), scratch: {} })
    expect(seen[2]).toBeUndefined()
  })

  it('未提供 scratch 时不抛（单跑 handler 的兼容路径）', async () => {
    const h = seeded()
    const handler = createH3InjectHandler({ repo: h.repo } as never)
    await expect(handler.run({ ctx: ctx() })).resolves.toEqual({ kind: 'continue' })
  })
})
