/**
 * LoopGuardian Hook Adapters
 * 把 LoopGuardian 的轮次纠偏和 no_tool 拦截迁移为注册式 hooks
 */
import type { GuardianState } from "./loop-guardian-core.js";
import {
  evaluateToolCall,
  REPEAT_CALL_THRESHOLD,
} from "./loop-guardian-core.js";
import { hookRegistry, type HookDefinition, type BeforeToolCallContext, type HookResult } from "../../services/hooks/index.js";

/**
 * R3: 重复调用拦截 hook（优先级 20）
 * 检测连续 N 次相同 tool+args 调用，返回 block
 */
export function createRepeatCallInterceptHook(state: GuardianState): HookDefinition {
  return {
    name: "loop-guardian-repeat-call-intercept",
    priority: 20,
    timeoutMs: 100,
    triggers: ["before_tool_call"],
    handler: (context: BeforeToolCallContext): HookResult => {
      const interventions = evaluateToolCall(state, context.toolName, context.args);

      if (interventions.length > 0) {
        // 有干预 = 检测到重复调用
        const reason = interventions[0].reason;
        return {
          action: "block",
          reason: `${reason}: 连续 ${REPEAT_CALL_THRESHOLD} 次调用 ${context.toolName} 参数相同`,
        };
      }

      return { action: "allow" };
    },
  };
}

/**
 * 注册 LoopGuardian 的 hooks 到全局注册表
 * 在 loopGuardianExtension 初始化时调用
 */
export function registerLoopGuardianHooks(state: GuardianState): void {
  // 清理旧 hooks（避免重复注册）
  try {
    hookRegistry.unregister("loop-guardian-repeat-call-intercept");
  } catch {
    // ignore
  }

  hookRegistry.register(createRepeatCallInterceptHook(state));
}

/**
 * 注销 LoopGuardian hooks（用于测试清理或禁用）
 */
export function unregisterLoopGuardianHooks(): void {
  try {
    hookRegistry.unregister("loop-guardian-repeat-call-intercept");
  } catch {
    // ignore
  }
}
