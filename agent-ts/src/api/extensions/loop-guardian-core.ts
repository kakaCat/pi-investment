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

// ---------- R5/R6：agent_end 最终回复检查 ----------
const CODE_BLOCK_AT_END = /```[a-zA-Z0-9_]*\n[\s\S]{50,}?```\s*$/;
const MIN_RESIDUAL_LEN = 30;

export function evaluateAgentEnd(
  s: GuardianState,
  finalText: string
): Intervention[] {
  // R7：provider 多次错误 → 立即停止，不注入任何消息（避免死循环）
  // 返回空数组 = 不发送任何干预，会话自然结束
  if (s.providerErrors >= PROVIDER_ERROR_THRESHOLD) {
    return [{
      kind: "notify",
      title: "🚨 LoopGuardian 强制停止会话",
      content: `LLM provider 连续返回错误 ${s.providerErrors} 次，已停止会话防止死循环。请检查：\n1. API key 是否有效 (.pi-invest/llm-state.json)\n2. 账户余额是否充足 (Kimi/DeepSeek)\n3. 模型切换日志 (model-switch.log)\n\n会话已终止，不会继续重试。`,
      reason: "R7:force-stop",
    }];
  }

  if (s.followUpSent) return []; // 防追问循环：每任务最多一次

  // R6：空回复或截断（仅在 provider 正常时才注入 followUp）
  if (!finalText.trim()) {
    s.followUpSent = true;
    return [{
      kind: "followUp",
      text: "[系统] 上轮回复为空或被截断。请分小步重新生成并完成操作。",
      reason: "R6:empty-response",
    }];
  }

  // R5：0 工具 + 单个大代码块结尾 + 块外残余 < 30 字符
  if (s.toolCallCount === 0) {
    const m = finalText.match(CODE_BLOCK_AT_END);
    if (m) {
      const residual = finalText
        .slice(0, finalText.length - m[0].length)
        .replace(/<thinking>[\s\S]*?<\/thinking>/gi, "")
        .replace(/<summary>[\s\S]*?<\/summary>/gi, "")
        .replace(/\s+/g, "");
      if (residual.length < MIN_RESIDUAL_LEN) {
        s.followUpSent = true;
        return [{
          kind: "followUp",
          text: "[系统] 你的回复以大段代码结尾但未调用任何工具。若要执行/写入/分析，请显式调用工具；若仅供展示，请用一句话说明后结束。",
          reason: "R5:code-block-no-tool",
        }];
      }
    }
  }
  return [];
}

// ---------- R7：provider 错误计数 ----------
export function evaluateProviderResponse(
  s: GuardianState,
  status: number
): void {
  if (status >= 400) s.providerErrors++;
}
