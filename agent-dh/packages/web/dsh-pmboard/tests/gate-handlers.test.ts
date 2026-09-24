/**
 * H1 / H4 / H5 三个 handler 测试（REQ-e3b6a0 t7 / FR-2 · FR-5 · FR-6）。
 *
 * H1：Phase B 以台账实时状态回填 verdict/requirementId；
 * H4：按 D5 分流组唤醒消息并投递（压缩过 → 只发摘要；否则带提示词全文）；
 * H5：把各步结果写成链级审计评论。
 *
 * @module dsh-pmboard/tests/gate-handlers
 */
import { describe, it, expect } from 'vitest'
import { makeHarness, req } from './application/harness.js'
import { createH1AdvanceHandler } from '../src/application/gate/handlers/h1-advance.js'
import { createH4ResumeHandler } from '../src/application/gate/handlers/h4-resume.js'
import { createH5AuditHandler } from '../src/application/gate/handlers/h5-audit.js'
import type { ConfirmContext } from '../src/domain/gate/GateSpec.js'
import type { ChainScratch } from '../src/application/gate/GatePostChain.js'
import type { AgentDeliveryPort, DeliveryResult } from '../src/application/ports.js'

const W = 'session-w-001'
const REQ_ID = 'REQ-000001'

function ctx(over: Partial<ConfirmContext> = {}): ConfirmContext {
  return {
    windowKey: W, gate: 'G1', from: 'brainstorming', to: 'design',
    requirementId: REQ_ID, answers: [{ id: 'confirm', selected: ['确认推进'] }], decidedAt: 1000,
    ...over,
  }
}

function deliverySpy(): { port: AgentDeliveryPort; sent: Array<{ windowKey: string; text: string }>; fail?: string } {
  const box = {
    sent: [] as Array<{ windowKey: string; text: string }>,
    fail: undefined as string | undefined,
    port: undefined as unknown as AgentDeliveryPort,
  }
  box.port = {
    deliver(windowKey, message): DeliveryResult {
      if (box.fail !== undefined) return { delivered: false, reason: box.fail }
      box.sent.push({ windowKey, text: message.text })
      return { delivered: true }
    },
  }
  return box as never
}

describe('H1 推进校验与回填', () => {
  it('台账 status === to → verdict=affirmative 且回填 requirementId', async () => {
    const h = makeHarness({ requirements: [req({ id: REQ_ID, status: 'design', sourceSessionId: W })] })
    const handler = createH1AdvanceHandler({ repo: h.repo })
    const c = ctx()
    const outcome = await handler.run({ ctx: c })
    expect(outcome).toEqual({ kind: 'continue' })
    expect(c.verdict).toBe('affirmative')
    expect(c.requirementId).toBe(REQ_ID)
  })

  it('未推进到 to（非肯定项）→ verdict=negative 且 skip: not_advanced', async () => {
    const h = makeHarness({ requirements: [req({ id: REQ_ID, status: 'brainstorming', sourceSessionId: W })] })
    const handler = createH1AdvanceHandler({ repo: h.repo })
    const c = ctx()
    const outcome = await handler.run({ ctx: c })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'not_advanced' })
    expect(c.verdict).toBe('negative')
  })

  it('无归属需求 → verdict=negative 且 skip: no_requirement', async () => {
    const h = makeHarness({ requirements: [] })
    const handler = createH1AdvanceHandler({ repo: h.repo })
    const c = ctx({ requirementId: undefined })
    const outcome = await handler.run({ ctx: c })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'no_requirement' })
    expect(c.verdict).toBe('negative')
  })
})

