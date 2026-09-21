/**
 * 闸门 handlers 的共享助手（REQ-e3b6a0 t5/t6）——归属需求选择、文档安全读取、错误转文本。
 *
 * 抽出来的理由：H2（压缩）与 H3（注入）都要"本窗口是哪条需求"与"需求文档读得到吗"，
 * 各写一份必然漂移（本仓"两份真相"教训）。
 *
 * @module dsh-pmboard/application/gate/handlers/shared
 */
import type { DocRepository, ReqboardRepository } from '../../ports.js'
import type { ConfirmContext } from '../../../domain/gate/GateSpec.js'
import type { RequirementRecord } from '../../../shared/protocol.js'
import { openRequirementsFor } from '../../internal/window.js'

/** 归属需求：显式 id 优先，否则本窗口最近更新的进行中需求。 */
export function pickGateRequirement(repo: ReqboardRepository, ctx: ConfirmContext): RequirementRecord | undefined {
  const ledger = repo.snapshot()
  if (ctx.requirementId !== undefined && ctx.requirementId.length > 0) {
    const byId = ledger.requirements.find(r => r.id === ctx.requirementId)
    if (byId !== undefined) return byId
  }
  const open = openRequirementsFor(ledger, ctx.windowKey)
  return [...open].sort((a, b) => b.updatedAt - a.updatedAt)[0]
}

/** 读文档；失败按"读不到"处理（调用方据此 skip，不冒泡）。 */
export async function safeReadDoc(docs: DocRepository, relPath: string): Promise<string> {
  try {
    return await docs.read(relPath)
  } catch {
    return ''
  }
}

/** 错误 → 一行可读文本。 */
export function reasonOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
