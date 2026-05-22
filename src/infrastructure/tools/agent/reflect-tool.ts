/**
 * Reflect Tool - 执行结果回顾工具
 *
 * 真实实现位于 services/plan/reflect-agent.ts
 */
import { Type } from "@sinclair/typebox";
import { createReflectAgent } from "../../../services/plan/reflect-agent.js";
import { logSubagentStart, logSubagentEnd } from "../../logging/observable-logger.js";
import { getBootstrapData } from "../../../config/config.js";

export const reflectTool = {
  name: "reflect",
  label: "结果回顾",
  description:
    "REFLECTION TOOL — evaluate whether completed work actually achieves the user's original goal. " +
    "Use after finishing a task (or a major phase of work) to catch gaps, omissions, or misalignments before delivering the result. " +
    "Provide the user's original goal and a summary of what was done; the reflect agent returns a structured verdict with any gaps and recommended next steps. " +
    "Do NOT use as a substitute for task_list (which tracks execution) — reflect evaluates quality and goal alignment, not completion status. " +
    "Do NOT use after every small action — call it once at the end of a meaningful unit of work.",
  parameters: Type.Object({
    goal: Type.String({ description: "The user's original goal or request, as stated." }),
    outcome: Type.String({ description: "Summary of what was actually done (tasks completed, files changed, results produced)." }),
    context: Type.Optional(Type.String({ description: "Optional additional context (e.g., constraints, relevant file paths, prior decisions)." })),
  }),
  execute: async (_toolCallId: string, params: { goal: string; outcome: string; context?: string }) => {
    const startTime = Date.now();
    logSubagentStart("reflect", params.goal);

    try {
      console.log("\n🪞 启动 Reflect Agent...");
      console.log(`🎯 目标: ${params.goal}`);

      const evaluation = await createReflectAgent(params.goal, params.outcome, params.context, getBootstrapData());

      console.log("✅ 回顾评估完成\n");
      logSubagentEnd("reflect", evaluation, 1, 0, Date.now() - startTime);

      return {
        content: [{ type: "text" as const, text: evaluation }],
        details: { goal: params.goal },
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error("❌ Reflect Agent 执行失败:", errorMsg);
      logSubagentEnd("reflect", `Error: ${errorMsg}`, 0, 0, Date.now() - startTime);

      return {
        content: [{ type: "text" as const, text: `Reflect Agent 执行失败: ${errorMsg}` }],
        details: { error: errorMsg },
      };
    }
  },
};
