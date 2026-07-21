/**
 * Session Facade — 封装 createAgentSession
 *
 * 所有 `as any` 强制转换集中在此处。
 * SDK 变更 createAgentSession 参数时，只需修改此文件。
 */

import { createAgentSession as sdkCreateAgentSession } from "@mariozechner/pi-coding-agent";
import type { AgentSession } from "@mariozechner/pi-coding-agent";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AgentSessionServices = Record<string, any>;

export interface CreateSessionOptions {
  cwd?: string;
  model?: unknown;
  systemPrompt?: string | (() => string);
  customTools?: unknown[];
  skills?: unknown[];
  sessionManager?: unknown;
  [key: string]: unknown; // 允许透传其他 SDK 选项
}

export interface CreateSessionResult {
  session: AgentSession;
  /** AgentSessionServices — 需要传给 AgentSessionRuntime 构造 */
  services: AgentSessionServices;
  [key: string]: unknown;
}

/**
 * 创建 Agent 会话（SDK 隔离包装）
 *
 * 替代直接调用 createAgentSession，所有 SDK 参数变更在此吸收。
 * 返回 session + services，services 用于 AgentSessionRuntime 构造。
 */
export async function createSession(
  options: CreateSessionOptions
): Promise<CreateSessionResult> {
  const result = await sdkCreateAgentSession(options as any);
  return result as unknown as CreateSessionResult;
}
