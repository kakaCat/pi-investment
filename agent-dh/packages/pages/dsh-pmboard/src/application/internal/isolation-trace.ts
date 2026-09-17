/**
 * 节点隔离留痕（REQ-422af1 t10）——隔离尝试（replaced / skipped / rejected / fallback）
 * 的可查台账：回答"这次节点结算到底有没有遗弃上下文、替换了 surface 的哪一段"。
 *
 * 与注入留痕（application/internal/injection-log.ts）同款：本模块是**纯逻辑**
 * （容量 + 追加 + 校验），不 import node:（application 层硬约束，tests/layer-boundary.test.ts
 * 机械检查）、不取时间（at 由 t9 用例经注入的 Clock 落章）。落盘由
 * adapters/IsolationTraceFile.ts 实现（原子写 + 串行队列）。
 *
 * 容量有界：ring buffer 保留最近 ISOLATION_TRACE_CAP 条（隔离是低频事件，200 足够回查）。
 *
 * @module dsh-pmboard/application/internal/isolation-trace
 */
import { fmt } from '../../domain/text/fmt.js'
import type { IsolationTraceEntry } from '../use-cases/IsolateNodeContext.js'

/** ring buffer 保留条数。 */
export const ISOLATION_TRACE_CAP = 200

/** 留痕文件的相对位置（相对 DSH 主目录）。 */
export const ISOLATION_TRACE_REL = 'state/node-isolation-log.json'

/** **必需**字段（可选字段 code/range/artifactSeq/replacementSeq 按状态出现，不在此列）。 */
export const ISOLATION_TRACE_FIELDS: readonly (keyof IsolationTraceEntry)[] = [
  'at', 'windowKey', 'stage', 'status', 'reason', 'routeKey', 'packageChars',
]

/** ring buffer 追加：保留最近 cap 条（超界丢最旧）。cap 非法 → 响亮抛错。 */
export function appendToIsolationTrace(
  existing: readonly IsolationTraceEntry[],
  entry: IsolationTraceEntry,
  cap: number = ISOLATION_TRACE_CAP,
): IsolationTraceEntry[] {
  if (!Number.isInteger(cap) || cap <= 0) {
    throw new Error(fmt('isolation-trace cap 必须是正整数，收到 {cap}', { cap }))
  }
  const next = [...existing, entry]
  return next.length > cap ? next.slice(next.length - cap) : next
}

/**
 * 一条记录是否可信（读回时防残缺记录混入）：
 * 必需七字段类型正确，且 status='replaced' 时**必须**带被替换区间——
 * 没有 range 的 replaced 记录等于"遗弃了上下文但说不清遗弃了哪一段"。
 */
export function isIsolationTraceEntry(raw: unknown): raw is IsolationTraceEntry {
  if (typeof raw !== 'object' || raw === null) return false
  const o = raw as Record<string, unknown>
  if (typeof o.at !== 'number' || !Number.isFinite(o.at)) return false
  for (const key of ['windowKey', 'stage', 'status', 'reason', 'routeKey'] as const) {
    if (typeof o[key] !== 'string') return false
  }
  if (typeof o.packageChars !== 'number' || !Number.isFinite(o.packageChars)) return false
  if (o.status === 'replaced' && !isRange(o.range)) return false
  if (o.range !== undefined && !isRange(o.range)) return false
  return true
}

function isRange(raw: unknown): boolean {
  if (typeof raw !== 'object' || raw === null) return false
  const r = raw as { start?: unknown; end?: unknown }
  return typeof r.start === 'number' && Number.isFinite(r.start)
    && typeof r.end === 'number' && Number.isFinite(r.end)
}
