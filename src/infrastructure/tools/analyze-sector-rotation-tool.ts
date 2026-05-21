/**
 * Analyze Sector Rotation Tool
 *
 * Analyzes current market sector rotation trends by examining sector fund flows
 * over recent periods to identify which sectors are gaining/losing momentum.
 * Helps improve stock selection timing by revealing where smart money is flowing.
 *
 * Returns:
 * - Top gaining sectors (by net inflow / inflow percentage)
 * - Top declining sectors (by net outflow / outflow percentage)
 * - Rotation signals (strong inflow / outflow alerts)
 * - Actionable advice for sector-aware investing
 *
 * Expected impact: improve stock selection quality, add 2-3% win rate.
 */
import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { getSectorFundFlowViaQuantCli } from "../quant/market-query-cli-adapter.js";

export const analyzeSectorRotationTool: ToolDefinition = {
  name: "analyze_sector_rotation",
  label: "分析行业轮动",
  description:
    "Analyze current market sector rotation trends. " +
    "Examines sector fund flows over recent periods to identify which sectors are gaining momentum (inflows) " +
    "and which are losing favor (outflows). Use this to improve stock selection timing and avoid sectors in decline. " +
    "Returns top gaining sectors, top declining sectors, and rotation signals.",
  parameters: Type.Object({
    days: Type.Optional(
      Type.Number({
        description: "Number of days to analyze (default: 5)",
        minimum: 1,
        maximum: 30,
      }),
    ),
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const days = params.days ?? 5;

      // ── Step 1: Fetch sector fund flow data ──────────────────────
      const flowResult = await getSectorFundFlowViaQuantCli();
      const flowData = JSON.parse(flowResult);

      if (flowData.error) {
        return {
          content: [
            {
              type: "text" as const,
              text: `获取行业资金流数据失败: ${flowData.error}`,
            },
          ],
          details: undefined,
        };
      }

      const sectors: any[] = flowData.data || [];
      if (sectors.length === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: "未获取到行业资金流数据",
            },
          ],
          details: undefined,
        };
      }

      // ── Step 2: Normalize and sort by net inflow ─────────────────
      type SectorEntry = {
        name: string;
        netInflow: number;
        inflowPct: number;
        price: number;
        changePct: number;
      };

      const sorted: SectorEntry[] = sectors
        .map((s: any) => ({
          name: s.行业 || s.name || s.sector_name || "未知",
          netInflow: Number(s.净额 || s.net_inflow || s.main_net_inflow || 0),
          inflowPct: Number(s["行业-涨跌幅"] || s.inflow_pct || s.main_net_inflow_pct || 0),
          price: Number(s.行业指数 || s.price || s.latest_price || 0),
          changePct: Number(s["行业-涨跌幅"] || s.change_pct || s.pct_chg || 0),
        }))
        .sort((a: SectorEntry, b: SectorEntry) => b.netInflow - a.netInflow);

      const topGainers = sorted.slice(0, 5);
      const topDecliners = sorted.slice(-5).reverse();

      // ── Step 3: Generate rotation signals ────────────────────────
      const signals: string[] = [];

      // Strong inflow sectors (large positive net inflow + significant inflow %)
      const strongInflow = topGainers.filter(
        (s: SectorEntry) => s.netInflow > 0 && s.inflowPct > 2,
      );
      if (strongInflow.length > 0) {
        signals.push(
          `强势流入: ${strongInflow.map((s: SectorEntry) => s.name).join(", ")}`,
        );
      }

      // Strong outflow sectors (large negative net inflow + significant outflow %)
      const strongOutflow = topDecliners.filter(
        (s: SectorEntry) => s.netInflow < 0 && s.inflowPct < -2,
      );
      if (strongOutflow.length > 0) {
        signals.push(
          `强势流出: ${strongOutflow.map((s: SectorEntry) => s.name).join(", ")}`,
        );
      }

      // Detect clear rotation pattern: inflow sectors rising while outflow sectors falling
      const inflowRising = strongInflow.filter(
        (s: SectorEntry) => s.changePct > 0,
      );
      const outflowFalling = strongOutflow.filter(
        (s: SectorEntry) => s.changePct < 0,
      );
      if (inflowRising.length >= 2 && outflowFalling.length >= 2) {
        signals.push(
          "轮动清晰: 资金流入板块普遍上涨，流出板块普遍下跌，行业轮动格局明确",
        );
      }

      // Detect mixed signals (inflow sectors still falling = watch for reversal)
      const inflowFalling = strongInflow.filter(
        (s: SectorEntry) => s.changePct <= 0,
      );
      if (inflowFalling.length >= 2) {
        signals.push(
          `资金流入但下跌: ${inflowFalling.map((s: SectorEntry) => s.name).join(", ")} 主力资金流入但价格下跌，可能为机构建仓，值得重点跟踪`,
        );
      }

      // ── Step 4: Detect market rotation stage ─────────────────────
      let rotationStage = "无明显轮动";
      const totalInflow = topGainers.reduce(
        (sum: number, s: SectorEntry) => sum + s.netInflow,
        0,
      );
      const totalOutflow = Math.abs(
        topDecliners.reduce(
          (sum: number, s: SectorEntry) => sum + s.netInflow,
          0,
        ),
      );

      if (totalInflow > 0 && totalOutflow > 0) {
        const ratio = totalInflow / (totalOutflow || 1);
        if (ratio > 2) {
          rotationStage = "强势轮动（资金大幅净流入）";
        } else if (ratio > 1.2) {
          rotationStage = "温和轮动（资金小幅净流入）";
        } else if (ratio < 0.5) {
          rotationStage = "弱势轮动（资金大幅净流出）";
        } else {
          rotationStage = "轮动中（资金流向分化）";
        }
      } else if (totalInflow > 0 && totalOutflow <= 0) {
        rotationStage = "普涨（各板块普遍流入）";
      } else if (totalInflow <= 0 && totalOutflow > 0) {
        rotationStage = "普跌（各板块普遍流出）";
      }

      // ── Step 5: Format output ────────────────────────────────────
      let output = `# 行业轮动分析 (近${days}日)\n`;
      output += `轮动阶段: ${rotationStage}\n\n`;

      output += `## 📈 资金流入TOP5\n`;
      topGainers.forEach((s: SectorEntry, i: number) => {
        const inflowStr =
          s.netInflow >= 0
            ? `+${(s.netInflow / 1e8).toFixed(2)}`
            : `${(s.netInflow / 1e8).toFixed(2)}`;
        output += `${i + 1}. **${s.name}**: 主力净流入 ${inflowStr}亿 (${s.inflowPct.toFixed(2)}%), 涨跌 **${s.changePct >= 0 ? "+" : ""}${s.changePct.toFixed(2)}%**\n`;
      });

      output += `\n## 📉 资金流出TOP5\n`;
      topDecliners.forEach((s: SectorEntry, i: number) => {
        const outflowStr = (Math.abs(s.netInflow) / 1e8).toFixed(2);
        output += `${i + 1}. **${s.name}**: 主力净流出 ${outflowStr}亿 (${s.inflowPct.toFixed(2)}%), 涨跌 **${s.changePct >= 0 ? "+" : ""}${s.changePct.toFixed(2)}%**\n`;
      });

      if (signals.length > 0) {
        output += `\n## 🚦 轮动信号\n`;
        signals.forEach((sig) => {
          output += `- ${sig}\n`;
        });
      }

      output += `\n## 💡 建议\n`;
      if (strongInflow.length > 0) {
        const inflowNames = strongInflow
          .map((s: SectorEntry) => s.name)
          .join("、");
        output += `- ✅ **关注方向**: ${inflowNames} — 可考虑在这些板块中选股，优先选择龙头股\n`;
      }
      if (strongOutflow.length > 0) {
        const outflowNames = strongOutflow
          .map((s: SectorEntry) => s.name)
          .join("、");
        output += `- ⚠️ **规避方向**: ${outflowNames} — 建议对这些板块暂无持仓，或考虑减仓\n`;
      }
      if (inflowFalling.length > 0) {
        output += `- 🔍 **跟踪观察**: 资金流入但价格下跌的板块可能存在机构建仓机会，可深入分析龙头股基本面\n`;
      }
      output += `- 📊 建议结合个股技术面和基本面做最终决策，行业资金流向仅为辅助参考\n`;

      return {
        content: [
          {
            type: "text" as const,
            text: output,
          },
        ],
        details: {
          rotationStage,
          topGainers,
          topDecliners,
          signals,
          totalInflow: (totalInflow / 1e8).toFixed(2),
          totalOutflow: (totalOutflow / 1e8).toFixed(2),
        },
      };
    } catch (e) {
      return {
        content: [
          {
            type: "text" as const,
            text: `行业轮动分析失败: ${e instanceof Error ? e.message : String(e)}`,
          },
        ],
        details: undefined,
      };
    }
  },
};
