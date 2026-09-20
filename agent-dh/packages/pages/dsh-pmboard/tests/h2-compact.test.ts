/**
 * H2 压缩接线测试（REQ-e3b6a0 t5 / FR-3 / AC-3.1 ~ AC-3.4）。
 *
 * 分两层：
 *  · **真跑**：用真实 `isolateNodeContext` + 假隔离端口，断言 replaced 与区间（AC-3.1）。
 *  · **映射**：条件不满足 / 失败态的四条路径各自 skip 或 degraded（AC-3.2）。
 *
 * @module dsh-pmboard/tests/h2-compact
 */
import { describe, it, expect } from 'vitest'
import { makeHarness, req } from './application/harness.js'
import { createH2CompactHandler } from '../src/application/gate/handlers/h2-compact.js'
import type { ConfirmContext } from '../src/domain/gate/GateSpec.js'
import type {
  IsolateNodeContextDeps,
  IsolateNodeContextRequest,
  IsolateNodeContextResult,
  NodeIsolationPort,
} from '../src/application/use-cases/IsolateNodeContext.js'

const WINDOW = 'session-w-001'
const REQ_ID = 'REQ-000001'
const DOC_PATH = 'docs/requirements/REQ-000001/requirement.md'

function ctx(over: Partial<ConfirmContext> = {}): ConfirmContext {
  return {
    windowKey: WINDOW, gate: 'G1', from: 'brainstorming', to: 'design',
    requirementId: REQ_ID, verdict: 'affirmative', answers: [], decidedAt: 1000,
    ...over,
  }
}

/** 假隔离端口：surface = [系统段, 历史, 历史]，替换返回更大的 seq（保证 artifactSeq < replacementSeq）。 */
function fakePort(over: Partial<NodeIsolationPort> = {}) {
  const replaces: Array<{ start: number; end: number; shadowed: readonly number[] }> = []
  const port = {
    reachable: () => true,
    idle: () => true,
    surface: () => [
      { seq: 0, type: 'system/message' },
      { seq: 1, type: 'user/message' },
      { seq: 2, type: 'assistant/message' },
    ],
    balancedBefore: () => true,
    balancedAfter: () => true,
    replace: (input: { start: number; end: number; shadowed: readonly number[] }) => {
      replaces.push({ start: input.start, end: input.end, shadowed: input.shadowed })
      return 100
    },
    ...over,
  } as unknown as NodeIsolationPort
  return { port, replaces }
}

/** 种子：一个进行中需求 + 已落盘的需求文档。 */
function seeded(withDoc = true) {
  const h = makeHarness({
    requirements: [req({ id: REQ_ID, status: 'design', sourceSessionId: WINDOW })],
  })
  if (withDoc) h.docs.put(DOC_PATH, '# 需求文档\n正文标记 DOC-BODY')
  return h
}

describe('H2 压缩：真跑 replaced（AC-3.1 / AC-3.3）', () => {
  it('肯定项 + 文档已落盘 → replaced 且区间自首个非 system 节点起；artifactSeq < replacementSeq', async () => {
    const h = seeded()
    const { port, replaces } = fakePort()
    const handler = createH2CompactHandler({ repo: h.repo, docs: h.docs, clock: h.clock, isolationFor: () => port })
    const outcome = await handler.run({ ctx: ctx(), session: {} })
    expect(outcome).toEqual({ kind: 'continue' })
    expect(replaces).toHaveLength(1)
    expect(replaces[0]!.start).toBe(1) // 首个非 system 节点
    expect(replaces[0]!.end).toBe(2)
    expect(replaces[0]!.shadowed).toEqual([1, 2])
    // 先落盘再遗弃：persistArtifacts 返回台账 revision(0) < 替换 seq(100)
    expect(h.repo.snapshot().revision).toBe(0)
  })
})

