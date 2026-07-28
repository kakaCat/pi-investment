/**
 * ZigZag 波段买卖点分析工具
 *
 * 基于历史价格波动识别局部高点（卖点）和低点（买点），
 * 不依赖任何策略，纯粹根据价格的 ZigZag 走势分析。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/tool-response-handler.js";

interface SwingPointsParams {
  symbol: string;
  start_date?: string;
  end_date?: string;
  min_change?: number;
}

function formatSwingResult(
  data: Record<string, unknown>,
  params: SwingPointsParams
): string {
  if ((data as any).error) {
    const lines: string[] = [`⚠️ ${(data as any).error}`];

    // 后端返回的建议（代码无效提示 / 历史数据范围提示等）
    const suggestions = ((data as any).suggestions || []) as string[];
    for (const s of suggestions) {
      lines.push(`  • ${s}`);
    }

    const validation = (data as any).validation as
      | { valid?: boolean }
      | undefined;
    const codeInvalid = validation && validation.valid === false;

    if (codeInvalid) {
      // 股票代码本身无效：补数据无意义，让 agent 先修正代码
      lines.push("");
      lines.push(
        "🚫 股票代码无效，请先核对/修正股票代码（可参考上方建议），再用正确的代码重新调用本工具。不要盲目调用 data_manager 补数据。"
      );
    } else {
      // 代码有效但库里没数据：引导 agent 自愈——先补K线，再重试
      lines.push("");
      lines.push("🔧 自愈指引（请按顺序执行）：");
      lines.push(
        `  1️⃣ 调用 data_manager({ command: "update_klines", params: { symbols: "${params.symbol}", days: 400 } }) 从数据源拉取K线并入库`
      );
      lines.push(
        "  2️⃣ 补数成功后，用相同参数重新调用 analysis_swing_points 获取分析结果"
      );
      lines.push(
        "  3️⃣ 若 update_klines 也返回 0 条，说明数据源确实无此股票数据（代码错误/已退市/新股），不要再重试，直接向用户说明"
      );
    }

    return lines.join("\n");
  }

  const lines: string[] = [];
  const symbol = data.symbol as string;
  const period = data.period as Record<string, string>;
  const minChange = data.minChange as number;
  const klineCount = data.klineCount as number;

  lines.push(`📊 ${symbol} ZigZag 波段分析`);
  lines.push(`📅 ${period?.start} ~ ${period?.end}（${klineCount} 根K线）`);
  lines.push(`📐 最小波动阈值: ${minChange}%`);
  lines.push("");

  // 买卖点列表
  const points = (data.swingPoints || []) as Array<Record<string, unknown>>;
  if (points.length > 0) {
    lines.push(`🔄 拐点列表（共 ${points.length} 个）：`);
    for (const pt of points) {
      const icon = pt.type === "low" ? "🟢买" : "🔴卖";
      const change = pt.changePct as number;
      const changeStr = change > 0 ? `+${change}%` : change < 0 ? `${change}%` : "";
      lines.push(`  ${icon} ${pt.date}  ¥${pt.price}  ${changeStr}`);
    }
    lines.push("");
  }

  // 交易配对
  const trades = (data.trades || []) as Array<Record<string, unknown>>;
  if (trades.length > 0) {
    lines.push(`💰 交易配对（共 ${trades.length} 笔）：`);
    for (let i = 0; i < trades.length; i++) {
      const t = trades[i];
      const pct = t.profitPct as number;
      const icon = pct >= 0 ? "✅" : "❌";
      lines.push(
        `  ${i + 1}. ${icon} 买 ${t.buyDate} ¥${t.buyPrice} → 卖 ${t.sellDate} ¥${t.sellPrice}  ` +
          `${pct >= 0 ? "+" : ""}${pct}%  持仓${t.holdingDays}天`
      );
    }
    lines.push("");
  }

  // 统计摘要
  const s = data.summary as Record<string, unknown>;
  if (s && (s.totalTrades as number) > 0) {
    lines.push("📈 统计摘要：");
    lines.push(`  交易次数: ${s.totalTrades}（盈${s.winCount}/亏${s.lossCount}）`);
    lines.push(`  胜率: ${s.winRate}%`);
    lines.push(`  累计收益: ${(s.totalReturn as number) >= 0 ? "+" : ""}${s.totalReturn}%`);
    lines.push(`  平均收益: ${(s.avgReturn as number) >= 0 ? "+" : ""}${s.avgReturn}%`);
    lines.push(`  最大盈利: +${s.maxReturn}%`);
    lines.push(`  最大亏损: ${s.maxLoss}%`);
    lines.push(`  平均持仓: ${s.avgHoldingDays} 天`);
  }

  if ((data as any).message) {
    lines.push(`\n💡 ${data.message}`);
  }

  return lines.join("\n");
}

export const swingPointsTool: ToolDefinition = {
  name: "analysis_swing_points",
  label: "ZigZag 波段买卖点",
  description:
    "ZigZag 波段买卖点分析：根据历史价格波动（而非策略）识别局部低点（买点）和局部高点（卖点）。\n" +
    "参数 min_change 控制最小波动幅度（默认5%），值越小拐点越多，值越大只保留大波段。\n" +
    "返回拐点列表、配对交易、收益统计（胜率/累计收益/最大盈亏/平均持仓天数）。\n" +
    "适用于：了解股票历史波段特征、评估波段交易潜力、辅助制定买卖策略。",
  promptSnippet: "分析个股历史波段买卖点（ZigZag拐点）时",
  promptGuidelines: [
    '返回「K线数据不足」时：先调用 data_manager(command=update_klines, params={symbols: 代码, days: 400}) 补K线入库，成功后用相同参数重试本工具',
    '若补数据后仍为 0 条，说明数据源无此股票（代码错误/退市/新股），停止重试并向用户说明',
    '提示「股票代码无效」时：先核对修正代码，不要调用 data_manager 补数据',
  ],
  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码（如 600519 或 000001）",
    }),
    start_date: Type.Optional(
      Type.String({
        description: "开始日期（YYYY-MM-DD），默认1年前",
      })
    ),
    end_date: Type.Optional(
      Type.String({
        description: "结束日期（YYYY-MM-DD），默认今天",
      })
    ),
    min_change: Type.Optional(
      Type.Number({
        description:
          "最小波动幅度百分比（1~30），默认5。值越小拐点越多，越大只保留大波段。",
        minimum: 1,
        maximum: 30,
      })
    ),
  }),
  execute: async (_toolCallId: string, params: SwingPointsParams) => {
    try {
      const result = await runQuantV2("analysis.swing_points", {
        symbol: params.symbol!,
        start_date: params.start_date!,
        end_date: params.end_date!,
        min_change: params.min_change,
      });

      const raw = result as unknown as Record<string, unknown>;
      const data =
        raw && typeof raw === "object" && "data" in raw
          ? (raw as any).data
          : raw;

      // 每个工具自己的处理：formatSwingResult 决定 LLM 看到什么
      // （含错误分支的自愈指引）；handleToolResponse 只管管道（大小/落盘）
      return handleToolResponse({
        toolName: "analysis_swing_points",
        data,
        formatter: (d) => formatSwingResult(d, params),
        threshold: 30 * 1024,
      });
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `ZigZag 波段分析失败: ${error instanceof Error ? error.message : String(error)}`,
          },
        ],
        details: null,
      };
    }
  },
};
