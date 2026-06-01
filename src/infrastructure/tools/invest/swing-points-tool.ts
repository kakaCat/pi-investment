/**
 * ZigZag 波段买卖点分析工具
 *
 * 基于历史价格波动识别局部高点（卖点）和低点（买点），
 * 不依赖任何策略，纯粹根据价格的 ZigZag 走势分析。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

interface SwingPointsParams {
  symbol: string;
  start_date?: string;
  end_date?: string;
  min_change?: number;
}

function formatSwingResult(data: Record<string, unknown>): string {
  if (data.error) return `⚠️ ${data.error}`;

  const lines: string[] = [];
  const symbol = data.symbol as string;
  const period = data.period as Record<string, string>;
  const minChange = data.min_change as number;
  const klineCount = data.kline_count as number;

  lines.push(`📊 ${symbol} ZigZag 波段分析`);
  lines.push(`📅 ${period?.start} ~ ${period?.end}（${klineCount} 根K线）`);
  lines.push(`📐 最小波动阈值: ${minChange}%`);
  lines.push("");

  // 买卖点列表
  const points = (data.swing_points || []) as Array<Record<string, unknown>>;
  if (points.length > 0) {
    lines.push(`🔄 拐点列表（共 ${points.length} 个）：`);
    for (const pt of points) {
      const icon = pt.type === "low" ? "🟢买" : "🔴卖";
      const change = pt.change_pct as number;
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
      const pct = t.profit_pct as number;
      const icon = pct >= 0 ? "✅" : "❌";
      lines.push(
        `  ${i + 1}. ${icon} 买 ${t.buy_date} ¥${t.buy_price} → 卖 ${t.sell_date} ¥${t.sell_price}  ` +
          `${pct >= 0 ? "+" : ""}${pct}%  持仓${t.holding_days}天`
      );
    }
    lines.push("");
  }

  // 统计摘要
  const s = data.summary as Record<string, unknown>;
  if (s && (s.total_trades as number) > 0) {
    lines.push("📈 统计摘要：");
    lines.push(`  交易次数: ${s.total_trades}（盈${s.win_count}/亏${s.loss_count}）`);
    lines.push(`  胜率: ${s.win_rate}%`);
    lines.push(`  累计收益: ${(s.total_return as number) >= 0 ? "+" : ""}${s.total_return}%`);
    lines.push(`  平均收益: ${(s.avg_return as number) >= 0 ? "+" : ""}${s.avg_return}%`);
    lines.push(`  最大盈利: +${s.max_return}%`);
    lines.push(`  最大亏损: ${s.max_loss}%`);
    lines.push(`  平均持仓: ${s.avg_holding_days} 天`);
  }

  if (data.message) {
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
        symbol: params.symbol,
        start_date: params.start_date,
        end_date: params.end_date,
        min_change: params.min_change,
      });

      const raw = result as unknown as Record<string, unknown>;
      const data =
        raw && typeof raw === "object" && "data" in raw
          ? raw.data
          : raw;

      const text = formatSwingResult(data as Record<string, unknown>);

      return {
        content: [{ type: "text" as const, text }],
        details: undefined,
      };
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `ZigZag 波段分析失败: ${error instanceof Error ? error.message : String(error)}`,
          },
        ],
        details: undefined,
      };
    }
  },
};
