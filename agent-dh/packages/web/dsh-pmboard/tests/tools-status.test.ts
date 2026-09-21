/**
 * reqboard_status 输出契约：本窗口可自行推进的目标（next_actions）。
 * 用户反馈「agent 自己不能推进吗」——窗口必须能从工具输出里直接看到可推进项。
 */
import { describe, it, expect } from 'vitest'
import { defineStatusTool } from './helpers/tool-deps.js'
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
  it('brainstorming → design 已入人工门（五门裁定），agent 仅可退回 draft', async () => {
    const out = await run('brainstorming')
    // 2026-09-14 五门裁定：需求文档确认 brainstorming>design 是人工确认门，
    // agent 的 next_actions 不再含 design（人确认需求文档后由看板推进）
    expect(out.next_actions).toEqual(['draft'])
    expect(out.note).toContain('reqboard_move')
  })

  it('draft → 提交评审；implementing → 进验收', async () => {
    expect((await run('draft')).next_actions).toEqual(['brainstorming'])
    expect((await run('implementing')).next_actions).toEqual(['accepting'])
  })

  it('终态与未绑定窗口：无 next_actions', async () => {
    expect((await run('archived')).next_actions).toEqual([])
  })
})
