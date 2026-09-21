/**
 * REQ-9494f9 回归：催办消息必须是 **UserMessage 信封**，不是纯字符串。
 *
 * 复盘（2026-09-21，w-f8006463）：buildNudgeMessage 曾返回 `[...].join(NL)` 字符串，
 * watchResolution 直接 `agent.followup(string)`。字符串没有 id / source，于是——
 *   ① 第二次入箱被 inbox 去重拒绝：message "undefined" is already pending
 *   ② session-controller 的 Host 级 control stream 建基线读 message.source.kind 时抛
 *      TypeError，**所有浏览器窗口**的控制流一起失败（脏数据在持久化 event log，重启不恢复）。
 *
 * 本文件的 A3/A4 是一对：A3 断言好形状能通过"严格双重身"，A4 断言坏形状一定被它拒绝——
 * 没有 A4，A3 可能只是恒真（双重身太宽松就会悄悄失效）。
 */
import { describe, expect, it } from 'vitest'

import { buildNudgeMessage } from '../src/host.js'

const BASE = {
  eventId: '7f0819b1-0000-4000-8000-000000000000',
  title: '错误事件：x',
  attempt: 1,
  total: 3,
  actorWindow: 'w-6faac762',
  panel: '执行看板',
  plugin: 'dashboard-execution',
}

/**
 * 严格双重身：逐条复刻框架真实读取点，坏形状在此**必须**抛。
 *  - push：| dsh-agent-loop `inbox.mutate` \| 去重集合读 `message.id`（:194）；
 *  - queueItems：| dsh-api-session-controller `queueItemsFromInbox` \| 读 `message.source.kind`（:1162）。
 */
function strictInboxDouble() {
  const ids = new Set<string>()
  return {
    push(message: unknown): void {
      const id = (message as any)?.id
      if (typeof id !== 'string' || id.length === 0) {
        throw new TypeError('inbox 拒绝非消息对象：message.id=' + String(id))
      }
      if (ids.has(id)) throw new Error('message "' + id + '" is already pending')
      ids.add(id)
    },
    queueItems(message: unknown): { id: string; sourceKind: string } {
      const source = (message as any)?.source
      return { id: (message as any).id, sourceKind: source.kind }
    },
  }
}

describe('buildNudgeMessage 形状纪律（REQ-9494f9 / FR-1 FR-2）', () => {
  it('A1 返回 UserMessage 信封（不是字符串）', () => {
    const m: any = buildNudgeMessage(BASE)

    expect(typeof m).toBe('object')
    expect(m).not.toBeNull()
    expect(typeof m.id).toBe('string')
    expect(m.id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i)
    expect(m.role).toBe('user')
    expect(Array.isArray(m.content)).toBe(true)
    expect(m.content[0].type).toBe('text')
    expect(m.content[0].text).toContain('收单催办')
    expect(m.source.kind).toBe('plugin')
    expect(m.source.plugin).toBe('dashboard-execution')
  })

  it('A2 连续两次调用 id 不相等（对治 already pending）', () => {
    const a: any = buildNudgeMessage(BASE)
    const b: any = buildNudgeMessage({ ...BASE, attempt: 2 })

    expect(a.id).not.toBe(b.id)
  })

  it('A3 严格双重身：入箱去重与控制流基线读取都不抛错', () => {
    const inbox = strictInboxDouble()
    const first: any = buildNudgeMessage(BASE)
    const second: any = buildNudgeMessage({ ...BASE, attempt: 2 })

    expect(() => {
      inbox.push(first)
      inbox.push(second)
    }).not.toThrow()
    expect(inbox.queueItems(first).sourceKind).toBe('plugin')
  })

  it('A4 反例锁：字符串投递必须被同一双重身拒绝（证明 A3 不是恒真）', () => {
    const inbox = strictInboxDouble()

    expect(() => inbox.push('⏰ 收单催办（执行看板 · 第 1/3 次）')).toThrow(/inbox 拒绝非消息对象/)
    expect(() => inbox.queueItems('⏰ 收单催办（执行看板 · 第 1/3 次）')).toThrow(TypeError)
  })
})
