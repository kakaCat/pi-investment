/**
 * 会话投递适配器（REQ-e3b6a0 t4 / FR-5）——**Dive专用投递实现**。
 *
 * 【2026-XX-XX 全面Dive化】
 * 移除 deliver() 方法（旧的followup → inbox路径）。
 * 现在只保留 Dive 专用的 deliverMessage + createRoundMessage。
 *
 * @module dsh-pmboard/adapters/AgentDeliverer
 */
import type { DiveRoundDeliveryPort, AgentDeliveryPort } from '../application/ports.js'
import { fmt } from '../domain/text/fmt.js'

type MessageIdFactory = () => string

interface AgentsLike { get?: (id: string) => unknown }
interface AgentLike { followup?: (msg: unknown) => void }

function reasonOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export class AgentDeliverer implements AgentDeliveryPort, DiveRoundDeliveryPort {
  private readonly resolveAgents: () => unknown
  private readonly idFactory: MessageIdFactory
  private readonly plugin: string

  constructor(resolveAgents: () => unknown, idFactory: MessageIdFactory, plugin: string) {
    this.resolveAgents = resolveAgents
    this.idFactory = idFactory
    this.plugin = plugin
  }

  /** Dive 专用：创建回合消息（带 round 元数据和 source.kind='dive'）。 */
  createRoundMessage(params: {
    requirementId: string
    revision: number
    round: number
    text: string
  }): { message: unknown; messageId: string } {
    const messageId = this.idFactory()
    const message = {
      id: messageId,
      role: 'user',
      content: [{ type: 'text', text: params.text }],
      source: {
        kind: 'dive',
        plugin: this.plugin,
        requirementId: params.requirementId,
        revision: params.revision,
        round: params.round,
      },
    }
    return { message, messageId }
  }

  /** Dive 专用：投递回合消息（直接调用 agent.followup，但消息带 source.kind='dive'）。 */
  deliverMessage(windowKey: string, message: unknown): { delivered: boolean; reason?: string } {
    const agents = this.resolveAgents() as AgentsLike | undefined
    if (typeof agents?.get !== 'function') {
      return { delivered: false, reason: 'agents 服务不可得（未装配 ctx.agents）' }
    }
    let agent: unknown
    try {
      agent = agents.get(windowKey)
    } catch (error) {
      return { delivered: false, reason: fmt('agents.get 抛错：{err}', { err: reasonOf(error) }) }
    }
    if (agent === undefined || agent === null) {
      return { delivered: false, reason: fmt('窗口 {w} 不在线', { w: windowKey }) }
    }
    const followup = (agent as AgentLike).followup
    if (typeof followup !== 'function') {
      return { delivered: false, reason: 'agent 无 followup 投递能力' }
    }
    try {
      followup.call(agent, message)
      return { delivered: true }
    } catch (error) {
      return { delivered: false, reason: fmt('投递失败：{err}', { err: reasonOf(error) }) }
    }
  }
}