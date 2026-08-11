/**
 * LoopGuardian 核心 —— 纯函数规则判定，不依赖 SDK。
 * 全部阈值与文案集中在常量区（将来可被文本参数进化系统调优）。
 */

// ---------- 阈值常量 ----------
export const NUDGE_INTERVAL = 13;          // R1：停止无效重试
export const FILE_CHECKPOINT_INTERVAL = 31; // R2：发现写入文件
export const HARD_TURN_LIMIT = 150;        // R4：软收尾上限
export const REPEAT_CALL_THRESHOLD = 3;    // R3：同 tool+args 连续次数
export const PROVIDER_ERROR_THRESHOLD = 3; // R7：provider 错误次数

// ---------- 状态 ----------
export interface GuardianState {
  turnCount: number;
  toolCallCount: number;
  consecutiveNoToolTurns: number;
  recentCallHashes: string[];
  providerErrors: number;
  firedNudgeTurns: Set<number>;
  hardLimitFired: boolean;
  followUpSent: boolean;
}

export function createGuardianState(): GuardianState {
  return {
    turnCount: 0,
    toolCallCount: 0,
    consecutiveNoToolTurns: 0,
    recentCallHashes: [],
    providerErrors: 0,
    firedNudgeTurns: new Set(),
    hardLimitFired: false,
    followUpSent: false,
  };
}

// ---------- 干预动作 ----------
export type Intervention =
  | { kind: "steer"; text: string; reason: string }
  | { kind: "followUp"; text: string; reason: string }
  | { kind: "notify"; title: string; content: string; reason: string };

// ---------- R1/R2：轮次纠偏 ----------
export function evaluateTurnEnd(s: GuardianState): Intervention[] {
  const out: Intervention[] = [];
  if (
    s.turnCount > 0 &&
    s.turnCount % NUDGE_INTERVAL === 0 &&
    !s.firedNudgeTurns.has(s.turnCount)
  ) {
    s.firedNudgeTurns.add(s.turnCount);
    out.push({
      kind: "steer",
      text: `[系统] 第${s.turnCount}轮：停止无新信息的重试。把关键上下文存入 memory_write；若无进展，换方案或重读相关 skill。`,
      reason: "R1:nudge",
    });
  }
  if (
    s.turnCount > 0 &&
    s.turnCount % FILE_CHECKPOINT_INTERVAL === 0 &&
    !s.firedNudgeTurns.has(-s.turnCount) // R2 用负数键与 R1 区分
  ) {
    s.firedNudgeTurns.add(-s.turnCount);
    out.push({
      kind: "steer",
      text: `[系统] 第${s.turnCount}轮：把关键发现/已试方案写入文件（不止工作记忆），防止上下文压缩后丢失。`,
      reason: "R2:file-checkpoint",
    });
  }
  return out;
}
