/**
 * 文字确认核验单测（REQ-2e9473 t10，三通道③）。
 * 覆盖：evidence 命中真实用户消息原文 → 落章；编造/找不到原文 → REQBOARD_EVIDENCE_FAKE；
 * 超窗（>60min）→ 拒；缓冲未注入 → 降级放行但注明；短消息（<4 字符）不作证。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { defineConfirmArtifactTool } from './helpers/tool-deps.js'
import { recordRecentUserMsg, CONFIRM_EVIDENCE_WINDOW_MS, type RecentUserMsg } from '../src/adapters/SessionProbeAdapter.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let buf: Map<string, RecentUserMsg[]>
let nowTs = 1_000_000_000_000

function makeTool(withBuf = true) {
  const deps = {
    store,
    now: () => nowTs,
    ...(withBuf ? { recentUserMsgs: buf } : {}),
  } as never
  return defineConfirmArtifactTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
}

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-evidence-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  buf = new Map()
  nowTs = 1_000_000_000_000
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seed(): Promise<void> {
  const r = {
    id: 'REQ-abc123', title: '看板需求', description: '', status: 'brainstorming', blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [],
    artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1 }],
  } as unknown as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown) =>
  tool.execute(args, { agent: { id: W } })

const ARGS = (evidence: string) => ({ target: 'artifact', kind: 'requirement', evidence })

describe('confirm_artifact 文字确认核验', () => {
  it('evidence 命中真实用户消息原文 → 落章成功且标 evidence_verified', async () => {
    await seed()
    recordRecentUserMsg(buf, W, '确认，进入设计吧', nowTs - 60_000)
    const out = await run(makeTool(), ARGS('用户在对话中回复"确认，进入设计吧"'))
    expect(out.success).toBe(true)
    expect(out.evidence_verified).toBe(true)
    expect(store.snapshot().requirements[0].artifacts![0].confirmedAt).toBeDefined()
  })

  it('编造 evidence（无对应消息）→ REQBOARD_EVIDENCE_FAKE', async () => {
    await seed()
    recordRecentUserMsg(buf, W, '今天天气怎么样', nowTs - 60_000)
    await expect(run(makeTool(), ARGS('用户说"我完全同意这个方案并批准一切"'))).rejects.toThrow(/REQBOARD_EVIDENCE_FAKE/)
    expect(store.snapshot().requirements[0].artifacts![0].confirmedAt).toBeUndefined()
  })

  it('缓冲为空（时间窗内无消息）→ REQBOARD_EVIDENCE_FAKE', async () => {
    await seed()
    await expect(run(makeTool(), ARGS('用户同意了'))).rejects.toThrow(/REQBOARD_EVIDENCE_FAKE/)
  })

  it('消息超出 60min 时间窗 → 拒', async () => {
    await seed()
    recordRecentUserMsg(buf, W, '确认进入设计', nowTs - CONFIRM_EVIDENCE_WINDOW_MS - 1000)
    await expect(run(makeTool(), ARGS('用户回复"确认进入设计"'))).rejects.toThrow(/REQBOARD_EVIDENCE_FAKE/)
  })

  it('过短消息（<4 字符）不作证', async () => {
    await seed()
    recordRecentUserMsg(buf, W, '嗯', nowTs - 1000)
    await expect(run(makeTool(), ARGS('用户回了"嗯"表示同意'))).rejects.toThrow(/REQBOARD_EVIDENCE_FAKE/)
  })

  it('缓冲未注入 → 降级放行但 note 注明核验未启用', async () => {
    await seed()
    const out = await run(makeTool(false), ARGS('用户同意了'))
    expect(out.success).toBe(true)
    expect(out.evidence_verified).toBeUndefined()
    expect(out.note).toMatch(/核验未启用/)
  })
})
