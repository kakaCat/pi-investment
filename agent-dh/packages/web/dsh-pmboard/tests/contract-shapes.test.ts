/**
 * 契约形状门禁（REQ-260924213231-b1c4 / T-1，落实 interfaces.md I-1/I-3/I-4/I-8 与
 * data-model.md T-1/T-3/T-4）。
 *
 * 本文件把设计文档的字段表**逐字钉死**，两道断言互为补充：
 *   - 运行时：构造规范取值，断言键集合与字段表一致（多一个少一个都红）；
 *   - 类型层：expectTypeOf 断言精确形状——实现卡（T-3/T-4/T-6/T-9）让字段漂移时本文件编译报错
 *     （T-1 验收标准要求「新增文件 0 报错」）。
 * 本卡只立契约、不含实现。
 */
import { describe, it, expect, expectTypeOf } from 'vitest'
import {
  ALL_ARTIFACT_KINDS,
  PENDING_CONFIRM_TICKET_PREFIX,
  type ArtifactKind,
  type DesignDocRegistration,
  type InterruptionRecord,
  type PendingConfirmation,
  type PendingConfirmationOutcome,
  type RequirementRecord,
} from '../src/shared/protocol.js'
import type { PendingConfirmPort, UseCaseDeps } from '../src/application/ports.js'

/** 规范挂起确认取值（T-4 字段表的最小完备样本）。 */
const PENDING: PendingConfirmation = {
  ticket: PENDING_CONFIRM_TICKET_PREFIX + '0f1e2d',
  windowKey: 'session-abc123',
  requirementId: 'REQ-abc123',
  target: 'artifact',
  kind: 'design',
  createdAt: 1_790_262_000_000,
}

describe('T-1 断点记录（FR-6 / I-8）', () => {
  it('字段表：at/reason/stage/pendingAction 必填，tool 可选', () => {
    const checkpoint: InterruptionRecord = {
      at: 1_790_262_000_000,
      reason: 'checkpoint',
      stage: 'design',
      pendingAction: 'reqboard_ask_confirm(target=artifact, kind=design)',
    }
    expect(Object.keys(checkpoint).sort()).toEqual(['at', 'pendingAction', 'reason', 'stage'])
    expectTypeOf<InterruptionRecord>().toEqualTypeOf<{
      at: number
      reason: string
      stage: string
      pendingAction: string
      tool?: string
    }>()
  })

  it('挂在需求上且可选：存量记录读出即「无断点」（undefined，不是空对象）', () => {
    const legacy = {} as RequirementRecord
    expect(legacy.interruption).toBeUndefined()
    expectTypeOf<RequirementRecord['interruption']>().toEqualTypeOf<InterruptionRecord | undefined>()
  })
})

describe('T-3 逐份登记态投影（FR-1 / I-1 design_docs[]）', () => {
  it('五个必填 + 两个可选，与 I-1 字段表一致', () => {
    const row: DesignDocRegistration = {
      name: 'architecture.md',
      path: 'docs/requirements/REQ-x/design/architecture.md',
      on_disk: true,
      registered: true,
      confirmed: false,
    }
    expect(Object.keys(row).sort()).toEqual(['confirmed', 'name', 'on_disk', 'path', 'registered'])
    expectTypeOf<DesignDocRegistration>().toEqualTypeOf<{
      name: string
      path: string
      on_disk: boolean
      registered: boolean
      confirmed: boolean
      exempted?: string
      conditional?: 'frontend' | 'backend'
    }>()
  })

  it('「未登记 / 待确认 / 已落章」三态由三个布尔区分（闸门文案分叉的事实源）', () => {
    const unregistered: DesignDocRegistration = { name: 'a.md', path: 'p/a.md', on_disk: true, registered: false, confirmed: false }
    const awaiting: DesignDocRegistration = { name: 'a.md', path: 'p/a.md', on_disk: true, registered: true, confirmed: false }
    const stamped: DesignDocRegistration = { name: 'a.md', path: 'p/a.md', on_disk: true, registered: true, confirmed: true }
    expect([unregistered.registered, awaiting.confirmed, stamped.confirmed]).toEqual([false, false, true])
  })
})

describe('T-4 挂起确认（FR-3 / I-3 I-4）', () => {
  it('ticket 前缀固定 pc-；字段表与 T-4 一致', () => {
    expect(PENDING_CONFIRM_TICKET_PREFIX).toBe('pc-')
    expect(PENDING.ticket.startsWith('pc-')).toBe(true)
    expect(Object.keys(PENDING).sort()).toEqual(['createdAt', 'kind', 'requirementId', 'target', 'ticket', 'windowKey'])
    expectTypeOf<PendingConfirmation>().toEqualTypeOf<{
      ticket: string
      windowKey: string
      requirementId: string
      target: 'artifact' | 'plan'
      kind?: ArtifactKind
      createdAt: number
      outcome?: PendingConfirmationOutcome
    }>()
  })

  it('回执结果：confirmed/advanced 必填，用户选择与意见可选', () => {
    const settled: PendingConfirmationOutcome = { confirmed: true, advanced: true }
    expect(Object.keys(settled).sort()).toEqual(['advanced', 'confirmed'])
    expectTypeOf<PendingConfirmationOutcome>().toEqualTypeOf<{
      confirmed: boolean
      advanced: boolean
      userChoice?: string
      userFeedback?: string
    }>()
  })

  it('端口面只有 register/get/settle；UseCaseDeps 允许缺省（未装配 = 旧阻塞语义）', () => {
    const fake: PendingConfirmPort = {
      register: () => PENDING,
      get: () => undefined,
      settle: () => undefined,
    }
    expect(Object.keys(fake).sort()).toEqual(['get', 'register', 'settle'])
    expectTypeOf<keyof PendingConfirmPort>().toEqualTypeOf<'register' | 'get' | 'settle'>()
    expectTypeOf<UseCaseDeps['pendingConfirms']>().toEqualTypeOf<PendingConfirmPort | undefined>()
  })
})

describe('I-1 kind=design 的事实前提', () => {
  it("'design' 已是合法产物种类（登记入口不会撞枚举）", () => {
    expect(ALL_ARTIFACT_KINDS).toContain('design')
  })
})
