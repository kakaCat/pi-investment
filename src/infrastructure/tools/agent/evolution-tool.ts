/**
 * Evolution Tool - evolution_run 工具定义
 *
 * 供 Agent 调用，手动触发进化分析流程。
 * Agent 在 npm run dev 中收到用户指令后调用此工具。
 */
import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { runWeeklyEvolution } from "../../services/intelligence/evolution-service.js";
import { formatReportAsMarkdown } from "../../services/intelligence/evolution-reporter.js";

export const evolutionRunTool: ToolDefinition = {
  name: "evolution_run",
  label: "运行进化分析",
  description:
    "Run the agent evolution analysis. " +
    "Calculates performance gap, performs attribution analysis, " +
    "and generates optimization suggestions (tool adjustments, parameter tuning, experience updates). " +
    "Call this when the user wants to review the agent's performance and evolve capabilities.",
  parameters: Type.Object({}),
  execute: async (_toolCallId, _params: any) => {
    try {
      const result = await runWeeklyEvolution();
      const markdown = formatReportAsMarkdown(result.report);

      return {
        content: [{
          type: "text" as const,
          text: markdown,
        }],
        details: {
          reportPath: result.reportPath,
        },
      };
    } catch (e) {
      return {
        content: [{
          type: "text" as const,
          text: `进化分析失败: ${e instanceof Error ? e.message : String(e)}`,
        }],
        details: undefined,
      };
    }
  },
};
