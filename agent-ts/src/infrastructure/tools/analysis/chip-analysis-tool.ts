/**
 * Chip Analysis Tool - 筹码分布（成本分布）分析工具
 *
 * 调用 quantsys-v2 GET /api/analysis/chip-distribution/{symbol}，返回：
 * 获利盘比例、平均持仓成本、90%/70% 成本区间、最大密集峰价位、集中度，
 * 以及当前价相对密集峰的位置解读（上方套牢压力/下方支撑）。
 *
 * 何时使用：
 * - 评估个股持仓成本结构：谁在赚钱、谁被套、支撑压力在哪
 * - 博弈分析：获利盘>90% 警惕兑现压力，<10% 可能是恐慌出清后的机会
 * - 集中度低（<0.1）说明筹码集中，变盘概率大
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

function pct(v: number | null | undefined): string {
  return v == null ? "未知" : `${(v * 100).toFixed(1)}%`;
}

function formatChip(data: any): string {
  if (data.error) return `筹码分布查询失败：${data.error}`;
  const m = data.metrics ?? {};
  const lines: string[] = [
    `筹码分布 ${data.symbol}（截至 ${data.asOf}，现价 ${data.close}）：`,
    `获利盘比例 ${pct(m.profitRatio)}｜平均成本 ${m.avgCost ?? "未知"}`,
    `90% 成本区间 [${m.cost90Low ?? "?"}, ${m.cost90High ?? "?"}]｜70% 区间 [${m.cost70Low ?? "?"}, ${m.cost70High ?? "?"}]`,
    `最大密集峰价位 ${m.peakPrice ?? "未知"}｜集中度 ${m.concentration ?? "未知"}（越小越集中）`,
  ];
  if (m.profitRatio != null && data.close != null && m.peakPrice != null) {
    if (m.profitRatio > 0.9) {
      lines.push("解读：获利盘 >90%，兑现压力大，追高需谨慎。");
    } else if (m.profitRatio < 0.1) {
      lines.push("解读：获利盘 <10%，大量筹码套牢，反弹抛压重；若基本面无恶化，可能是恐慌出清后的左侧机会。");
    }
    if (data.close > m.peakPrice * 1.05) {
      lines.push(`现价高于密集峰 ${m.peakPrice} 超 5%，上方套牢压力已部分消化。`);
    } else if (data.close < m.peakPrice * 0.95) {
      lines.push(`现价低于密集峰 ${m.peakPrice} 超 5%，密集峰构成反弹阻力。`);
    }
  }
  return lines.join("\n");
}

export const chipAnalysisTool: ToolDefinition = {
  name: "chip_analysis",
  label: "筹码分布分析",
  description: "筹码分布（成本分布）分析：获利盘比例、平均持仓成本、90%/70% 成本区间、最大密集峰价位、集中度，以及现价相对密集峰的支撑/压力解读。用于评估持仓成本结构和博弈位置。",
  parameters: Type.Object({
    symbol: Type.String({ description: "股票代码，如 600519 或 600519.SH" }),
  }),
  execute: async (_toolCallId: string, params: any) => {
    if (!params.symbol) {
      return {
        content: [{ type: "text" as const, text: "缺少必填参数: symbol" }],
        details: { success: false, error: "MISSING_SYMBOL" },
      };
    }
    try {
      const response = await runQuantV2("analysis.chipDistribution", { symbol: params.symbol });
      return handleToolResponse({
        toolName: "chip_analysis",
        data: (response as any).data ?? response,
        formatter: (data) => (typeof data === "string" ? data : formatChip(data)),
        metadata: { params },
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text" as const, text: `筹码分布分析失败: ${errorMsg}` }],
        details: { success: false, error: errorMsg },
      };
    }
  },
};
