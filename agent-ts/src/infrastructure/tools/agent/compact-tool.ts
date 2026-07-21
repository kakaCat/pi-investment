/**
 * Compact Tool - 手动触发上下文压缩
 */
import { Type } from "@sinclair/typebox";
import { generateSummary } from "../../../sdk-facade.js";
import type { AgentSession } from "../../../sdk-facade.js";
import { getMessages, getModel } from "../../../core/agent/session-adapter.js";
import { getActiveApiKey } from "../../../config/config.js";

let sessionRef: AgentSession | null = null;

export function initCompactTool(session: AgentSession) {
  sessionRef = session;
}

export const compactTool = {
  name: "compact",
  label: "压缩上下文",
  description:
    "Manually trigger conversation compaction to reclaim context window space. " +
    "Use when the conversation is getting long and you notice degraded recall, or proactively before starting a large task that will consume many tokens. " +
    "Do NOT use routinely after every response — compaction discards raw history and replaces it with a summary, so only trigger it when context pressure is real. " +
    "Optionally provide a focus hint to tell the summarizer what to preserve (e.g., 'current task state and file paths').",
  parameters: Type.Object({
    focus: Type.Optional(Type.String({ description: "What to preserve in the summary" }))
  }),
  execute: async (_toolCallId: string, params: { focus?: string }) => {
    if (!sessionRef) {
      return {
        content: [{ type: "text" as const, text: "Session not initialized" }],
        details: null,
      };
    }

    try {
      const messages = getMessages(sessionRef);
      const beforeCount = messages.length;

      // 生成摘要（SDK 会自动处理压缩和保存 CompactionEntry）
      const model = getModel(sessionRef);
      const apiKey = getActiveApiKey();

      await generateSummary(messages as any, model, 16384, apiKey);

      return {
        content: [{ type: "text" as const, text: `✅ Compaction triggered (${beforeCount} messages).${params.focus ? `\nFocus: ${params.focus}` : ""}` }],
        details: null,
        triggerCompaction: true
      };
    } catch (e) {
      console.warn("⚠️  压缩失败:", e instanceof Error ? e.message : String(e));
      return {
        content: [{ type: "text" as const, text: `❌ Compaction failed: ${e instanceof Error ? e.message : String(e)}` }],
        details: null,
      };
    }
  }
};
