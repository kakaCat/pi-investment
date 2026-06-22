/**
 * Evolution Tool - evolution_run 工具定义
 *
 * 供 Agent 调用，手动触发进化分析流程。
 * Agent 在 npm run dev 中收到用户指令后调用此工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runWeeklyEvolution } from "../../../services/intelligence/evolution-service.js";
import { formatReportAsMarkdown } from "../../../services/intelligence/evolution-reporter.js";

export const evolutionRunTool: ToolDefinition = {
  name: "evolution_run",
  label: "运行进化分析",
  description:
    "🚀 系统自我进化引擎 — 不是复盘总结，是让 Agent 自主改进。\n\n" +
    "执行完整的自我进化循环：\n" +
    "1. 分析执行历史（会话日志、交易记录、持仓变动）→ 计算决策质量 gap\n" +
    "2. 归因分析 — 哪些工具调用低效？哪些参数需要调整？哪些决策模式有问题？\n" +
    "3. 生成优化建议 — 工具权重调整、参数调优、经验库更新、提示词改进\n" +
    "4. 自动执行可落地的建议，持久化到 .pi-invest/evolution/\n\n" +
    "何时调用：每次复盘结束后、发现 agent 决策质量下降、定期（每 N 次交易后）维护。\n" +
    "这不是「看看过去做了什么」— 这是「改变未来怎么做」。",
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
        details: null,
      };
    }
  },
};
