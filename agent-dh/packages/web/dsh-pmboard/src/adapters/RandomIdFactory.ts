/**
 * ID 工厂适配器（REQ-47939a t5 / ports.ts IdFactory）。
 *
 * domain 禁止 Math.random()，ID 一律注入。需求ID格式：REQ-YYMMDDHHmmss-xxxx
 * (时间戳精确到秒 + 4位随机hex)，任务/执行/评论ID保持原格式：
 * 前缀-xxxxxx (6位随机hex + 可读前缀)。
 *
 * 本适配器不 import shared 契约层（architecture.md §2：adapters 只依赖 ports/domain/node），
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

/** 随机 4 位 hex（用于带时间戳的ID）。 */
function hex4(): string {
  return randomInt(0, 0xffff).toString(16).padStart(4, '0')
}

/** 格式化时间戳为 YYMMDDHHmmss（精确到秒）。 */
function formatTimestamp(date: Date = new Date()): string {
  const yy = date.getFullYear().toString().slice(-2)
  const MM = (date.getMonth() + 1).toString().padStart(2, '0')
  const DD = date.getDate().toString().padStart(2, '0')
  const HH = date.getHours().toString().padStart(2, '0')
  const mm = date.getMinutes().toString().padStart(2, '0')
  const ss = date.getSeconds().toString().padStart(2, '0')
  return `${yy}${MM}${DD}${HH}${mm}${ss}`
}

export class RandomIdFactory implements IdFactory {
  requirement(): string {
    return `REQ-${formatTimestamp()}-${hex4()}`
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
