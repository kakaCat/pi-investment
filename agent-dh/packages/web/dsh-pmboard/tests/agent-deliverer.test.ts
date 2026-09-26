/**
 * AgentDeliverer 测试（REQ-e3b6a0 t4 / FR-5 / AC-5.1 · AC-5.2）。
 *
 * 三态全判：在线 → delivered=true 且消息形状正确；离线 / 无 followup / 抛错 → delivered=false 且不抛。
 * 本文件同时是**形状纪律的执行者**：若有人回退成把 AgentRegistry 当 Agent 用（`agents.followup(id,msg)`），
 * 生产代码那条会先被 grep 判据拦下，这里再锁住正确形状的语义。
 *
 * @module dsh-pmboard/tests/agent-deliverer
 */
import { describe, it, expect } from 'vitest'
import { AgentDeliverer } from '../src/adapters/AgentDeliverer.js'

const ID = 'msg-fixed-1'
const opts = { idFactory: () => ID, plugin: 'dsh-pmboard' }

/** 造一个只带 get 的假 registry（与 ctx.agents 的形状一致：只有 get/list/roots…，没有 followup）。 */
function registryOf(agent: unknown): () => unknown {
  return () => ({ get: () => agent })
}

describe('AgentDeliverer：投递形状与三态', () => {
  it('在线 → delivered=true，且 followup 收到 createUserMessage 形状的消息（AC-5.1）', () => {
    const sent: unknown[] = []
    const agent = { followup(message: unknown) { sent.push(message) } }
    const deliverer = new AgentDeliverer(registryOf(agent), opts)
    const r = deliverer.deliver('w-abc', { text: '节点已推进，请继续' })
    expect(r.delivered).toBe(true)
    expect(sent).toHaveLength(1)
    expect(sent[0]).toMatchObject({
      id: ID,
      role: 'user',
      content: [{ type: 'text', text: '节点已推进，请继续' }],
      source: { kind: 'plugin', plugin: 'dsh-pmboard' },
    })
  })

  it('离线（get 返回 undefined）→ delivered=false，reason 指明不在线，不抛（AC-5.2）', () => {
    const deliverer = new AgentDeliverer(registryOf(undefined), opts)
    const r = deliverer.deliver('w-gone', { text: 'x' })
    expect(r.delivered).toBe(false)
    expect(r.reason).toContain('不在线')
  })

  it('agent 无 followup → delivered=false，不抛', () => {
    const deliverer = new AgentDeliverer(registryOf({ id: 'w' }), opts)
    const r = deliverer.deliver('w-nofu', { text: 'x' })
    expect(r.delivered).toBe(false)
    expect(r.reason).toContain('followup')
  })

  it('followup 抛错 → delivered=false，不抛', () => {
    const agent = { followup() { throw new Error('boom') } }
    const deliverer = new AgentDeliverer(registryOf(agent), opts)
    const r = deliverer.deliver('w-boom', { text: 'x' })
    expect(r.delivered).toBe(false)
    expect(r.reason).toContain('boom')
  })

  it('agents 服务不可得 → delivered=false，不抛', () => {
    const deliverer = new AgentDeliverer(() => undefined, opts)
    expect(deliverer.deliver('w', { text: 'x' })).toMatchObject({ delivered: false })
    const broken = new AgentDeliverer(() => ({}), opts)
    expect(broken.deliver('w', { text: 'x' }).delivered).toBe(false)
  })

  it('agents.get 自身抛错 → delivered=false，不抛', () => {
    const deliverer = new AgentDeliverer(() => ({ get() { throw new Error('registry down') } }), opts)
    const r = deliverer.deliver('w', { text: 'x' })
    expect(r.delivered).toBe(false)
    expect(r.reason).toContain('registry down')
  })

  it('消息 plugin 署名可被调用方覆盖', () => {
    const sent: Array<{ source?: { plugin?: string } }> = []
    const agent = { followup(m: unknown) { sent.push(m as { source?: { plugin?: string } }) } }
    const deliverer = new AgentDeliverer(registryOf(agent), opts)
    deliverer.deliver('w', { text: 'x', plugin: 'dsh-pmboard-board' })
    expect(sent[0]!.source!.plugin).toBe('dsh-pmboard-board')
  })
})

describe('AgentDeliverer：Dive 回合消息（T-3 / FR-10）', () => {
  it('createRoundMessage → 带 source:{kind:dive,requirementId,revision,round} 且不投递', () => {
    const deliverer = new AgentDeliverer(() => undefined, opts)
    const built = deliverer.createRoundMessage({ requirementId: 'REQ-t', revision: 7, round: 2, text: '继续' })
    expect(built.messageId).toBe(ID)
    expect(built.message).toMatchObject({
      id: ID, role: 'user', content: [{ type: 'text', text: '继续' }],
      source: { kind: 'dive', requirementId: 'REQ-t', revision: 7, round: 2 },
    })
  })

  it('deliverMessage → 原样投递（保留 source）；离线/不可得 → delivered=false 且不抛', () => {
    const sent: unknown[] = []
    const agent = { followup(m: unknown) { sent.push(m) } }
    const deliverer = new AgentDeliverer(registryOf(agent), opts)
    const built = deliverer.createRoundMessage({ requirementId: 'REQ-t', revision: 1, round: 1, text: 'r' })
    expect(deliverer.deliverMessage('w', built.message).delivered).toBe(true)
    expect(sent[0]).toBe(built.message)
    const offline = new AgentDeliverer(() => undefined, opts)
    const r = offline.deliverMessage('w', built.message)
    expect(r.delivered).toBe(false)
    expect(r.reason).toContain('agents 服务不可得')
  })
})
