/**
 * 确认门挂起期间的停手守卫（REQ-260927100007-b8ba t9 / FR-9）。
 *
 * 弹框走非阻塞投递：超宽限返回 {pending:true, ticket}，**不拦 agent loop**。若不停手，窗口会在
 * 等作答期间继续产出下游产物（实测事故）。本文件锁：写路径被拒且不写盘；status/receipt 保持可用。
 */
import { describe, it, expect } from 'vitest'
import { PendingConfirmRegistry } from '../src/adapters/PendingConfirmRegistry.js'
import { assertNoPendingConfirm } from '../src/application/internal/support.js'
import { defineStatusTool, defineRequirementSubmitTool, defineMoveTool, defineTaskMoveTool } from './helpers/tool-deps.js'
import { emptyLedger } from '../src/shared/protocol.js'
import type { UseCaseDeps } from '../src/application/ports.js'

const W = 'session-w-001'

function makeDeps() {
  const ledger = { ...emptyLedger(), requirements: [] as unknown[], tasks: [] as unknown[] }
  const store = { read: async (fn: (l: unknown) => unknown) => fn(ledger), snapshot: () => ledger } as never
  const registry = new PendingConfirmRegistry({ now: () => 100 })
  return { ledger, store, registry }
}

async function codeOf(p: Promise<unknown>): Promise<string | undefined> {
  try { await p; return undefined } catch (err) { return (err as { code?: string }).code }
}

describe('确认门挂起期间的停手守卫（FR-9）', () => {
  it('pending 未作答：本窗口 reqboard_submit 被拒 REQBOARD_CONFIRM_PENDING，且不写盘', async () => {
    const { ledger, store, registry } = makeDeps()
    registry.register({ windowKey: W, requirementId: 'REQ-x', target: 'plan' })
    const tool = defineRequirementSubmitTool({ store, now: () => 100, pendingConfirms: registry } as never) as never as { execute: (a: unknown, e: unknown) => Promise<unknown> }
    expect(await codeOf(tool.execute({ path: 'p.md', summary: 's', tasks: [] }, { agent: { id: W } }))).toBe('REQBOARD_CONFIRM_PENDING')
    expect(ledger.requirements).toHaveLength(0)
    expect(ledger.tasks).toHaveLength(0)
  })

  it('pending 未作答：reqboard_move / reqboard_task_move 同样被拒；跨窗口与本窗口已作答则放行', async () => {
    const { store, registry } = makeDeps()
    const rec = registry.register({ windowKey: W, requirementId: 'REQ-x', target: 'plan' })
    const deps = { store, now: () => 100, pendingConfirms: registry } as never
    const move = defineMoveTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<unknown> }
    const tmove = defineTaskMoveTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<unknown> }
    expect(await codeOf(move.execute({ to: 'implementing' }, { agent: { id: W } }))).toBe('REQBOARD_CONFIRM_PENDING')
    expect(await codeOf(tmove.execute({ task_id: 't-x', to: 'in_progress' }, { agent: { id: W } }))).toBe('REQBOARD_CONFIRM_PENDING')
    // 跨窗口不算挂起（守卫只看本窗口）
    expect(await codeOf(move.execute({ to: 'implementing' }, { agent: { id: 'session-other' } }))).not.toBe('REQBOARD_CONFIRM_PENDING')
    // 已作答（settle）后本窗口放行
    registry.settle(rec.ticket, { confirmed: true, advanced: true })
    expect(await codeOf(move.execute({ to: 'implementing' }, { agent: { id: W } }))).not.toBe('REQBOARD_CONFIRM_PENDING')
  })

  it('reqboard_status 不被守卫拦住（否则人无法解除挂起）', async () => {
    const { store, registry } = makeDeps()
    registry.register({ windowKey: W, requirementId: 'REQ-x', target: 'plan' })
    const status = defineStatusTool({ store, now: () => 100, pendingConfirms: registry } as never) as never as { execute: (a: unknown, e: unknown) => Promise<{ window_key?: string }> }
    const out = await status.execute({}, { agent: { id: W } })
    expect(out.window_key).toBe(W)
  })

  it('assertNoPendingConfirm 直测：无挂起/跨窗口/已作答放行；本窗口未作答抛错且信息含三条恢复路径', () => {
    const { store } = makeDeps()
    const registry = new PendingConfirmRegistry({ now: () => 100 })
    // 判定单点 livePendingConfirm 需读台账（有无落章）——测试同样给 repo，口径与运行态一致。
    const deps = { pendingConfirms: registry, repo: store } as unknown as UseCaseDeps
    assertNoPendingConfirm(deps, W)
    const rec = registry.register({ windowKey: W, requirementId: 'REQ-x', target: 'plan' })
    assertNoPendingConfirm(deps, 'session-other')
    try {
      assertNoPendingConfirm(deps, W)
      throw new Error('应当抛错')
    } catch (err) {
      const e = err as { code?: string; message?: string }
      expect(e.code).toBe('REQBOARD_CONFIRM_PENDING')
      expect(e.message).toContain('reqboard_confirm_receipt(ticket="' + rec.ticket + '")')
      expect(e.message).toContain('收到作答前不得产出下游产物')
      expect(e.message).toContain('看板')
      expect(e.message).toContain('reqboard_ask_confirm')
    }
    registry.settle(rec.ticket, { confirmed: true, advanced: true })
    assertNoPendingConfirm(deps, W)
  })

  it('TC-9 台账已落章（人走看板/证据通道作答）→ 守卫放行，不死锁', () => {
    const { ledger, store, registry } = makeDeps()
    ledger.requirements.push({ id: 'REQ-x', plan: { approvedAt: 1 } })
    registry.register({ windowKey: W, requirementId: 'REQ-x', target: 'plan' })
    const deps = { pendingConfirms: registry, repo: store } as unknown as UseCaseDeps
    expect(() => assertNoPendingConfirm(deps, W)).not.toThrow()
  })
})
