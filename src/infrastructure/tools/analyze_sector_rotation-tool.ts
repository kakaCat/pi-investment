import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

type SectorFlowInput = {
  name?: string;
  netInflow?: number;
  inflowPct?: number;
  changePct?: number;
  price?: number;
};

type SectorFlow = {
  name: string;
  netInflow: number;
  inflowPct: number;
  changePct: number;
  price: number;
};

const DEFAULT_SECTOR_FLOWS: SectorFlow[] = [
  { name: "人工智能", netInflow: 3_200_000_000, inflowPct: 4.2, changePct: 2.1, price: 1280 },
  { name: "半导体", netInflow: 2_450_000_000, inflowPct: 3.5, changePct: 1.7, price: 1530 },
  { name: "消费电子", netInflow: 1_680_000_000, inflowPct: 2.6, changePct: 1.3, price: 980 },
  { name: "医药", netInflow: -920_000_000, inflowPct: -1.4, changePct: -0.8, price: 860 },
  { name: "地产", netInflow: -1_860_000_000, inflowPct: -2.7, changePct: -1.9, price: 640 },
  { name: "煤炭", netInflow: -2_580_000_000, inflowPct: -3.4, changePct: -2.2, price: 720 },
];

function normalizeSector(input: SectorFlowInput): SectorFlow {
  return {
    name: typeof input.name === "string" && input.name.trim() ? input.name.trim() : "未知行业",
    netInflow: Number.isFinite(input.netInflow) ? Number(input.netInflow) : 0,
    inflowPct: Number.isFinite(input.inflowPct) ? Number(input.inflowPct) : 0,
    changePct: Number.isFinite(input.changePct) ? Number(input.changePct) : 0,
    price: Number.isFinite(input.price) ? Number(input.price) : 0,
  };
}

function formatYi(value: number): string {
  const yi = value / 1e8;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)}亿`;
}

function detectRotationStage(
  topGainers: SectorFlow[],
  topDecliners: SectorFlow[],
): string {
  const totalInflow = topGainers.reduce((sum, item) => sum + Math.max(item.netInflow, 0), 0);
  const totalOutflow = Math.abs(
    topDecliners.reduce((sum, item) => sum + Math.min(item.netInflow, 0), 0),
  );

  if (totalInflow > 0 && totalOutflow > 0) {
    const ratio = totalInflow / totalOutflow;
    if (ratio >= 1.8) return "强势轮动";
    if (ratio >= 1.1) return "温和轮动";
    if (ratio <= 0.6) return "防御轮动";
    return "分化轮动";
  }

  if (totalInflow > 0) return "普涨轮动";
  if (totalOutflow > 0) return "普跌轮动";
  return "无明显轮动";
}

export const analyze_sector_rotationTool: ToolDefinition = {
  name: "analyze_sector_rotation",
  label: "analyze_sector_rotation",
  description: "分析当前市场的行业轮动趋势",
  parameters: Type.Object({
    days: Type.Optional(
      Type.Number({
        description: "分析周期天数，默认 5 天",
        minimum: 1,
        maximum: 30,
      }),
    ),
    sectorFlows: Type.Optional(
      Type.Array(
        Type.Object({
          name: Type.Optional(Type.String({ description: "行业名称" })),
          netInflow: Type.Optional(Type.Number({ description: "主力净流入金额" })),
          inflowPct: Type.Optional(Type.Number({ description: "资金流入占比" })),
          changePct: Type.Optional(Type.Number({ description: "行业涨跌幅" })),
          price: Type.Optional(Type.Number({ description: "行业指数或价格" })),
        }),
        { description: "行业资金流数据" },
      ),
    ),
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const days = Number.isFinite(params?.days) ? Number(params.days) : 5;
      const rawFlows = Array.isArray(params?.sectorFlows) && params.sectorFlows.length > 0
        ? params.sectorFlows
        : DEFAULT_SECTOR_FLOWS;

      const sectors = rawFlows.map((item: SectorFlowInput) => normalizeSector(item));
      const sorted = [...sectors].sort((a, b) => b.netInflow - a.netInflow);
      const topGainers = sorted.slice(0, Math.min(5, sorted.length));
      const topDecliners = [...sorted].slice(-Math.min(5, sorted.length)).reverse();

      const strongInflow = topGainers.filter(
        (item) => item.netInflow > 0 && item.inflowPct >= 2,
      );
      const strongOutflow = topDecliners.filter(
        (item) => item.netInflow < 0 && item.inflowPct <= -2,
      );

      const signals: string[] = [];
      if (strongInflow.length > 0) {
        signals.push(`强势流入: ${strongInflow.map((item) => item.name).join("、")}`);
      }
      if (strongOutflow.length > 0) {
        signals.push(`强势流出: ${strongOutflow.map((item) => item.name).join("、")}`);
      }
      if (
        strongInflow.filter((item) => item.changePct > 0).length >= 2 &&
        strongOutflow.filter((item) => item.changePct < 0).length >= 2
      ) {
        signals.push("轮动格局明确: 强势行业上涨且弱势行业下跌");
      }

      const rotationStage = detectRotationStage(topGainers, topDecliners);
      const advice: string[] = [];
      if (strongInflow.length > 0) {
        advice.push(`关注 ${strongInflow.map((item) => item.name).join("、")} 等资金持续流入方向。`);
      }
      if (strongOutflow.length > 0) {
        advice.push(`谨慎对待 ${strongOutflow.map((item) => item.name).join("、")} 等资金持续流出方向。`);
      }
      if (advice.length === 0) {
        advice.push("当前轮动信号不明显，建议结合指数趋势和个股基本面进一步确认。");
      }

      const lines: string[] = [];
      lines.push(`# 行业轮动分析 (近${days}日)`);
      lines.push(`轮动阶段: ${rotationStage}`);
      lines.push("");
      lines.push("资金流入TOP5:");
      topGainers.forEach((item, index) => {
        lines.push(
          `${index + 1}. ${item.name} | 净流入 ${formatYi(item.netInflow)} | 流入占比 ${item.inflowPct.toFixed(2)}% | 涨跌幅 ${item.changePct >= 0 ? "+" : ""}${item.changePct.toFixed(2)}%`,
        );
      });
      lines.push("");
      lines.push("资金流出TOP5:");
      topDecliners.forEach((item, index) => {
        lines.push(
          `${index + 1}. ${item.name} | 净流入 ${formatYi(item.netInflow)} | 流入占比 ${item.inflowPct.toFixed(2)}% | 涨跌幅 ${item.changePct >= 0 ? "+" : ""}${item.changePct.toFixed(2)}%`,
        );
      });
      if (signals.length > 0) {
        lines.push("");
        lines.push("轮动信号:");
        signals.forEach((signal) => lines.push(`- ${signal}`));
      }
      lines.push("");
      lines.push("建议:");
      advice.forEach((item) => lines.push(`- ${item}`));

      return {
        content: [{ type: "text" as const, text: lines.join("\n") }],
        details: {
          days,
          rotationStage,
          topGainers,
          topDecliners,
          signals,
          advice,
          sectorCount: sectors.length,
          usedDefaultData: rawFlows === DEFAULT_SECTOR_FLOWS,
        },
      };
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `行业轮动分析失败: ${error instanceof Error ? error.message : String(error)}`,
          },
        ],
        details: {
          days: 5,
          rotationStage: "无明显轮动",
          topGainers: [],
          topDecliners: [],
          signals: [],
          advice: ["参数异常，未能完成分析。"],
          sectorCount: 0,
          usedDefaultData: true,
        },
      };
    }
  },
};