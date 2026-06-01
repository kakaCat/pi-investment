/**
 * Indicator Backtest Tool — 指标回测
 *
 * 对指定指标（indicator_id）在指定股票和时间段上运行回测，
 * 返回权益曲线、交易记录和摘要指标（收益率、夏普比率、最大回撤等）。
 *
 * 从 quant_cli 的 indicators.backtest 提取为独立工具，
 * 提升可发现性和参数类型安全。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

interface BacktestParams {
  indicator_id: number;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_cash?: number;
}

export const indicatorBacktestTool: ToolDefinition = {
  name: "indicator_backtest",
  label: "指标回测",
  description:
    "对指定指标进行历史回测，返回权益曲线、交易记录和摘要指标（收益率、夏普比率、最大回撤等）。" +
    "需要提供 indicator_id（可通过 indicator_list 查询可用指标）。" +
    "支持 A 股。港股数据暂不可用。",

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
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(result.data ?? result, null, 2),
        }],
        details: undefined,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `指标回测失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