describe('H4 唤醒（D5 分流）', () => {
  it('H2 已压缩 → 只发作答摘要，不带提示词全文', async () => {
    const d = deliverySpy()
    const handler = createH4ResumeHandler({ delivery: d.port, plugin: 'dsh-pmboard' })
    const scratch: ChainScratch = { promptText: '【design 阶段纪律】不变量A', compacted: true }
    const outcome = await handler.run({ ctx: ctx({ verdict: 'affirmative' }), scratch })
    expect(outcome).toEqual({ kind: 'continue' })
    expect(d.sent).toHaveLength(1)
    expect(d.sent[0]!.text).toContain('闸门确认')
    expect(d.sent[0]!.text).toContain('确认推进')
    expect(d.sent[0]!.text).not.toContain('不变量A')
  })

  it('H2 跳过/降级 → 摘要 + 阶段纪律提示词全文', async () => {
    const d = deliverySpy()
    const handler = createH4ResumeHandler({ delivery: d.port })
    const scratch: ChainScratch = { promptText: '【design 阶段纪律】不变量A' }
    await handler.run({ ctx: ctx({ verdict: 'affirmative' }), scratch })
    expect(d.sent[0]!.text).toContain('不变量A')
  })

  it('非肯定项也要唤醒（带用户意见）', async () => {
    const d = deliverySpy()
    const handler = createH4ResumeHandler({ delivery: d.port })
    const c = ctx({ verdict: 'negative', from: 'brainstorming', to: 'design', answers: [{ id: 'confirm', selected: ['需要修改'], custom: '补边界' }] })
    await handler.run({ ctx: c, scratch: {} })
    expect(d.sent[0]!.text).toContain('待改进')
    expect(d.sent[0]!.text).toContain('补边界')
  })

  it('无 from 的闸门（G0 立项门）负分支 → 不编造"节点仍在 X"（REQ-260924002956-f37c BUG-2）', async () => {
    const d = deliverySpy()
    const handler = createH4ResumeHandler({ delivery: d.port })
    // G0 没有 from（尚未绑定需求）：负分支只能说"未通过"，没有"当前节点"可言
    const c = ctx({ gate: 'G0', from: undefined, to: 'brainstorming', requirementId: undefined, verdict: 'negative', answers: [{ id: 'name', selected: ['✖️ 不需要立项'] }] })
    await handler.run({ ctx: c, scratch: {} })
    expect(d.sent).toHaveLength(1)
    expect(d.sent[0]!.text).toContain('待改进')
    expect(d.sent[0]!.text).not.toContain('节点仍在')
  })

  it('有 from 的闸门负分支仍印"节点仍在 {from}"（防把 H4 改反）', async () => {
    const d = deliverySpy()
    const handler = createH4ResumeHandler({ delivery: d.port })
    await handler.run({ ctx: ctx({ verdict: 'negative', from: 'design', to: 'decomposing' }), scratch: {} })
    expect(d.sent).toHaveLength(1)
    expect(d.sent[0]!.text).toContain('节点仍在 design')
  })

  it('投递失败 → degraded: not_delivered（不抛）', async () => {
    const d = deliverySpy()
    d.fail = '窗口不在线'
    const handler = createH4ResumeHandler({ delivery: d.port })
    const outcome = await handler.run({ ctx: ctx({ verdict: 'affirmative' }), scratch: {} })
    expect(outcome).toMatchObject({ kind: 'degraded', code: 'not_delivered' })
  })
})

describe('H5 链级审计', () => {
  it('把各步结果写成需求时间线评论', async () => {
    const h = makeHarness({ requirements: [req({ id: REQ_ID, sourceSessionId: W })] })
    const handler = createH5AuditHandler({ repo: h.repo, now: () => 123, newCommentId: () => 'c-audit' })
    const scratch: ChainScratch = {
      steps: [
        { name: 'h1-advance', outcome: { kind: 'continue' } },
        { name: 'h2-compact', outcome: { kind: 'skip', code: 'doc_not_ready', reason: 'r' } },
        { name: 'h4-resume', outcome: { kind: 'degraded', code: 'not_delivered', reason: 'r' } },
      ],
    }
    const outcome = await handler.run({ ctx: ctx({ verdict: 'affirmative' }), scratch })
    expect(outcome).toEqual({ kind: 'continue' })
    const body = h.repo.snapshot().requirements[0]!.comments.at(-1)!.body
    expect(body).toContain('[闸门后置链] G1')
    expect(body).toContain('h1-advance=ok')
    expect(body).toContain('h2-compact=skip（doc_not_ready）')
    expect(body).toContain('h4-resume=degraded（not_delivered）')
  })

  it('无 requirementId → skip: no_requirement（不写台账）', async () => {
    const h = makeHarness({})
    const handler = createH5AuditHandler({ repo: h.repo, now: () => 1, newCommentId: () => 'c' })
    const outcome = await handler.run({ ctx: ctx({ requirementId: undefined }), scratch: {} })
    expect(outcome).toMatchObject({ kind: 'skip', code: 'no_requirement' })
  })
})
