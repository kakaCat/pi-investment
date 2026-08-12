/**
 * SDK Facade — 唯一的 SDK 导入入口
 *
 * 当 @mariozechner/pi-coding-agent 升级时，只需修改此文件及其子 facade。
 * 业务代码通过此 facade 导入所有 SDK 类型和函数，不直接依赖 SDK。
 *
 * 架构: 业务层 → facade → SDK
 */

// ═══════════════════════════════════════════════════════════════════════════
// 1. 稳定的内部类型定义（不受 SDK 变更影响）
// ═══════════════════════════════════════════════════════════════════════════

import type { AgentToolResult } from "@mariozechner/pi-coding-agent";

/**
 * 稳定的工具执行函数签名
 * 使用 `any` 保持参数类型兼容性，避免 contravariance 问题
 * 固定 5 参数格式，通过 normalizeToolDefinition 适配 SDK 的当前签名
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type PiToolExecute<TParams = any> = (
  toolCallId: string,
  params: TParams,
  signal?: AbortSignal,
  onUpdate?: (update: unknown) => void,
  ctx?: unknown
) => Promise<AgentToolResult<unknown>>;

/**
 * 稳定的工具结果类型
 */
export type PiToolResult = AgentToolResult<unknown>;

/**
 * 稳定的工具定义接口
 *
 * - label: 可选（normalize 时自动使用 name 填充）
 * - execute: 固定 5 参数 PiToolExecute 签名
 * - parameters: 宽泛的 Record 类型，兼容 TypeBox 和 plain object
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface PiToolDefinition<TParams = any> {
  name: string;
  label?: string;
  description: string;
  parameters: Record<string, unknown>;
  execute: PiToolExecute<TParams>;
  promptSnippet?: string;
  promptGuidelines?: string[];
}

// ═══════════════════════════════════════════════════════════════════════════
// 2. 类型归一化：适配 PiToolDefinition → SDK ToolDefinition
// ═══════════════════════════════════════════════════════════════════════════

import type { ToolDefinition as SdkToolDefinition } from "@mariozechner/pi-coding-agent";

// Hook 系统（T6）懒加载：模块不存在（T6 未合并）或初始化失败时降级为直接执行。
// 静态 import 会让 main 在 T6 落地前无法编译——2026-08-12 T3b 曾因此弄断 main。
type BeforeHookFn = (ctx: {
  toolName: string;
  args: unknown;
  turnCount: number;
  toolCallCount: number;
}) => Promise<{ action: "allow" | "block" | "modify"; reason?: string; modifiedArgs?: unknown }>;

let hookFn: BeforeHookFn | null | undefined; // undefined=未探测，null=不可用
const HOOKS_MODULE_SPEC = "./services/hooks/index.js"; // 变量化：T6 未落地时 tsc 不静态解析
async function getBeforeToolCallHook(): Promise<BeforeHookFn | null> {
  if (hookFn !== undefined) return hookFn;
  try {
    const mod = await import(HOOKS_MODULE_SPEC);
    hookFn = mod.executeBeforeToolCallHooks as BeforeHookFn;
  } catch {
    hookFn = null;
  }
  return hookFn;
}

// 用于追踪 turn/toolCall 计数（全局状态，每个 agent_start 重置由 LoopGuardian 管理）
let globalTurnCount = 0;
let globalToolCallCount = 0;

// 导出给 LoopGuardian 使用的计数器重置函数
export function resetToolExecutionCounters(): void {
  globalTurnCount = 0;
  globalToolCallCount = 0;
}

// 导出给 session-factory 在 turn_end 时递增 turnCount
export function incrementTurnCount(): void {
  globalTurnCount++;
}

/**
 * 将内部的 PiToolDefinition 转为 SDK 要求的 ToolDefinition
 * SDK 签名变更时只需修改此函数
 *
 * 集成 Hook 系统：在工具执行前调用 before_tool_call hooks
 */
export function normalizeToolDefinition(tool: PiToolDefinition): SdkToolDefinition {
  return {
    name: tool.name,
    label: tool.label ?? tool.name,
    description: tool.description,
    parameters: tool.parameters as SdkToolDefinition["parameters"],
    execute: async (
      toolCallId: string,
      params: unknown,
      signal?: AbortSignal,
      onUpdate?: (update: unknown) => void,
      ctx?: unknown
    ): Promise<AgentToolResult<unknown>> => {
      // Hook 系统拦截点（懒加载，T6 未落地时直通）
      globalToolCallCount++;
      const hook = await getBeforeToolCallHook();
      let finalParams = params;
      if (hook) {
        try {
          const hookResult = await hook({
            toolName: tool.name,
            args: params,
            turnCount: globalTurnCount,
            toolCallCount: globalToolCallCount,
          });

          if (hookResult.action === "block") {
            // 返回结果给 LLM（不标记为错误，让 LLM 能看到原因）
            return {
              content: [{ type: "text", text: `🚫 Tool call blocked by hook: ${hookResult.reason}` }],
              details: { blocked: true, reason: hookResult.reason },
            };
          }

          if (hookResult.action === "modify" && hookResult.modifiedArgs !== undefined) {
            finalParams = hookResult.modifiedArgs;
          }
        } catch (hookErr) {
          // hook 系统内部错误不阻断工具执行
          console.warn(`⚠️ before_tool_call hook error (allowing tool): ${hookErr}`);
        }
      }

      return tool.execute(toolCallId, finalParams, signal, onUpdate, ctx);
    },
    ...(tool.promptSnippet ? { promptSnippet: tool.promptSnippet } : {}),
    ...(tool.promptGuidelines ? { promptGuidelines: tool.promptGuidelines } : {}),
  } as SdkToolDefinition;
}

// ═══════════════════════════════════════════════════════════════════════════
// 3. 稳定类型的重导出（这些 SDK 类型历史上很少变化）
// ═══════════════════════════════════════════════════════════════════════════

export type { Skill } from "@mariozechner/pi-coding-agent";
export { loadSkills } from "@mariozechner/pi-coding-agent";
export type { AgentSession, AgentSessionEvent } from "@mariozechner/pi-coding-agent";
export { SessionManager } from "@mariozechner/pi-coding-agent";
export type { ToolDefinition as SdkToolDefinition } from "@mariozechner/pi-coding-agent";
export type { AgentToolResult, AgentToolUpdateCallback } from "@mariozechner/pi-coding-agent";

// ═══════════════════════════════════════════════════════════════════════════
// 4. 子 facade 导入
// ═══════════════════════════════════════════════════════════════════════════

export { createSession, createSession as createAgentSession, type CreateSessionOptions, type CreateSessionResult, type AgentSessionServices } from "./session-facade";
export { estimateTokens, generateSummary } from "./compaction-facade";

// 向后兼容：部分文件使用 ToolDefinition 作为类型名（重导出自身）
export type { PiToolDefinition as ToolDefinition };

// 跨包类型重导出
export type { AgentMessage } from "@mariozechner/pi-agent-core";

// ═══════════════════════════════════════════════════════════════════════════
// 5. 运行时工具重导出（createReadTool 等）
// ═══════════════════════════════════════════════════════════════════════════

export { createReadTool } from "@mariozechner/pi-coding-agent";
export { InteractiveMode, AgentSessionRuntime, createAgentSessionRuntime, createAgentSessionServices, getAgentDir } from "@mariozechner/pi-coding-agent";
export type { CreateAgentSessionRuntimeResult } from "@mariozechner/pi-coding-agent";
