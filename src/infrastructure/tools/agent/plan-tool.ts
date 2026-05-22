/**
 * Plan Tool - 独立的规划 Agent 工具
 *
 * 当主 Agent 遇到复杂任务时，调用此工具启动独立的 Plan Agent
 * Plan Agent 负责探索代码库、分析需求、生成结构化计划
 */
import { Type } from "@sinclair/typebox";
import { createPlanAgent } from "../../../services/plan/plan-agent.js";
import { logSubagentStart, logSubagentEnd } from "../../logging/observable-logger.js";
import type { ToolDefinition } from "../index.js";
import { getBootstrapData } from "../../../config/config.js";

let availableTools: ToolDefinition[] = [];

export function setPlanToolContext(tools: ToolDefinition[]) {
  availableTools = tools;
}

export const planTool = {
  name: "plan_task",
  label: "任务规划",
  description:
    "THINKING TOOL — reason about user intent and produce a structured execution plan before doing any work. " +
    "Use at the start of any non-trivial task: ambiguous requests, multi-step work, tasks touching multiple files, or anything where the right approach is unclear. " +
    "The plan agent explores the codebase and clarifies what needs to happen, in what order, and why. " +
    "Do NOT skip this for complex tasks hoping to figure it out along the way — planning first prevents wasted effort and wrong assumptions. " +
    "Do NOT confuse with task_create: plan_task is for thinking and deciding the approach; task_create is for recording and tracking steps after the plan is set.",
  parameters: Type.Object({
    task: Type.String({ description: "Task to plan — describe the goal clearly; more detail yields a better plan" }),
    context: Type.Optional(Type.String({ description: "Optional context: relevant file paths, constraints, or background information" }))
  }),
  execute: async (_toolCallId: string, params: { task: string; context?: string }) => {
    const startTime = Date.now();
    const prompt = `${params.task}${params.context ? `\n\n上下文: ${params.context}` : ''}`;

    logSubagentStart('plan', prompt);

    try {
      console.log("\n🎯 启动 Plan Agent...");
      console.log(`📋 任务: ${params.task}`);

      const toolsForPlan = availableTools.map(t => ({
        name: t.name,
        description: t.description
      }));

      const plan = await createPlanAgent(params.task, params.context, toolsForPlan, getBootstrapData());

      console.log("✅ 计划生成完成\n");

      logSubagentEnd('plan', plan, 1, 0, Date.now() - startTime);

      return {
        content: [{
          type: "text" as const,
          text: `${plan}

---
⚠️ NEXT ACTION REQUIRED: Call task_create with ALL steps listed above before executing anything.`
        }],
        details: { task: params.task, context: params.context }
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error("❌ Plan Agent 执行失败:", errorMsg);

      logSubagentEnd('plan', `Error: ${errorMsg}`, 0, 0, Date.now() - startTime);

      return {
        content: [{
          type: "text" as const,
          text: `Plan Agent 执行失败: ${errorMsg}`
        }],
        details: { error: errorMsg }
      };
    }
  }
};
