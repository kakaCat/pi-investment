/**
 * reqboard_status 输出契约：本窗口可自行推进的目标（next_actions）。
 * 用户反馈「agent 自己不能推进吗」——窗口必须能从工具输出里直接看到可推进项。
 */
import { describe, it, expect } from 'vitest'
import { defineStatusTool } from '../src/host/agent-tools.js'
import { emptyLedger, type ReqboardLedger, type RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-abc-123'

function ledgerWith(status: RequirementRecord['status']): ReqboardLedger {
  const req = {
    id: 'REQ-abc123', title: '需求', description: '', status, blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
  } as RequirementRecord
  return { ...emptyLedger(), requirements: [req] }
}

async function run(status: RequirementRecord['status']) {
  const ledger = ledgerWith(status)
  const deps = {
    store: { read: async (fn: (l: ReqboardLedger) => unknown) => fn(ledger), snapshot: () => ledger },
    now: () => 1,
  } as never
  const tool = defineStatusTool(deps) as unknown as { execute: (a: unknown, e: unknown) => Promise<any> }
  return tool.execute({}, { agent: { id: W } })
}

describe('reqboard_status.next_actions（窗口可自行推进的动作）', () => {
  it('reviewing → 可自行推进到 decomposing / 退回 draft（取消不在列）', async () => {
    const out = await run('reviewing')
    expect(out.next_actions).toEqual(['decomposing', 'draft'])
    expect(out.note).toContain('reqboard_move')
  })

  it('draft → 提交评审；implementing → 进验收', async () => {
    expect((await run('draft')).next_actions).toEqual(['reviewing'])
    expect((await run('implementing')).next_actions).toEqual(['accepting'])
  })

  it('终态与未绑定窗口：无 next_actions', async () => {
    expect((await run('archived')).next_actions).toEqual([])
  })
})
