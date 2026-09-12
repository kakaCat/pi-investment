/**
 * 自动回滚守卫（2026-09-12，w-adb088f2）
 *
 * 背景（真实验证门风险）：
 * validation_gate 在"显著恶化"分支对 candidate 执行
 *   genome_rollback(to_section_version = c.section_version - 1)
 * 该目标版本号**固化在候选记录里**，而 genome_rollback 没有任何 staleness 守卫——
 * 它按绝对版本号取内容后直接 writeSection 覆盖当前段。于是：
 *   ① 同一 section 堆叠多条 watching 候选时（实证：rules 段同时挂 g19/g21/g22/g28/g30×2，
 *      各自记着 section_version 8/10/11/16/17），任一条迟到裁决回滚，会把**其后的变更一并抹掉**；
 *   ② 候选双登记（见 fix/candidate-dedup）会加剧同一风险。
 *
 * 守卫不变量：**只有候选的 section_version 恰好等于该段当前版本时，才允许自动回滚**
 * —— 唯此"回滚到 v(n-1)"才精确等价于"撤销这次变更"。
 * 信息缺失一律拒绝（fail-closed）：破坏性操作宁可不做。
 */

export interface RollbackCandidateView {
  id: string;
  section: string;
  section_version?: number;
}

export interface RollbackDecision {
  allowed: boolean;
  /** 判定理由：拒绝时写入 candidate.note，供审计追溯（不静默） */
  reason: string;
}

export function canAutoRollback(
  cand: RollbackCandidateView,
  currentSectionVersion: number | null | undefined,
): RollbackDecision {
  const target = cand?.section_version;
  if (!Number.isInteger(target) || (target as number) < 1) {
    return {
      allowed: false,
      reason: `候选 section_version 非法（${String(target)}），无法定位回滚目标版本`,
    };
  }
  if (
    currentSectionVersion === null ||
    currentSectionVersion === undefined ||
    !Number.isFinite(Number(currentSectionVersion))
  ) {
    return {
      allowed: false,
      reason: '读不到该段当前版本号（genome.json 不可读或字段缺失），拒绝自动回滚（fail-closed）',
    };
  }
  const cur = Number(currentSectionVersion);
  const tgt = target as number;
  if (cur !== tgt) {
    return {
      allowed: false,
      reason:
        `候选已被后续变更取代（候选 section_version=${tgt}，当前 v${cur}）——` +
        '自动回滚会覆盖其后的变更，已拒绝；如确需撤销请人工 genome_rollback 并写明目标版本',
    };
  }
  return {
    allowed: true,
    reason: `候选仍为当前版本（v${tgt}），回滚到 v${tgt - 1} 精确等价于撤销本次变更`,
  };
}
