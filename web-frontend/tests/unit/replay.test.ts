import { describe, it, expect } from 'vitest'
import { groupEventsToTurns } from '@/services/agentSession/replay'
import type { SessionEvent } from '@/types'

const ev = (seq: number, event_type: string, payload: any = {}): SessionEvent => ({
  seq, event_type, payload, created_at: `2026-07-26T10:00:0${seq}Z`,
})

describe('groupEventsToTurns', () => {
  it('按 user_message 切分回合，工具与错误挂进回合，assistant_reply 收尾', () => {
    const events = [
      ev(1, 'session_start', { channel: 'wake', peerId: 'e2e' }),
      ev(2, 'user_message', { text: '分析一下', messageId: 'm1' }),
      ev(3, 'tool_call', { toolName: 'a', durationMs: 100, success: true }),
      ev(4, 'tool_call', { toolName: 'b', durationMs: 300, success: false, error: 'timeout' }),
      ev(5, 'assistant_reply', { text: '结论', replyLength: 2 }),
      ev(6, 'user_message', { text: '再来一次', messageId: 'm2' }),
      ev(7, 'error', { stage: 'prompt', message: 'boom' }),
    ]
    const turns = groupEventsToTurns(events)
    expect(turns).toHaveLength(2)
    expect(turns[0].userText).toBe('分析一下')
    expect(turns[0].toolCalls).toHaveLength(2)
    expect(turns[0].reply).toBe('结论')
    expect(turns[1].userText).toBe('再来一次')
    expect(turns[1].errors).toHaveLength(1)
    expect(turns[1].reply).toBeNull()
  })

  it('session_start 不产生回合', () => {
    const turns = groupEventsToTurns([ev(1, 'session_start', { channel: 'wake' })])
    expect(turns).toHaveLength(0)
  })

  it('空事件流返回空数组', () => {
    expect(groupEventsToTurns([])).toEqual([])
  })

  it('乱序 seq 先排序再分组', () => {
    const events = [
      ev(5, 'assistant_reply', { text: 'r', replyLength: 1 }),
      ev(2, 'user_message', { text: 'q', messageId: 'm' }),
      ev(3, 'tool_call', { toolName: 'a', durationMs: 1, success: true }),
    ]
    const turns = groupEventsToTurns(events)
    expect(turns[0].userText).toBe('q')
    expect(turns[0].toolCalls).toHaveLength(1)
    expect(turns[0].reply).toBe('r')
  })

  it('没有 user_message 的孤儿工具调用归入 turn 0（userText 为空）', () => {
    const turns = groupEventsToTurns([
      ev(1, 'tool_call', { toolName: 'a', durationMs: 1, success: true }),
    ])
    expect(turns).toHaveLength(1)
    expect(turns[0].userText).toBeNull()
    expect(turns[0].toolCalls).toHaveLength(1)
  })
})
