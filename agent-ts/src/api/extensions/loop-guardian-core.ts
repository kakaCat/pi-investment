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
  // ---------- R4：硬上限（每任务一次） ----------
  if (s.turnCount >= HARD_TURN_LIMIT && !s.hardLimitFired) {
    s.hardLimitFired = true;
    out.push(
      {
        kind: "notify",
        title: "⚠️ LoopGuardian 硬上限",
        content: `任务已达 ${s.turnCount} 轮上限，已要求 agent 总结进展并收尾。`,
        reason: "R4:hard-limit",
      },
      {
        kind: "steer",
        text: `[系统] 已达 ${s.turnCount} 轮上限。停止继续尝试，总结已验证的进展和残余风险后收尾。`,
        reason: "R4:hard-limit",
      }
    );
  }
  return out;
}

/** key 排序的稳定序列化（同语义不同 key 顺序视为同一调用） */
export function stableStringify(v: unknown): string {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return `[${v.map(stableStringify).join(",")}]`;
  const o = v as Record<string, unknown>;
  return `{${Object.keys(o).sort().map(k => `${JSON.stringify(k)}:${stableStringify(o[k])}`).join(",")}}`;
}

/** 简单字符串哈希（仅用于 firedNudgeTurns 去重键，非加密用途） */
function hashCode(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h * 31 + str.charCodeAt(i)) | 0;
  }
  return h;
}

// ---------- R3：重复调用检测 ----------
export function evaluateToolCall(
  s: GuardianState,
  toolName: string,
  args: unknown
): Intervention[] {
  s.toolCallCount++;
  const hash = `${toolName}(${stableStringify(args)})`;
  s.recentCallHashes.push(hash);
  if (s.recentCallHashes.length > REPEAT_CALL_THRESHOLD) {
    s.recentCallHashes.shift();
  }
  const repeated =
    s.recentCallHashes.length === REPEAT_CALL_THRESHOLD &&
    s.recentCallHashes.every(h => h === hash);
  if (repeated && !s.firedNudgeTurns.has(hashCode(hash))) {
    s.firedNudgeTurns.add(hashCode(hash));
    return [{
      kind: "steer",
      text: `[系统] 检测到连续 ${REPEAT_CALL_THRESHOLD} 次相同调用 ${toolName}（参数相同）。先分析上次结果为什么不符合预期，再决定下一步。`,
      reason: "R3:repeat-call",
    }];
  }
  return [];
}
