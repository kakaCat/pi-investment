/**
 * 挂起确认注册表（REQ-260924213231-b1c4 T-6 · FR-3 / T-4）——`PendingConfirmPort` 的唯一实现。
 *
 * 为什么是**内存**：挂起确认是「弹框已投递、人还没答」的短时态，不是业务事实；业务事实
 * （confirmedAt / 计划批准）落台账。进程重启丢掉 ticket 时，回执按 E-5 报
 * `REQBOARD_UNKNOWN_TICKET`，引导调用方改读台账（confirmedAt 为准）——不猜、不伪造。
 *
 * 语义：
 *  - ticket 前缀固定 `pc-`（PENDING_CONFIRM_TICKET_PREFIX），全局唯一；
 *  - `get` 只认**本窗口**且未过期（createdAt + ttl，缺省 LIMITS.confirmEvidenceWindowMs）的记录；
 *  - `settle` 回填后台作答结果，**幂等**（重复回填保留首次结果）；
 *  - 三个方法都**不抛**（未知/跨窗口/过期一律 undefined，由用例降级）。
 *
 * @module dsh-pmboard/adapters/PendingConfirmRegistry
 */
import { randomInt } from 'node:crypto'
import type { PendingConfirmPort } from '../application/ports.js'
import { LIMITS } from '../domain/limits.js'
import {
  PENDING_CONFIRM_TICKET_PREFIX,
  type ArtifactKind,
  type PendingConfirmation,
  type PendingConfirmationOutcome,
} from '../shared/protocol.js'

export interface PendingConfirmRegistryOptions {
  /** 时间源（测试注入固定值；默认 Date.now——adapters 允许非确定性）。 */
  now?: () => number
  /** 过期窗口（毫秒；默认 LIMITS.confirmEvidenceWindowMs）。 */
  ttlMs?: number
  /** ticket 生成器（测试注入固定值；默认 `pc-` + 6 位 hex）。 */
  newTicket?: () => string
}

export class PendingConfirmRegistry implements PendingConfirmPort {
  private readonly records = new Map<string, PendingConfirmation>()
  private readonly now: () => number
  private readonly ttlMs: number
  private readonly newTicket: () => string

  constructor(options: PendingConfirmRegistryOptions = {}) {
    this.now = options.now ?? ((): number => Date.now())
    this.ttlMs = options.ttlMs ?? LIMITS.confirmEvidenceWindowMs
    this.newTicket = options.newTicket ?? ((): string =>
      PENDING_CONFIRM_TICKET_PREFIX + randomInt(0, 0xffffff).toString(16).padStart(6, '0'))
  }

  register(input: {
    windowKey: string
    requirementId: string
    target: 'artifact' | 'plan'
    kind?: ArtifactKind
  }): PendingConfirmation {
    const record: PendingConfirmation = {
      ticket: this.newTicket(),
      windowKey: input.windowKey,
      requirementId: input.requirementId,
      target: input.target,
      ...(input.kind === undefined ? {} : { kind: input.kind }),
      createdAt: this.now(),
    }
    this.records.set(record.ticket, record)
    return { ...record }
  }

  get(ticket: string, windowKey: string): PendingConfirmation | undefined {
    const found = this.records.get(ticket)
    if (found === undefined) return undefined
    if (found.windowKey !== windowKey) return undefined
    if (this.now() - found.createdAt > this.ttlMs) return undefined
    return this.copy(found)
  }

  settle(ticket: string, outcome: PendingConfirmationOutcome): PendingConfirmation | undefined {
    const found = this.records.get(ticket)
    if (found === undefined) return undefined
    if (found.outcome === undefined) found.outcome = { ...outcome }
    return this.copy(found)
  }

  /** 对外一律给副本：调用方拿不到内部引用，也改不动注册表。 */
  private copy(record: PendingConfirmation): PendingConfirmation {
    return {
      ...record,
      ...(record.outcome === undefined ? {} : { outcome: { ...record.outcome } }),
    }
  }
}
