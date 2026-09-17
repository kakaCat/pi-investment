/**
 * ID 工厂适配器（REQ-47939a t5 / ports.ts IdFactory）。
 *
 * domain 禁止 Math.random()，ID 一律注入。格式与 shared/protocol.ts 的
 * newRequirementId/newTaskId/newExecutionId/newCommentId **一致**（随机 6 位 hex + 可读前缀）——
 * 但本适配器不 import shared 契约层（architecture.md §2：adapters 只依赖 ports/domain/node），
 * 用 node:crypto 生成随机数，避免"domain 层契约"反向渗入 I/O 层。
 *
 * @module dsh-pmboard/adapters/RandomIdFactory
 */
import { randomInt } from 'node:crypto'
import type { IdFactory } from '../application/ports.js'

/** 随机 6 位 hex（与 protocol 的 new*Id 同格式）。 */
function hex6(): string {
  return randomInt(0, 0xffffff).toString(16).padStart(6, '0')
}

export class RandomIdFactory implements IdFactory {
  requirement(): string {
    return `REQ-${hex6()}`
  }
  task(): string {
    return `t-${hex6()}`
  }
  execution(): string {
    return `e-${hex6()}`
  }
  comment(): string {
    return `c-${hex6()}`
  }
}
