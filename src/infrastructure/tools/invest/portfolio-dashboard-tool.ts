/**
 * V2 组合仪表盘工具
 *
 * 聚合 quantsys-v2 的组合/风控数据，提供一站式组合分析视图。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";

const V2_BASE = "http://127.0.0.1:5001";

export const portfolioDashboardTool: ToolDefinition = {
  name: "portfolio_dashboard",
  label: "组合仪表盘",
  description:
    "组合仪表盘：一站式查看组合全貌。\n" +
    "- positions: 持仓明细（代码/名称/数量/成本/现价/盈亏）\n" +
    "- summary: 组合汇总（总资产/总市值/现金/总盈亏/盈亏比例/盈亏股数）\n" +
    "- history: 历史权益曲线\n" +
    "- allocation: 仓位分配图\n" +
    "- risk: 组合风控报告（集中度/波动率/最大回撤/VaR）\n" +
    "默认 action='summary' 快速查看。",
  parameters: Type.Object({
    action: Type.Optional(Type.String({
      description: "视图: 'summary'(汇总), 'positions'(持仓), 'history'(历史), 'allocation'(分配), 'risk'(风控), 默认summary",
    })),
  }),
  execute: async (_toolCallId: string, rawParams: any) => {
    const action = rawParams?.action ?? "summary";

    const endpoints: Record<string, string> = {
      summary:    `${V2_BASE}/api/portfolio/summary`,
      positions:  `${V2_BASE}/api/portfolio/positions`,
      history:    `${V2_BASE}/api/portfolio/history`,
      allocation: `${V2_BASE}/api/portfolio/allocation`,
      risk:       `${V2_BASE}/api/risk/check`,
    };

    const url = endpoints[action];
    if (!url) {
      return { content: [{ type: "text" as const, text: `不支持的视图: ${action}。支持: summary, positions, history, allocation, risk` }], details: undefined };
    }

    try {
      const resp = await fetch(action === "risk"
        ? `${V2_BASE}/api/risk/check`
        : url,
        {
          method: action === "risk" ? "POST" : "GET",
          headers: action === "risk" ? { "Content-Type": "application/json" } : undefined,
          body: action === "risk" ? JSON.stringify({}) : undefined,
          signal: AbortSignal.timeout(30_000),
        },
      );

      const result = await resp.json();

      return {
        content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
        details: undefined,
      };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `组合仪表盘查询失败: ${error instanceof Error ? error.message : String(error)}` }],
        details: undefined,
      };
    }
  },
};
