/**
 * Clarify Tool - 意图识别与澄清工具
 *
 * 真实实现位于 services/plan/clarify-agent.ts
 */
import { Type } from "@sinclair/typebox";
import { createClarifyAgent } from "../../services/plan/clarify-agent.js";
import { logSubagentStart, logSubagentEnd } from "../logging/observable-logger.js";

export const clarifyTool = {
  name: "clarify",
  label: "意图澄清",
  description:
    "CLARIFICATION TOOL — pause execution and ask the user a focused question. Two valid use cases: " +
    "(1) BEFORE starting: request is vague, has multiple valid interpretations, or is missing information that would change what you do " +
    "(e.g., 'help me with my project' — which project? what kind of help?). " +
    "(2) MID-EXECUTION: a critical planned step has failed or hit a blocker, and proceeding differently would meaningfully change the output " +
    "(e.g., browser can't fetch real-time data — proceed with knowledge-based estimates, or stop and let user retry later?). " +
    "Returns structured questions with options for the user to answer. Execution resumes only after the user responds. " +
    "Do NOT use for recoverable errors where a retry or alternative tool would suffice without changing the output quality. " +
    "Do NOT use as a substitute for plan_task: clarify resolves 'what does the user want / how to handle a blocker', plan_task decides 'how to do it'.",
  parameters: Type.Object({
    request: Type.String({ description: "The user's original request or the ambiguous part to analyze." }),
    context: Type.Optional(Type.String({ description: "Optional additional context (e.g., recent conversation, relevant file paths)." })),
  }),
  execute: async (_toolCallId: string, params: { request: string; context?: string }) => {
    const startTime = Date.now();
    logSubagentStart("clarify", params.request);

    try {
      console.log("\n🔍 启动 Clarify Agent...");
      console.log(`📝 请求: ${params.request}`);

      const questions = await createClarifyAgent(params.request, params.context);

      console.log("✅ 意图分析完成\n");
      logSubagentEnd("clarify", questions, 1, 0, Date.now() - startTime);

      return {
        content: [{ type: "text" as const, text: questions }],
        details: { request: params.request },
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error("❌ Clarify Agent 执行失败:", errorMsg);
      logSubagentEnd("clarify", `Error: ${errorMsg}`, 0, 0, Date.now() - startTime);

      return {
        content: [{ type: "text" as const, text: `Clarify Agent 执行失败: ${errorMsg}` }],
        details: { error: errorMsg },
      };
    }
  },
};
