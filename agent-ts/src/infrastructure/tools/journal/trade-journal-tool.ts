/**
 * Trade Journal Tool - 统一交易簿记入口
 *
 * decision_record / experience_write / trade_monitor / daily_report
 * 本质是同一件事的四个切面，合并为一个工具四个 action，
 * 减少工具表面积，降低 LLM 选错工具的概率。
 *
 * 过渡期：旧工具仍保留注册（兼容存量 prompt），新 prompt 一律用本工具。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { decisionRecordTool } from "../decision/decision-record-tool.js";
import { experienceWriteTool } from "../agent/experience-write-tool.js";
import { tradeMonitorTool } from "../trade/trade-monitor-tool.js";
import { dailyReportTool } from "../report/daily-report-tool.js";

const ACTIONS = ["record", "experience", "status", "daily_report"] as const;
type JournalAction = typeof ACTIONS[number];

const DISPATCH: Record<JournalAction, ToolDefinition> = {
  record: decisionRecordTool,
  experience: experienceWriteTool,
  status: tradeMonitorTool,
  daily_report: dailyReportTool,
};

export const tradeJournalTool: ToolDefinition = {
  name: "trade_journal",
  label: "交易簿记",
  description:
    "统一交易簿记入口（替代 decision_record / experience_write / trade_monitor / daily_report 四个工具）。" +
    "\n\n四个 action：" +
    "\n  • record：记录一条决策（交易/放弃信号/不交易），参数同 decision_record" +
    "\n  • experience：写经验库（有效模式/教训），参数同 experience_write" +
    "\n  • status：交易监控与统计，参数同 trade_monitor" +
    "\n  • daily_report：生成每日报告，参数同 daily_report" +
    "\n\n何时用哪个：" +
    "\n  成交后服务端已自动记账，你只需在'放弃信号/选择不交易'时 record；" +
    "\n  复盘发现可复用模式时 experience；查交易统计用 status。",

  parameters: Type.Object({
    action: Type.Union(
      ACTIONS.map(a => Type.Literal(a)) as [any, any, any, any],
      { description: "record=决策记录 | experience=写经验 | status=交易监控 | daily_report=每日报告" }
    ),
    params: Type.Optional(Type.Object({}, {
      description: "透传给对应子工具的参数（同 decision_record/experience_write/trade_monitor/daily_report 的参数）",
      additionalProperties: true,
    })),
  }),

  execute: async (toolCallId: string, input: { action: JournalAction; params?: any }) => {
    const target = input.action && DISPATCH[input.action];
    if (!target) {
      const msg = `未知或不支持的 action: ${input.action ?? "（缺失）"}，合法 action：${ACTIONS.join(" / ")}`;
      return {
        content: [{ type: "text" as const, text: msg }],
        details: { success: false, error: msg },
      };
    }
    return target.execute(toolCallId, input.params ?? {});
  }
};
