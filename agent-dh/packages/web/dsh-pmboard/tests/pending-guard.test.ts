/**
 * 挂起确认判定口径单点（REQ-260927123256-196b t-f8ed18 · serves: FR-4）。
 *
 * 锁三件事，别退化：
 *   - `targetConfirmedInLedger` 是「台账是否已落章」的**唯一**判定处（plan=approvedAt /
 *     artifact=该 kind 成组 confirmedAt）——守卫与回执共用同一份口径；
 *   - `markInterrupted` 幂等（只写首次），未知 ticket 返回 undefined 且不抛；
 *   - 过期基准 = `interruptedAt ?? createdAt`：中止记录再获一个完整 TTL，不因登记早而提前失效。
 */
import { describe, it, expect } from 'vitest'
import { PendingConfirmRegistry } from '../src/adapters/PendingConfirmRegistry.js'
import {
  PENDING_CONFIRM_BLOCKED_TOOLS,
  PENDING_CONFIRM_RECOVERY,
  livePendingConfirm,
  pendingConfirmRejectMessage,
  targetConfirmedInLedger,
} from '../src/application/internal/pending-guard.js'
import type { PendingConfirmation, RequirementRecord } from '../src/shared/protocol.js'
import type { UseCaseDeps } from '../src/application/ports.js'

const W = 'session-w-001'

/** 只给判定用到的字段（targetConfirmedInLedger 只读 plan / artifacts）。 */
function reqOf(id: string, patch: Partial<RequirementRecord> = {}): RequirementRecord {
  return { id, title: id, description: '', status: 'design', blocked: false, comments: [], version: 1, createdAt: 0, updatedAt: 0, ...patch } as unknown as RequirementRecord
}

function depsOf(registry: PendingConfirmRegistry, requirements: RequirementRecord[]): UseCaseDeps {
  const ledger = { schemaVersion: 1, revision: 0, requirements, tasks: [], triages: [] }
  return { pendingConfirms: registry, repo: { snapshot: () => ledger } } as unknown as UseCaseDeps
}

function rec(overrides: Partial<PendingConfirmation> = {}): PendingConfirmation {
  return {
    ticket: 'pc-000001',
    windowKey: W,
    requirementId: 'REQ-x',
    target: 'artifact',
    kind: 'requirement',
    createdAt: 0,
    ...overrides,
  }
}

describe('targetConfirmedInLedger：台账落章判定单点（FR-4）', () => {
  it('target=plan：approvedAt 已写 → true；未批准 → false', () => {
    expect(targetConfirmedInLedger(reqOf('REQ-x', { plan: { approvedAt: 1 } as never }), rec({ target: 'plan' }))).toBe(true)
    expect(targetConfirmedInLedger(reqOf('REQ-x', { plan: {} as never }), rec({ target: 'plan' }))).toBe(false)
    expect(targetConfirmedInLedger(reqOf('REQ-x'), rec({ target: 'plan' }))).toBe(false)
  })

  it('target=artifact：该 kind 成组 confirmedAt 已写 → true；缺一 / 无该 kind → false', () => {
    const stamped = reqOf('REQ-x', { artifacts: [{ kind: 'requirement', confirmedAt: 1 }] as never })
    expect(targetConfirmedInLedger(stamped, rec())).toBe(true)
    const partial = reqOf('REQ-x', { artifacts: [{ kind: 'requirement', confirmedAt: 1 }, { kind: 'requirement' }] as never })
    expect(targetConfirmedInLedger(partial, rec())).toBe(false)
    const otherKind = reqOf('REQ-x', { artifacts: [{ kind: 'design', confirmedAt: 1 }] as never })
    expect(targetConfirmedInLedger(otherKind, rec())).toBe(false)
  })
})

