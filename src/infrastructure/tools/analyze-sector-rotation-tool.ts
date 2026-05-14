/**
 * Analyze Sector Rotation Tool
 *
 * Analyzes current market sector rotation trends by examining sector fund flows.
 * Helps identify which sectors are gaining/losing momentum for better stock selection.
 */
import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { callPython } from "./invest-tools.js";

export const analyzeSectorRotationTool: ToolDefinition = {
  name: "analyze_sector_rotation",
  label: "分析行业轮动",
  description:
    "Analyze current market sector rotation trends. " +
    "Examines sector fund flows over recent periods to identify which sectors are gaining momentum (inflows) " +
    "and which are losing favor (outflows). Use this to improve stock selection timing and avoid sectors in decline. " +
    "Returns top gaining sectors, top declining sectors, and rotation signals.",
  parameters: Type.Object({
    days: Type.Optional(Type.Number({
      description: "Number of days to analyze (default: 5)",
      minimum: 1,
      maximum: 30,
    })),
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const days = params.days ?? 5;

      // Fetch sector fund flow data
      const flowResult = await callPython("get_sector_fund_flow", {});
      const flowData = JSON.parse(flowResult);

      if (flowData.error) {
        return {
          content: [{
            type: "text" as const,
            text: `获取行业资金流数据失败: ${flowData.error}`,
          }],
          details: undefined,
        };
      }

      // Parse and analyze sector flows
      const sectors = flowData.data || [];
      if (sectors.length === 0) {
        return {
          content: [{
            type: "text" as const,
            text: "未获取到行业资金流数据",
          }],
          details: undefined,
        };
      }

      // Sort by net inflow
      const sorted = sectors
        .map((s: any) => ({
          name: s.name || s.sector_name || "未知",
          netInflow: Number(s.net_inflow || s.main_net_inflow || 0),
          inflowPct: Number(s.inflow_pct || s.main_net_inflow_pct || 0),
          price: Number(s.price || s.latest_price || 0),
          changePct: Number(s.change_pct || s.pct_chg || 0),
        }))
        .sort((a, b) => b.netInflow - a.netInflow);

      const topGainers = sorted.slice(0, 5);
      const topDecliners = sorted.slice(-5).reverse();

      // Generate rotation signals
      const signals: string[] = [];

      // Strong inflow sectors
      const strongInflow = topGainers.filter(s => s.netInflow > 0 && s.inflowPct > 2);
      if (strongInflow.length > 0) {
        signals.push(`强势流入: ${strongInflow.map(s => s.name).join(", ")}`);
      }

      // Strong outflow sectors
      const strongOutflow = topDecliners.filter(s => s.netInflow < 0 && s.inflowPct < -2);
      if (strongOutflow.length > 0) {
        signals.push(`强势流出: ${strongOutflow.map(s => s.name).join(", ")}`);
      }

      // Format output
      let output = `# 行业轮动分析 (近${days}日)\n\n`;

      output += `## 资金流入TOP5\n`;
      topGainers.forEach((s, i) => {
        output += `${i + 1}. ${s.name}: 净流入 ${(s.netInflow / 1e8).toFixed(2)}亿 (${s.inflowPct.toFixed(2)}%), 涨跌 ${s.changePct.toFixed(2)}%\n`;
      });

      output += `\n## 资金流出TOP5\n`;
      topDecliners.forEach((s, i) => {
        output += `${i + 1}. ${s.name}: 净流出 ${(Math.abs(s.netInflow) / 1e8).toFixed(2)}亿 (${s.inflowPct.toFixed(2)}%), 涨跌 ${s.changePct.toFixed(2)}%\n`;
      });

      if (signals.length > 0) {
        output += `\n## 轮动信号\n`;
        signals.forEach(sig => output += `- ${sig}\n`);
      }

      output += `\n## 建议\n`;
      if (strongInflow.length > 0) {
        output += `- 关注强势流入板块的龙头股票\n`;
      }
      if (strongOutflow.length > 0) {
        output += `- 规避强势流出板块，考虑减仓相关持仓\n`;
      }

      return {
        content: [{
          type: "text" as const,
          text: output,
        }],
        details: {
          topGainers,
          topDecliners,
          signals,
        },
      };
    } catch (e) {
      return {
        content: [{
          type: "text" as const,
          text: `行业轮动分析失败: ${e instanceof Error ? e.message : String(e)}`,
        }],
        details: undefined,
      };
    }
  },
};
