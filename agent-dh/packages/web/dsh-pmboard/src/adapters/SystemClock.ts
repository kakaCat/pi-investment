/**
 * 时钟适配器（REQ-47939a t5 / ports.ts Clock）。
 *
 * domain 禁止 Date.now()（时间必须注入），用例要可复现；真实运行时注入本实现，
 * 测试注入固定时钟。这是"时间副作用"的唯一入口。
 *
 * @module dsh-pmboard/adapters/SystemClock
 */
import type { Clock } from '../application/ports.js'

export class SystemClock implements Clock {
  now(): number {
    return Date.now()
  }
}
