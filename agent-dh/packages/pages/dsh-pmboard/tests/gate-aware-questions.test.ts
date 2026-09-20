/**
 * GateAwareQuestions 装饰器测试（REQ-e3b6a0 t7 / FR-1 · FR-10 / AC-1.1 · AC-10.2）。
 *
 * 两件事：
 *  ① 装饰器语义（带 gate 登记 / 不带不登记 / 无作答不登记 / 取不到窗口不抛 / 协议零变化）；
 *  ② **三条 pm 弹框路径**作答后各触发一次链（AskConfirm 一次 + accept_sheet 逐项与最终各一次）。
 *
 * @module dsh-pmboard/tests/gate-aware-questions
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { makeHarness, req } from './application/harness.js'
import { GateAwareQuestions } from '../src/adapters/GateAwareQuestions.js'
import { createGatePostChain } from '../src/application/gate/GatePostChain.js'
import { createPendingGateStore } from '../src/application/gate/PendingGate.js'
import { askConfirm } from '../src/application/use-cases/AskConfirm.js'
import { acceptSheet } from '../src/application/use-cases/AcceptSheet.js'
import { DEFAULT_CONFIRM_OPTIONS, ACCEPT_ITEM_OPTIONS, FINAL_PASS_LABEL } from '../src/domain/text/labels.js'
import type { AskAnswer, AskQuestion, UserQuestionPort } from '../src/application/ports.js'

const W = 'session-w-001'
const REQ_ID = 'REQ-000001'

/** 批次队列假 UI：每次 ask 消费一批答案；可注入异常。 */
function queueUI(batches: AskAnswer[][]) {
  const seenOpts: Array<{ gate?: string }> = []
  const port: UserQuestionPort = {
    available: () => true,
    ask: async (_q: readonly AskQuestion[], opts: { gate?: string }) => {
      seenOpts.push({ ...(opts.gate === undefined ? {} : { gate: opts.gate }) })
      return batches.shift() ?? []
    },
  }
  return { port, seenOpts }
}

/** 造一条链（空 handler：只验证"被登记"这一件事）。 */
function chainWithStore() {
  const pending = createPendingGateStore()
  const chain = createGatePostChain({ handlers: [], enabled: true, pending })
  return { chain, pending }
}

describe('装饰器语义（AC-1.1）', () => {
  it('带 opts.gate 且确有作答 → 登记一次，且上下文含 gate/to/answers/窗口', async () => {
    const { port } = queueUI([[{ id: "confirm", selected: ["ok"] }]])
    const { chain, pending } = chainWithStore()
    const g = new GateAwareQuestions(port, chain, { now: () => 42 })
    const answers = await g.ask([{ id: 'confirm', question: 'q' }], { agent: { id: W }, gate: 'G1' })
    expect(answers).toEqual([{ id: 'confirm', selected: ['ok'] }])
    expect(chain.stats().enqueued).toBe(1)
    const ctx = pending.peek(W)!
    expect(ctx).toMatchObject({ windowKey: W, gate: 'G1', to: 'design', decidedAt: 42 })
    expect(ctx.answers).toHaveLength(1)
    expect(ctx.verdict).toBeUndefined() // Phase B 由 H1 回填
  })

  it('不带 gate → 不登记（通用征询不进链）', async () => {
    const { port } = queueUI([[{ id: 'a', selected: ['ok'] }]])
    const { chain, pending } = chainWithStore()
    const g = new GateAwareQuestions(port, chain)
    await g.ask([{ id: 'a', question: 'q' }], { agent: { id: W } })
    expect(chain.stats().enqueued).toBe(0)
    expect(pending.size()).toBe(0)
  })

  it('无作答（用户取消/暂离）→ 不登记', async () => {
    const { port } = queueUI([[]])
    const { chain, pending } = chainWithStore()
    const g = new GateAwareQuestions(port, chain)
    await g.ask([{ id: 'c', question: 'q' }], { agent: { id: W }, gate: 'G1' })
    expect(chain.stats().enqueued).toBe(0)
    expect(pending.size()).toBe(0)
  })

  it('取不到窗口（agent 缺 id）→ 不登记、不抛', async () => {
    const { port } = queueUI([[{ id: 'c', selected: ['ok'] }]])
    const { chain } = chainWithStore()
    const g = new GateAwareQuestions(port, chain)
    await expect(g.ask([{ id: 'c', question: 'q' }], { agent: {}, gate: 'G1' })).resolves.toHaveLength(1)
    expect(chain.stats().enqueued).toBe(0)
  })

  it('available() 与 questions/answers 原样透传（协议零变化）', async () => {
    const { port, seenOpts } = queueUI([[{ id: 'c', selected: ['ok'], custom: 'x' }]])
    const { chain } = chainWithStore()
    const g = new GateAwareQuestions(port, chain)
    expect(g.available()).toBe(true)
    const q = [{ id: 'c', question: 'q', options: [{ label: 'ok' }] }]
    const a = await g.ask(q, { agent: { id: W }, gate: 'G2' })
    expect(seenOpts[0]).toEqual({ gate: 'G2' }) // gate 原样下行给真实 UI
    expect(a).toEqual([{ id: 'c', selected: ['ok'], custom: 'x' }])
  })
})

