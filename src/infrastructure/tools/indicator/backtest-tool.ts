/**
 * Indicator Backtest Tool — 指标回测（集成统一持久化）
 *
 * 对指定指标（indicator_id）在指定股票和时间段上运行回测，
 * 返回权益曲线、交易记录和摘要指标（收益率、夏普比率、最大回撤等）。
 *
 * 从 quant_cli 的 indicators.backtest 提取为独立工具，
 * 提升可发现性和参数类型安全。
 *
 * 🆕 集成统一持久化：使用 handleToolResponse 自动格式化和持久化大数据
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";
import { formatBacktestResult } from "../../adapters/quant/formatters.js";

interface BacktestParams {
  indicator_id: number;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_cash?: number;
  period?: string;
}

export const indicatorBacktestTool: ToolDefinition = {
  name: "indicator_backtest",
  label: "指标回测",
  description:
    "对指定指标进行历史回测，返回权益曲线、交易记录和摘要指标（收益率、夏普比率、最大回撤等）。" +
    "需要提供 indicator_id（可通过 indicator_list 查询可用指标）。" +
    "支持 A 股。港股数据暂不可用。" +
    "\n\n📊 回测支持两种策略类型：" +
    "\n1️⃣ 简单信号策略（全仓模式）：每次买入/卖出使用全部资金/持仓" +
    "\n2️⃣ 分批信号策略（分步建仓/止盈）：支持最多3级买入和3级卖出" +
    "\n   - 买入：按 buy_tier1_pct/buy_tier2_pct/buy_tier3_pct 分配资金" +
    "\n   - 卖出：按 sell_tier1_pct/sell_tier2_pct/sell_tier3_pct 减仓或全清" +
    "\n   - 交易记录会包含 tiers 字段，显示每个批次的明细（买入价、股数、盈亏）" +
    "\n\n💾 大数据自动保存到本地文件，避免污染上下文。",

  parameters: Type.Object({
    indicator_id: Type.Integer({
      description: "指标ID（可通过 indicator_list 查询）",
      minimum: 1,
    }),
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）或港股（如 9988）",
    }),
    start_date: Type.String({
      description: "回测开始日期，格式 YYYY-MM-DD（如 2025-01-01）",
    }),
    end_date: Type.String({
      description: "回测结束日期，格式 YYYY-MM-DD（如 2026-05-31）",
    }),
    initial_cash: Type.Optional(
      Type.Number({
        description: "初始资金。默认: 1000000",
        minimum: 10000,
      })
    ),
    period: Type.Optional(
      Type.String({
        description: "K线周期。不传=日线, '5min'/'15min'/'30min'/'60min'=分钟线（分钟线自动启用T+1约束）",
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: BacktestParams) => {
    try {
      const result = await runQuantV2("indicators.backtest", rawParams as unknown as Record<string, unknown>);
      const data = result.data ?? result;

      // 使用统一的响应处理器（自动格式化和持久化）
      return handleToolResponse({
        toolName: 'indicator_backtest',
        data,
        formatter: formatBacktestResult,
        metadata: {
          indicator_id: rawParams.indicator_id,
          symbol: rawParams.symbol,
          start_date: rawParams.start_date,
          end_date: rawParams.end_date,
          initial_cash: rawParams.initial_cash || 1000000,
          period: rawParams.period || 'daily',
        },
        threshold: 30 * 1024, // 30KB
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `指标回测失败: ${errorMsg}`,
        }],
        details: null,
      };
    }
  },
};