describe('H2 压缩：条件不满足 → skip（AC-3.2）', () => {
  it('非肯定项 → negative_verdict，且**不调用**压缩用例', async () => {
    const h = seeded()
    let called = 0
    const handler = createH2CompactHandler({
      repo: h.repo, docs: h.docs, clock: h.clock,
      run: async () => { called += 1; throw new Error('不该被调用') },
    })
    const outcome = await handler.run({ ctx: ctx({ verdict: 'negative' }), session: {} })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'negative_verdict' })
    expect(called).toBe(0)
  })

  it('to 不是可注入阶段（draft）→ not_prompt_stage', async () => {
    const h = seeded()
    const handler = createH2CompactHandler({ repo: h.repo, docs: h.docs, clock: h.clock })
    const outcome = await handler.run({ ctx: ctx({ to: 'draft' }), session: {} })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'not_prompt_stage' })
  })

  it('需求文档未落盘 → doc_not_ready（输入包不自足的闸）', async () => {
    const h = seeded(false)
    const handler = createH2CompactHandler({ repo: h.repo, docs: h.docs, clock: h.clock, isolationFor: () => fakePort().port })
    const outcome = await handler.run({ ctx: ctx(), session: {} })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'doc_not_ready' })
  })

  it('本窗口无归属需求 → no_requirement', async () => {
    const h = makeHarness({ requirements: [] })
    const handler = createH2CompactHandler({ repo: h.repo, docs: h.docs, clock: h.clock })
    const outcome = await handler.run({ ctx: ctx(), session: {} })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'no_requirement' })
  })

  it('agent 忙（idle=false）→ skip: agent_busy', async () => {
    const h = seeded()
    const { port } = fakePort({ idle: () => false })
    const handler = createH2CompactHandler({ repo: h.repo, docs: h.docs, clock: h.clock, isolationFor: () => port })
    const outcome = await handler.run({ ctx: ctx(), session: {} })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'agent_busy' })
  })
})

describe('H2 压缩：失败态 → degraded（AC-3.2 / AC-3.4）', () => {
  it('触达不到会话 → fallback 降级为 degraded', async () => {
    const h = seeded()
    const handler = createH2CompactHandler({ repo: h.repo, docs: h.docs, clock: h.clock })
    const outcome = await handler.run({ ctx: ctx(), session: {} })
    expect(outcome).toMatchObject({ kind: 'degraded', code: 'isolation_unreachable' })
  })

  it('边界 tool 配对不平衡 → rejected 降级为 degraded', async () => {
    const h = seeded()
    const { port } = fakePort({ balancedAfter: () => false })
    const handler = createH2CompactHandler({ repo: h.repo, docs: h.docs, clock: h.clock, isolationFor: () => port })
    const outcome = await handler.run({ ctx: ctx(), session: {} })
    expect(outcome).toMatchObject({ kind: 'degraded', code: 'boundary_unbalanced' })
  })

  it('用例抛未预期异常 → degraded: h2_threw（不冒泡）', async () => {
    const h = seeded()
    const handler = createH2CompactHandler({
      repo: h.repo, docs: h.docs, clock: h.clock,
      run: async () => { throw new Error('unexpected') },
    })
    const outcome = await handler.run({ ctx: ctx(), session: {} })
    expect(outcome).toMatchObject({ kind: 'degraded', code: 'h2_threw' })
    expect(JSON.stringify(outcome)).toContain('unexpected')
  })

  it('docs.read 抛错按未落盘处理（skip，不冒泡）', async () => {
    const h = seeded()
    h.docs.read = async () => { throw new Error('fs down') }
    const handler = createH2CompactHandler({ repo: h.repo, docs: h.docs, clock: h.clock })
    const outcome = await handler.run({ ctx: ctx(), session: {} })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'doc_not_ready' })
  })

  it('显式 run 替身可断言请求形状（windowKey/stage/category/requirementId）', async () => {
    const h = seeded()
    let seen: IsolateNodeContextRequest | undefined
    const handler = createH2CompactHandler({
      repo: h.repo, docs: h.docs, clock: h.clock,
      run: async (_d: IsolateNodeContextDeps, request: IsolateNodeContextRequest) => {
        seen = request
        return {
          status: 'replaced', replaced: true, routeKey: 'design/light/feature', fragmentIds: [],
          packageText: 'pkg', range: { start: 1, end: 2 }, artifactSeq: 0, replacementSeq: 1,
          trace: { at: 0, windowKey: WINDOW, stage: 'design', status: 'replaced', reason: 'ok', routeKey: 'design/light/feature', packageChars: 3 },
        } as IsolateNodeContextResult
      },
    })
    await handler.run({ ctx: ctx(), session: {} })
    expect(seen).toMatchObject({
      windowKey: WINDOW,
      stage: 'design',
      category: 'feature',
      requirementId: REQ_ID,
    })
  })
})
