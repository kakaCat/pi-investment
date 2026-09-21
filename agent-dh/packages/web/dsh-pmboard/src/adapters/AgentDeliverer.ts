/**
 * 会话投递适配器（REQ-e3b6a0 t4 / FR-5）——**唯一**投递实现。
 *
 * 形状纪律（本文件存在的全部理由）：`ctx.agents` 是 **AgentRegistry**（只有 get/list/roots/…），
 * `followup` 在 **Agent 实例**上。故正确形状是：
 *
 *     agents.get(windowKey)?.followup(createUserMessage({ content, source }))
 *
 * 而 pmboard 两处历史写法 `agents.followup(id, msg)` 把 registry 当 agent 用——typeof 守卫恒 false，
 * 于是"状态转移注入"与"产物超时 30 分钟催办"自诞生起从未投递过（同一根因的三个受害者）。
 *
 * 为什么不 import `createUserMessage`：本包的依赖树**解析不到** `@deepseek-ai/dsh-llm`
 * （`NodeIsolationAdapter` 文件头记过同一坑）。而该 helper 的实现是
 * `deepFreeze(structuredClone({ ...input, role: "user", id: brandString(randomUUID()) }))`——
 * 结构复刻完全等价，且让 vitest 树不必解析框架包。消息 id 由注入的工厂生成（测试可固定）。
 *
 * @module dsh-pmboard/adapters/AgentDeliverer
 */
import { randomUUID } from 'node:crypto'
import { fmt } from '../domain/text/fmt.js'
import type { AgentDeliveryPort, DeliveryResult } from '../application/ports.js'

interface AgentsLike { get?: (id: string) => unknown }
interface AgentLike { followup?: (message: unknown) => void }

export interface AgentDelivererOptions {
  /** 消息 id 生成器（默认 randomUUID；测试注入固定值以保证可复现）。 */
  idFactory?: () => string
  /** 默认 plugin 署名（写进 `message.source.plugin`）。 */
  plugin?: string
}

/** 错误 → 一行可读文本（不吞类型信息）。 */
function reasonOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export class AgentDeliverer implements AgentDeliveryPort {
  private readonly resolveAgents: () => unknown
  private readonly idFactory: () => string
  private readonly plugin: string

  constructor(resolveAgents: () => unknown, options: AgentDelivererOptions = {}) {
    this.resolveAgents = resolveAgents
    this.idFactory = options.idFactory ?? ((): string => randomUUID())
    this.plugin = options.plugin ?? 'dsh-pmboard'
  }

  /** 三态全判、**永不抛**（调用方是结算点/HTTP 路由，异常冒泡会打断流水线）。 */
  deliver(windowKey: string, message: { text: string; plugin?: string }): DeliveryResult {
    const agents = this.resolveAgents() as AgentsLike | undefined
    if (typeof agents?.get !== "function") {
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
    if (typeof followup !== "function") {
      return { delivered: false, reason: 'agent 无 followup 投递能力' }
    }
    const payload = {
      id: this.idFactory(),
      role: 'user',
      content: [{ type: 'text', text: message.text }],
      source: { kind: 'plugin', plugin: message.plugin ?? this.plugin },
    }
    try {
      followup.call(agent, payload)
      return { delivered: true }
    } catch (error) {
      return { delivered: false, reason: fmt('投递失败：{err}', { err: reasonOf(error) }) }
    }
  }
}
