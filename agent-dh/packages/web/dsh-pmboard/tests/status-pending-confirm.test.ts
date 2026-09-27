// serves: FR-4
/**
 * reqboard_status.pending_confirms 投影（REQ-260927123256-196b t3 · serves: FR-4 / I-2）。
 *
 * 锁三件事：
 *   · 有挂起 → 列出该 ticket，且 blocked_tools / recovery 与守卫同源；
 *   · 无挂起 → 空数组（不 omit，形状稳定）；
 *   · 台账已落章（人走看板/证据通道作答）→ 陈旧记录不列（否则守卫死锁，TC-9）。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { SessionProbeAdapter } from '../src/adapters/SessionProbeAdapter.js'
import { RandomIdFactory } from '../src/adapters/RandomIdFactory.js'
import { UserQuestionsAdapter } from '../src/adapters/UserQuestionsAdapter.js'
import { PendingConfirmRegistry } from '../src/adapters/PendingConfirmRegistry.js'
import { defineStatusTool } from '../src/tools/index.js'
import type { UseCaseDeps } from '../src/application/ports.js'
import type { RequirementRecord, StageArtifact } from '../src/shared/protocol.js'

const W = 'session-status-pending-001'
let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-status-pending-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function makeDeps(): UseCaseDeps & { pendingConfirms: PendingConfirmRegistry } {
  const now = (): number => Date.now()
  return {
    repo: store,
    docs: new FileDocRepository({ workspaceRoot: dir }),
    clock: { now },
    ids: new RandomIdFactory(),
    session: new SessionProbeAdapter({}),
    questions: new UserQuestionsAdapter(() => ({ ask: async () => ({ answers: [] }) })),
    doneThrottleMs: 0,
    pendingConfirms: new PendingConfirmRegistry({ now }),
  } as unknown as UseCaseDeps & { pendingConfirms: PendingConfirmRegistry }
}

async function seedArtifact(confirmedAt?: number): Promise<void> {
  // 需求文档真实落盘：QueryState 的 RTM/追溯链会异步读它，缺文件会产生未捕获 rejection 噪声。
  mkdirSync(join(dir, 'docs/requirements/REQ-st01'), { recursive: true })
  writeFileSync(join(dir, 'docs/requirements/REQ-st01/requirement.md'), '# 挂起投影\n')
  const r = {
    id: 'REQ-st01', title: '挂起投影', description: '', status: 'brainstorming', blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    artifacts: [{
      stage: 'brainstorming', kind: 'requirement',
      path: 'docs/requirements/REQ-st01/requirement.md', registeredAt: 1,
      ...(confirmedAt === undefined ? {} : { confirmedAt }),
    } as StageArtifact],
  } as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

const exec = { agent: { id: W } }

describe('reqboard_status.pending_confirms（FR-4 / I-2）', () => {
  it('无挂起 → 空数组（形状稳定）', async () => {
    await seedArtifact()
    const out = await (defineStatusTool(makeDeps()) as any).execute({}, exec)
    expect(out.pending_confirms).toEqual([])
  })

  it('有挂起 → 逐字段投影（ticket/requirement_id/target/created_at/interrupted/blocked_tools/recovery）', async () => {
    await seedArtifact()
    const deps = makeDeps()
    const rec = deps.pendingConfirms.register({
      windowKey: W, requirementId: 'REQ-st01', target: 'artifact', kind: 'requirement',
    })
    const out = await (defineStatusTool(deps) as any).execute({}, exec)
    expect(out.pending_confirms).toHaveLength(1)
    const p = out.pending_confirms[0]
    expect(p.ticket).toBe(rec.ticket)
    expect(p.requirement_id).toBe('REQ-st01')
    expect(p.target).toBe('artifact')
    expect(p.kind).toBe('requirement')
    expect(typeof p.created_at).toBe('number')
    expect(p.interrupted).toBe(false)
    expect(p.blocked_tools).toEqual(['reqboard_submit', 'reqboard_decompose', 'reqboard_move', 'reqboard_task_move'])
    expect(p.recovery).toContain('reqboard_confirm_receipt')
    expect(p.recovery).toContain('看板')
  })

  it('被中止记录 → interrupted=true', async () => {
    await seedArtifact()
    const deps = makeDeps()
    const rec = deps.pendingConfirms.register({ windowKey: W, requirementId: 'REQ-st01', target: 'plan' })
    deps.pendingConfirms.markInterrupted(rec.ticket)
    const out = await (defineStatusTool(deps) as any).execute({}, exec)
    expect(out.pending_confirms[0].interrupted).toBe(true)
    expect(out.pending_confirms[0].target).toBe('plan')
  })

  it('TC-9 台账已落章 → 陈旧记录不列（守卫不死锁）', async () => {
    await seedArtifact(1)
    const deps = makeDeps()
    deps.pendingConfirms.register({
      windowKey: W, requirementId: 'REQ-st01', target: 'artifact', kind: 'requirement',
    })
    const out = await (defineStatusTool(deps) as any).execute({}, exec)
    expect(out.pending_confirms).toEqual([])
  })
})
