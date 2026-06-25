/**
 * Session Facade — 封装 createAgentSession
 *
 * 所有 `as any` 强制转换集中在此处。
 * SDK 变更 createAgentSession 参数时，只需修改此文件。
 */

import { createAgentSession as sdkCreateAgentSession } from "@mariozechner/pi-coding-agent";
import type { AgentSession } from "@mariozechner/pi-coding-agent";

export interface CreateSessionOptions {
  cwd?: string;
  model?: unknown;
  systemPrompt?: string | (() => string);
  customTools?: unknown[];
  skills?: unknown[];
  sessionManager?: unknown;
  [key: string]: unknown; // 允许透传其他 SDK 选项
}

/**
 * 创建 Agent 会话（SDK 隔离包装）
 *
 * 替代直接调用 createAgentSession，所有 SDK 参数变更在此吸收。
 */
export async function createSession(
  options: CreateSessionOptions
): Promise<{ session: AgentSession; [key: string]: unknown }> {
  return sdkCreateAgentSession(options as any) as any;
}