describe('零成本扩展（AC-10.2）', () => {
  it('新增一个带 gate 的假弹框用例即可进链，且装饰器与链源码无需为此改动', async () => {
    // 「假用例」= 本次测试新造的一个 entry，生产代码里没有任何它的痕迹
    const { port } = queueUI([[{ id: 'fake', selected: ['yes'] }]])
    const { chain, pending } = chainWithStore()
    const g = new GateAwareQuestions(port, chain)
    await g.ask([{ id: 'fake', question: '某个新入口的确认' }], { agent: { id: 'w-new-entry' }, gate: 'G3' })
    expect(pending.peek('w-new-entry')!.gate).toBe('G3')

    // 机械判据：装饰器与链里**不得出现**针对具体入口的特判
    const src = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')
    for (const f of ['../src/adapters/GateAwareQuestions.ts', '../src/application/gate/GatePostChain.ts']) {
      expect(src(f)).not.toMatch(/reqboard_ask_confirm|reqboard_accept_sheet|reqboard_capture/)
    }
  })
})

describe('三条 pm 弹框路径各触发一次链', () => {
  it('AskConfirm（G1 确认需求文档）作答 → 登记一次，gate=G1', async () => {
    const h = makeHarness({
      requirements: [req({
        id: REQ_ID, status: 'brainstorming', sourceSessionId: W,
        // 落章需要该产物已登记（三问/确认门的语义：确认的是已产出的东西）
        artifacts: [{
          stage: 'brainstorming', kind: 'requirement',
          path: 'docs/requirements/REQ-000001/requirement.md',
          registeredAt: 1, registeredBy: { kind: 'agent', sessionId: W },
        }],
      })],
    })
    const { port, seenOpts } = queueUI([[{ id: 'confirm', selected: [DEFAULT_CONFIRM_OPTIONS[0]] }]])
    const { chain, pending } = chainWithStore()
    h.deps.questions = new GateAwareQuestions(port, chain)
    await askConfirm(h.deps, { target: 'artifact', kind: 'requirement', question: '确认？', advance: false }, { agent: { id: W } })
    expect(seenOpts[0]!.gate).toBe('G1')
    expect(chain.stats().enqueued).toBe(1)
    expect(pending.peek(W)!.gate).toBe('G1')
  })

  it('accept_sheet 逐项 + 最终归档确认 → 各登记一次，均为 G4', async () => {
    const sheet = {
      version: 1, generatedAt: 1, generatedBy: { kind: 'agent' as const, sessionId: W },
      items: [{ id: 'v1-1', source: { kind: 'requirement' } as const, criterion: '判据一', evidence: ['e'], status: 'pending' as const }],
    }
    const h = makeHarness({
      requirements: [req({ id: REQ_ID, status: 'accepting', sourceSessionId: W, verification: { sheet } as never })],
    })
    const { port, seenOpts } = queueUI([
      [{ id: 'v1-1', selected: [ACCEPT_ITEM_OPTIONS.pass] }],
      [{ id: 'final-pass', selected: [FINAL_PASS_LABEL] }],
    ])
    const { chain, pending } = chainWithStore()
    h.deps.questions = new GateAwareQuestions(port, chain)
    await acceptSheet(h.deps, {}, { agent: { id: W } })
    expect(seenOpts.map(o => o.gate)).toEqual(['G4', 'G4'])
    expect(chain.stats().enqueued).toBe(2)
    expect(pending.peek(W)!.gate).toBe('G4')
  })
})
