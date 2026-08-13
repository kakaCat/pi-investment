// quality-gate.ts
import type { GateResult, RecallHit } from './types.js';

export function applyQualityGate(hits: RecallHit[]): GateResult {
  if (hits.length === 0) return { gate: 'suppressed', reason: 'empty-result' };
  return { gate: 'passed', hits };
}
// 注：分量阈值（BM25>0 / cosine floor）在 v2 检索侧已过滤；
// 本门负责"空则不注入"语义 + 未来扩展（如 source 加权）的单点。
