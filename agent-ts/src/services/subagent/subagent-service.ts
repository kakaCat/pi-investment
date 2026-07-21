/**
 * Subagent - 独立上下文的子 agent
 *
 * 核心概念：
 * - 子 agent 有全新的 messages=[]
 * - 只返回最终摘要给父 agent
 * - 共享文件系统，但不共享对话历史
 */
import { createModel, paths } from "../../config/config.js";
import { createTrackedSession } from "../../infrastructure/session/session-factory.js";
import { getLastMessage, extractTextContent } from "../../core/agent/session-adapter.js";

/**
 * 运行子 agent 执行独立任务
 * @param prompt - 子任务提示
 * @returns 子 agent 的执行摘要
 */
export async function runSubagent(prompt: string): Promise<string> {
  try {
    if (!prompt || !prompt.trim()) {
      throw new Error("Subagent prompt cannot be empty");
    }

    const session = await createTrackedSession({
      agentType: 'subagent',
      createOptions: {
        cwd: paths.root,
        model: createModel(),
      },
    });

    // 执行任务
    await session.prompt(prompt);

    // 只返回最终文本摘要
    const lastMsg = getLastMessage(session);

    if (lastMsg?.role === "assistant") {
      const summary = extractTextContent(lastMsg);

      if (!summary!.trim()) {
        return "(no summary generated)";
      }

      return summary;
    }

    return "(no response from subagent)";
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("❌ Subagent 执行失败:", message);
    return `Error: Subagent failed - ${message}`;
  }
}
