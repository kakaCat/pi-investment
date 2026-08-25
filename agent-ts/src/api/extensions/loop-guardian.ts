/**
 * LoopGuardian —— 引擎侧防呆护栏（纯工程机制，不调用 LLM）
 *
 * 设计：docs/superpowers/specs/2026-08-11-loop-guardian-design.md
 * 对治：光说不练（R5/R6）、死循环（R1-R4）、静默失败（R7）
 *
 * 本文件是薄事件翻译层：SDK 事件 → 更新状态 → core 纯函数判定 → 执行干预。
 * 全部规则逻辑在 loop-guardian-core.ts（可单测）。
 *
 * 开关：LOOP_GUARDIAN=off 整体禁用（默认开）。
 */
import type { ExtensionFactory } from "@mariozechner/pi-coding-agent";
import {
  createGuardianState,
  evaluateTurnEnd,
  evaluateProviderResponse,
  evaluateAgentEnd,
  type GuardianState,
  type Intervention,
} from "./loop-guardian-core.js";
import { notificationService } from "../../services/notification/notification-service.js";
import {
  registerLoopGuardianHooks,
  unregisterLoopGuardianHooks,
} from "./loop-guardian-hooks.js";
import { initHookLog } from "../../services/hooks/index.js";

/** 从 SDK AgentMessage 提取纯文本（content 为 string 或 {type:"text"} 数组） */
function extractText(message: any): string {
  if (!message) return "";
  const c = message.content;
  if (typeof c === "string") return c;
  if (Array.isArray(c)) {
    return c.filter((b: any) => b?.type === "text").map((b: any) => b.text ?? "").join("\n");
  }
  return "";
}

async function execute(pi: any, interventions: Intervention[]): Promise<void> {
  for (const iv of interventions) {
    console.log(`[LoopGuardian] ${iv.reason} → ${iv.kind}`);
    if (iv.kind === "notify") {
      try {
        await notificationService.sendCard({
          title: iv.title,
          content: iv.content,
          type: "warning",
          metadata: { reason: iv.reason },
        });
      } catch (e) {
        console.warn("[LoopGuardian] 通知发送失败:", e);
      }
    } else {
      pi.sendUserMessage(iv.text, { deliverAs: iv.kind });
    }
  }
}

export const loopGuardianExtension: ExtensionFactory = (pi) => {
  if (process.env.LOOP_GUARDIAN === "off") return;

  // 初始化 hook 日志
  initHookLog();

  let state: GuardianState = createGuardianState();

  // 会话级别的持久化标志（跨 agent_start 保留）
  let sessionFollowUpSent = false;
  let sessionProviderErrorCount = 0;

  pi.on("agent_start", () => {
    // 保留上一轮的 provider 错误计数和 followUp 标志
    const prevErrors = state.providerErrors;
    const prevFollowUpSent = state.followUpSent;

    state = createGuardianState();

    // 累加 provider 错误（跨轮次）
    sessionProviderErrorCount += prevErrors;
    state.providerErrors = sessionProviderErrorCount;

    // 恢复 followUpSent 标志
    if (sessionFollowUpSent) {
      state.followUpSent = true;
    }

    // 注册 hooks（每次新任务重新注册，确保状态绑定正确）
    unregisterLoopGuardianHooks();
    registerLoopGuardianHooks(state);
  });

  pi.on("turn_end", (event) => {
    state.turnCount++;
    if (event.toolResults?.length) {
      state.consecutiveNoToolTurns = 0;
    } else {
      state.consecutiveNoToolTurns++;
    }
    void execute(pi, evaluateTurnEnd(state));
  });

  // tool_execution_start 不再直接调用 evaluateToolCall
  // R3 重复调用检测已迁移到 hook 系统（在 tool 执行前被 hook executor 拦截）

  pi.on("after_provider_response", (event) => {
    evaluateProviderResponse(state, event.status);
  });

  pi.on("agent_end", (event) => {
    const lastAssistant = [...(event.messages ?? [])]
      .reverse()
      .find((m: any) => m?.role === "assistant");
    void execute(pi, evaluateAgentEnd(state, extractText(lastAssistant)));

    // 同步会话级别的标志（跨轮次保留）
    if (state.followUpSent) {
      sessionFollowUpSent = true;
    }

    // 任务结束后注销 hooks
    unregisterLoopGuardianHooks();
  });
};
