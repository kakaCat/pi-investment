/**
 * 待处理闸门登记表（REQ-e3b6a0 t3 / FR-2）——两相之间的**内存**瞬态信号。
 *
 * 为什么进内存不进台账：与既有 pendingCapture 同款——它是"刚被作答、待边界执行"的一次性
 * 信号；落台账就要迁移、要清理、要处理陈旧记录，而这些都不产生任何业务价值。
 *
 * 键 = windowKey：同窗口只保留**最新一条**（重复信号覆盖，不排队）——同一窗口同时挂两轮链
 * 没有意义，排队只会让迟到的旧信号带着过期上下文执行。
 *
 * @module dsh-pmboard/application/gate/PendingGate
 */
import type { ConfirmContext } from '../../domain/gate/GateSpec.js'

export interface PendingGateStore {
  set(ctx: ConfirmContext): void
  /** 取出并**消费**（同窗口只跑一轮链）。 */
  take(windowKey: string): ConfirmContext | undefined
  peek(windowKey: string): ConfirmContext | undefined
  size(): number
  clear(): void
}

export function createPendingGateStore(): PendingGateStore {
  const byWindow = new Map<string, ConfirmContext>()
  return {
    set(ctx) { byWindow.set(ctx.windowKey, ctx) },
    take(windowKey) {
      const ctx = byWindow.get(windowKey)
      byWindow.delete(windowKey)
      return ctx
    },
    peek(windowKey) { return byWindow.get(windowKey) },
    size() { return byWindow.size },
    clear() { byWindow.clear() },
  }
}
