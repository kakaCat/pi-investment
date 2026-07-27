/**
 * 会话回放加工：事件流 → 回合结构（纯函数）
 * 按 user_message 切分回合；回合内挂 tool_call/error；assistant_reply 收尾
 */
import type { SessionEvent } from '@/types'

export interface ToolCallItem {
  toolName: string
  durationMs: number
  success: boolean
  error?: string
  seq: number
}

export interface Turn {
  userText: string | null
  userTime: string | null
  toolCalls: ToolCallItem[]
  errors: Array<{ stage: string; message: string; time: string }>
  reply: string | null
  replyTime: string | null
}

export function groupEventsToTurns(events: SessionEvent[]): Turn[] {
  const sorted = [...events].sort((a, b) => a.seq - b.seq)
  const turns: Turn[] = []
  let current: Turn | null = null

  const ensureTurn = (): Turn => {
    if (!current) {
      current = { userText: null, userTime: null, toolCalls: [], errors: [], reply: null, replyTime: null }
      turns.push(current)
    }
    return current
  }

  for (const e of sorted) {
    switch (e.event_type) {
      case 'user_message':
        current = {
          userText: e.payload.text ?? '',
          userTime: e.created_at,
          toolCalls: [], errors: [], reply: null, replyTime: null,
        }
        turns.push(current)
        break
      case 'tool_call':
        ensureTurn().toolCalls.push({
          toolName: e.payload.toolName ?? 'unknown',
          durationMs: e.payload.durationMs ?? 0,
          success: !!e.payload.success,
          error: e.payload.error,
          seq: e.seq,
        })
        break
      case 'assistant_reply': {
        const turn = ensureTurn()
        turn.reply = e.payload.text ?? ''
        turn.replyTime = e.created_at
        break
      }
      case 'error':
        ensureTurn().errors.push({
          stage: e.payload.stage ?? '',
          message: e.payload.message ?? '',
          time: e.created_at,
        })
        break
      default:
        // session_start / session_idle / legacy_note 不进回合
        break
    }
  }
  return turns
}