describe('markInterrupted / 过期基准（FR-4）', () => {
  it('未知 ticket 返回 undefined 且不抛', () => {
    const registry = new PendingConfirmRegistry({ now: () => 0 })
    expect(registry.markInterrupted('pc-nope')).toBeUndefined()
  })

  it('幂等：二次调用不改 interruptedAt（只写首次）', () => {
    let now = 10
    const registry = new PendingConfirmRegistry({ now: () => now, ttlMs: 1000, newTicket: () => 'pc-000001' })
    registry.register({ windowKey: W, requirementId: 'REQ-x', target: 'plan' })
    expect(registry.markInterrupted('pc-000001')?.interruptedAt).toBe(10)
    now = 20
    expect(registry.markInterrupted('pc-000001')?.interruptedAt).toBe(10)
    now = 30
    expect(registry.get('pc-000001', W)?.interruptedAt).toBe(10)
  })

  it('过期基准 = interruptedAt ?? createdAt：createdAt 早于中止时间也不提前失效', () => {
    let now = 0
    const registry = new PendingConfirmRegistry({ now: () => now, ttlMs: 100, newTicket: () => 'pc-000001' })
    registry.register({ windowKey: W, requirementId: 'REQ-x', target: 'plan' })
    now = 90 // 仍在中止有效期内（90 <= 100）
    expect(registry.markInterrupted('pc-000001')?.interruptedAt).toBe(90)
    now = 150 // 以 createdAt 为基准早该过期（150 > 100）；以 interruptedAt 为基准仍有效（60 <= 100）
    expect(registry.get('pc-000001', W)?.ticket).toBe('pc-000001')
    expect(registry.pendingForWindow(W)?.ticket).toBe('pc-000001')
    now = 191 // interruptedAt + ttl = 190 → 过期
    expect(registry.get('pc-000001', W)).toBeUndefined()
    expect(registry.pendingForWindow(W)).toBeUndefined()
  })
})

describe('livePendingConfirm：过滤已 settle / 已过期 / 台账已落章（FR-2 / FR-4）', () => {
  it('台账已落章 → 放行（返回 undefined）；未落章 → 仍拦', () => {
    const registry = new PendingConfirmRegistry({ now: () => 0, ttlMs: 1000 })
    const p = registry.register({ windowKey: W, requirementId: 'REQ-x', target: 'artifact', kind: 'requirement' })
    expect(livePendingConfirm(depsOf(registry, [reqOf('REQ-x', { artifacts: [{ kind: 'requirement' }] as never })]), W)?.ticket).toBe(p.ticket)
    expect(livePendingConfirm(depsOf(registry, [reqOf('REQ-x', { artifacts: [{ kind: 'requirement', confirmedAt: 1 }] as never })]), W)).toBeUndefined()
  })

  it('已 settle → undefined；台账查不到需求 → 保守仍拦', () => {
    const registry = new PendingConfirmRegistry({ now: () => 0, ttlMs: 1000 })
    const p = registry.register({ windowKey: W, requirementId: 'REQ-x', target: 'plan' })
    expect(livePendingConfirm(depsOf(registry, []), W)?.ticket).toBe(p.ticket)
    registry.settle(p.ticket, { confirmed: false, advanced: false })
    expect(livePendingConfirm(depsOf(registry, []), W)).toBeUndefined()
  })

  it('未装配端口（deps.pendingConfirms 缺省）→ undefined', () => {
    expect(livePendingConfirm({} as UseCaseDeps, W)).toBeUndefined()
  })

  it('文案常量：blocked_tools 四条写路径；recovery 含取回执与看板两条路径', () => {
    expect([...PENDING_CONFIRM_BLOCKED_TOOLS]).toEqual(['reqboard_submit', 'reqboard_decompose', 'reqboard_move', 'reqboard_task_move'])
    expect(PENDING_CONFIRM_RECOVERY).toContain('收到作答前不得产出下游产物')
    expect(PENDING_CONFIRM_RECOVERY).toContain('reqboard_confirm_receipt')
    expect(PENDING_CONFIRM_RECOVERY).toContain('看板')
    const msg = pendingConfirmRejectMessage(rec({ ticket: 'pc-abc123', requirementId: 'REQ-x' }))
    expect(msg).toContain('pc-abc123')
    expect(msg).toContain('REQ-x')
    expect(msg).toContain('收到作答前不得产出下游产物')
    expect(msg).toContain('reqboard_confirm_receipt(ticket="pc-abc123")')
    expect(msg).toContain('看板')
    expect(msg).toContain('reqboard_ask_confirm')
  })
})
