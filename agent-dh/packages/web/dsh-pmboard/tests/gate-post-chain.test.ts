/**
 * 闸门后置链框架测试（REQ-e3b6a0 t3 / FR-2 / AC-1.2 · AC-2.1 · AC-2.2）。
 *
 * 用**替身 handler** 测框架本身（顺序/短路/降级/幂等/开关/登记表语义），
 * 真实 handler（H2 压缩、H3 注入…）由后续任务各自单测。
 *
 * @module dsh-pmboard/tests/gate-post-chain
 */
import { describe, it, expect } from 'vitest'
import {
  createGatePostChain,
  HANDLER_ORDER,
  type GateHandler,
  type HandlerOutcome,
} from '../src/application/gate/GatePostChain.js'
import { createPendingGateStore } from '../src/application/gate/PendingGate.js'
import type { ConfirmContext } from '../src/domain/gate/GateSpec.js'

function ctx(over: Partial<ConfirmContext> = {}): ConfirmContext {
  return {
    windowKey: 'w-test', gate: 'G1', from: 'brainstorming', to: 'design',
    requirementId: 'REQ-abc123', verdict: 'affirmative', answers: [], decidedAt: 1000,
    ...over,
  }
}

/** 记录调用顺序的替身 handler。 */
function spy(
  name: GateHandler['name'],
  order: string[],
  outcome: HandlerOutcome = { kind: 'continue' },
  opts: { throws?: boolean } = {},
): GateHandler & { calls: number } {
  const h = {
    name,
    calls: 0,
    async run() {
      h.calls += 1
      order.push(name)
      if (opts.throws === true) throw new Error(name + ' boom')
      return outcome
    },
  }
  return h as unknown as GateHandler & { calls: number }
}

describe('闸门后置链框架', () => {
  it('按 HANDLER_ORDER 执行；H2 skip 不阻断后续（AC-2.1）', async () => {
    const order: string[] = []
    const handlers: GateHandler[] = [
      spy('h5-audit', order),
      spy('h2-compact', order, { kind: 'skip', code: 'doc_missing', reason: '输入包不自足' }),
      spy('h1-advance', order),
      spy('h4-resume', order),
      spy('h3-inject', order),
    ]
    const chain = createGatePostChain({ handlers, enabled: true })
    chain.enqueue(ctx())
    const summary = await chain.runPending('w-test')
    expect(order).toEqual([...HANDLER_ORDER])
    expect(summary.ran).toBe(true)
    expect(summary.steps).toHaveLength(5)
    expect(summary.degraded).toBe(0)
  })

  it('handler 抛错就地降级：不冒泡、不阻断后续（AC-2.2）', async () => {
    const order: string[] = []
    const handlers: GateHandler[] = [
      spy('h1-advance', order),
      spy('h2-compact', order, { kind: 'continue' }, { throws: true }),
      spy('h3-inject', order),
      spy('h4-resume', order, { kind: 'continue' }, { throws: true }),
      spy('h5-audit', order),
    ]
    const chain = createGatePostChain({ handlers, enabled: true })
    chain.enqueue(ctx())
    const summary = await chain.runPending('w-test')
    expect(order).toEqual([...HANDLER_ORDER])
    expect(summary.ran).toBe(true)
    expect(summary.degraded).toBe(2)
    expect(summary.steps[1]!.outcome).toMatchObject({ kind: 'degraded', code: 'handler_threw' })
    expect(chain.stats().handlerThrew).toBe(2)
  })

  it('幂等：同一 (windowKey, gate, decidedAt) 只跑一轮（AC-1.2）', async () => {
    const order: string[] = []
    const h1 = spy('h1-advance', order)
    const chain = createGatePostChain({ handlers: [h1], enabled: true })
    chain.enqueue(ctx())
    const first = await chain.runPending('w-test')
    chain.enqueue(ctx())
    const second = await chain.runPending('w-test')
    expect(first.ran).toBe(true)
    expect(second).toMatchObject({ ran: false, reason: 'duplicate' })
    expect(h1.calls).toBe(1)
    expect(chain.stats().deduped).toBe(1)
  })

  it('开关关：enqueue 不登记、runPending 不执行（Phase B 计数为 0）', async () => {
    const order: string[] = []
    const handlers = [spy('h1-advance', order)] as GateHandler[]
    const chain = createGatePostChain({ handlers, enabled: false })
    chain.enqueue(ctx())
    const summary = await chain.runPending('w-test')
    expect(summary).toMatchObject({ ran: false, reason: 'disabled' })
    expect(order).toEqual([])
    expect(chain.stats().executed).toBe(0)
    expect(chain.stats().enqueued).toBe(0)
    expect(chain.stats().disabled).toBe(2)
  })

  it('无待处理 → no-pending；同窗口重复登记只保留最新一条', async () => {
    const store = createPendingGateStore()
    const seen: string[] = []
    const handlers: GateHandler[] = [{
      name: 'h1-advance',
      async run(input) {
        seen.push(String(input.ctx.decidedAt))
        return { kind: 'continue' }
      },
    }]
    const chain = createGatePostChain({ handlers, enabled: true, pending: store })
    expect(await chain.runPending('w-x')).toMatchObject({ ran: false, reason: 'no-pending' })
    chain.enqueue(ctx({ windowKey: 'w-x', decidedAt: 1 }))
    chain.enqueue(ctx({ windowKey: 'w-x', decidedAt: 2 }))
    expect(store.size()).toBe(1)
    const s = await chain.runPending('w-x')
    expect(s.ran).toBe(true)
    expect(seen).toEqual(['2'])
    expect(await chain.runPending('w-x')).toMatchObject({ ran: false, reason: 'no-pending' })
  })

  it('onStep 每步回调一次；回调抛错不中断链', async () => {
    const order: string[] = []
    const steps: string[] = []
    const handlers: GateHandler[] = [
      spy('h1-advance', order), spy('h2-compact', order),
    ]
    const chain = createGatePostChain({
      handlers, enabled: true,
      onStep: (step) => { steps.push(step.name); throw new Error('留痕失败') },
    })
    chain.enqueue(ctx())
    const summary = await chain.runPending('w-test')
    expect(summary.ran).toBe(true)
    expect(steps).toEqual(['h1-advance', 'h2-compact'])
    expect(order).toEqual(['h1-advance', 'h2-compact'])
  })

  it('同名 handler 只跑一次（防重复注册）', async () => {
    const order: string[] = []
    const handlers: GateHandler[] = [spy('h1-advance', order), spy('h1-advance', order)]
    const chain = createGatePostChain({ handlers, enabled: true })
    chain.enqueue(ctx())
    await chain.runPending('w-test')
    expect(order).toEqual(['h1-advance'])
  })
})
