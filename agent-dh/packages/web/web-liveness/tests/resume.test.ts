/**
 * resume.ts 单测 —— 快照口径 / 死信分流 / 续跑消息。
 */
import { describe, expect, it } from 'vitest'
import {
  RESUME_ENTRY_TTL_MS,
  partitionResumeEntries,
  renderResumeMessage,
  selectBusyAgentIds,
} from '../src/resume.js'

describe('selectBusyAgentIds（快照口径）', () => {
  it('只挑 running 的窗口', () => {
    const agents = [
      { id: 'w1', status: 'running' },
      { id: 'w2', status: 'idle' },
      { id: 'w3', status: 'running' },
    ]
    expect(selectBusyAgentIds(agents)).toEqual(['w1', 'w3'])
  })

  it('没有窗口在跑 → 空清单', () => {
    expect(selectBusyAgentIds([{ id: 'w1', status: 'idle' }])).toEqual([])
    expect(selectBusyAgentIds([])).toEqual([])
  })

  it('id 统一转字符串', () => {
    expect(selectBusyAgentIds([{ id: 42 as unknown, status: 'running' }])).toEqual(['42'])
  })
})

describe('partitionResumeEntries（死信分流）', () => {
  const now = 1_000_000_000_000
  const fresh = { agentId: 'w1', status: 'running', at: now - 60_000 }
  const stale = { agentId: 'w2', status: 'running', at: now - RESUME_ENTRY_TTL_MS - 1 }

  it('未过期 → active；过期 → expired', () => {
    const { active, expired } = partitionResumeEntries([fresh, stale], now)
    expect(active).toEqual([fresh])
    expect(expired).toEqual([stale])
  })

  it('恰好到 TTL 边界 → 过期', () => {
    const edge = { agentId: 'w3', status: 'running', at: now - RESUME_ENTRY_TTL_MS }
    expect(partitionResumeEntries([edge], now).active).toEqual([])
  })

  it('坏条目（缺 agentId / at 非法）按死信处理，不阻塞其余', () => {
    const bad1 = { status: 'running', at: now } as any
    const bad2 = { agentId: 'w4', status: 'running', at: NaN }
    const { active, expired } = partitionResumeEntries([bad1, bad2, fresh], now)
    expect(active).toEqual([fresh])
    expect(expired).toHaveLength(2)
  })

  it('空/缺省输入 → 双空', () => {
    expect(partitionResumeEntries(undefined, now)).toEqual({ active: [], expired: [] })
    expect(partitionResumeEntries([], now)).toEqual({ active: [], expired: [] })
  })
})

describe('renderResumeMessage（续跑措辞）', () => {
  it('带原因、注明非用户消息、给出行动指引', () => {
    const msg = renderResumeMessage('页面异常自救')
    expect(msg).toContain('web-liveness')
    expect(msg).toContain('不是用户消息')
    expect(msg).toContain('页面异常自救')
    expect(msg).toContain('继续未完成的部分')
  })
})
