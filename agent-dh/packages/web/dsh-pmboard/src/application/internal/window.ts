/**
 * 窗口↔需求绑定投影（REQ-47939a t6）——从 host/capture.ts 逐字搬入的纯判定（无 I/O、无 ctx）。
 *
 * 为什么在 application：用例需要"本窗口绑定的 open 需求"这一投影（move/decompose/show-status
 * 都靠它做归属校验）。REQ-47939a t9：host/capture.ts 的同名实现（重复的第二份 OPEN 状态集合）
 * 已删除，本模块成为唯一实现处；windowKeyFromContext / draftRequirementsFor / shouldCaptureWindow
 * 也在 t9 从 host/capture.ts、host/capture-hook.ts 逐字搬入。行为与搬迁前一致。
 *
 * @module dsh-pmboard/application/internal/window
 */
import { isOpenRequirement } from '../../domain/status/Predicates.js'
import type { LedgerView } from '../ports.js'
import type { RequirementRecord } from '../../shared/protocol.js'

/** 只读台账视图：直接取 ports 的 LedgerView 投影（此前 Pick<ReqboardLedger,...> 要求可变数组，
 *  与 repo.snapshot()/read() 返回的只读视图不兼容——收敛为同一类型，消除两套口径）。 */
type View = Pick<LedgerView, 'requirements' | 'triages'>

// 进行中判据已单点至 domain（REQ-47939a 返工修复：此前此处私下定义 OPEN_REQ_STATUSES，
// 路由层却引用了不存在的 OPEN_STATUSES → /session/:id/progress 运行时 500、会话框流程节点不显示）
const isOpenReq = isOpenRequirement

/**
 * 该窗口是否已绑定进行中的需求。规则（B：从需求记录判断）：
 *  1. 台账存在 open req 且 sourceSessionId === windowKey（窗口直接立项/自动立项）；
 *  2. 该窗口某条 triage 已确认（bind_req/create_req）且其 resultRequirementId(s)
 *     指向仍 open 的 req（bind 场景 req.sourceSessionId 可能不是本窗口，需窗口侧锚点）。
 */
export function isWindowBound(ledger: View, windowKey: string): boolean {
  if (ledger.requirements.some(r => r.sourceSessionId === windowKey && isOpenReq(r))) return true
  for (const tri of ledger.triages) {
    if (tri.sessionId !== windowKey) continue
    const anchorIds: string[] = []
    if (tri.resultRequirementId) anchorIds.push(tri.resultRequirementId)
    if (Array.isArray(tri.resultRequirementIds)) anchorIds.push(...tri.resultRequirementIds)
    for (const reqId of anchorIds) {
      const req = ledger.requirements.find(r => r.id === reqId)
      if (req && isOpenReq(req)) return true
    }
  }
  return false
}

/** 该窗口进行中的需求（简要投影，供引导文本与 reqboard_status 使用）。 */
export function openRequirementsFor(ledger: View, windowKey: string): RequirementRecord[] {
  const direct = ledger.requirements.filter(r => r.sourceSessionId === windowKey && isOpenReq(r))
  const anchored = new Map<string, RequirementRecord>()
  for (const tri of ledger.triages) {
    if (tri.sessionId !== windowKey) continue
    const ids: string[] = []
    if (tri.resultRequirementId) ids.push(tri.resultRequirementId)
    if (Array.isArray(tri.resultRequirementIds)) ids.push(...tri.resultRequirementIds)
    for (const reqId of ids) {
      const req = ledger.requirements.find(r => r.id === reqId)
      if (req && isOpenReq(req) && !anchored.has(req.id)) anchored.set(req.id, req)
    }
  }
  const seen = new Set<string>()
  const out: RequirementRecord[] = []
  for (const r of [...direct, ...anchored.values()]) {
    if (seen.has(r.id)) continue
    seen.add(r.id)
    out.push(r)
  }
  return out
}

/** 该窗口绑定的 open 需求里，仍处 draft 的（接手推进信号 R1 用）。 */
export function draftRequirementsFor(ledger: View, windowKey: string): RequirementRecord[] {
  return openRequirementsFor(ledger, windowKey).filter(r => r.status === 'draft')
}

/** 该窗口是否「需要走一次立项捕获」：unbound 即需要。 */
export function shouldCaptureWindow(ledger: View, windowKey: string): boolean {
  return !isWindowBound(ledger, windowKey)
}

// ---------------------------------------------------------------------------
// systemPrompt 组装上下文 → 窗口键（REQ-47939a t9：从 host/capture.ts 逐字搬入）
// ---------------------------------------------------------------------------

/** 从组装 context 提取窗口键：agent.id（'session-<uuid>'）优先，scope 兜底。 */
export function windowKeyFromContext(context: { agent?: { id?: unknown }; scope?: unknown } | undefined): string | undefined {
  const agentId = context?.agent?.id
  if (typeof agentId === 'string' && agentId.length > 0) return agentId
  const scope = context?.scope
  if (typeof scope === 'string' && scope.length > 0) return scope
  return undefined
}
