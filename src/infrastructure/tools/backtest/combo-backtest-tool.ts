import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { comboBacktest } from "../../adapters/quant/quant-v2-client.js";

export const comboBacktestTool: ToolDefinition = {
  name: "strategy_combo_backtest",
  label: "组合策略回测",
  description:
    "多策略组合回测，支持三种模式：" +
    "1) portfolio - 仓位分配：多策略按权重分配资金独立运行；" +
    "2) ensemble - 信号融合：多策略信号加权融合后统一执行；" +
    "3) pipeline - 流程编排：策略按阶段串行执行（选股→择时→风控）。",

  parameters: Type.Object({
    mode: Type.Union(
      [
        Type.Literal("portfolio"),
        Type.Literal("ensemble"),
        Type.Literal("pipeline"),
      ],
      { description: "组合模式" }
    ),

    strategies: Type.Array(
      Type.Object({
        strategy_id: Type.Number({ description: "策略ID" }),
        weight: Type.Optional(Type.Number({ description: "权重 0-1" })),
        stage: Type.Optional(Type.String({ description: "阶段" })),
      }),
      { description: "策略配置列表", minItems: 2 }
    ),

    symbols: Type.Array(Type.String(), { description: "股票代码列表" }),
    start_date: Type.Optional(Type.String({ description: "起始日期" })),
    end_date: Type.Optional(Type.String({ description: "结束日期" })),
    initial_capital: Type.Optional(Type.Number({ description: "初始资金" })),
    ensemble_method: Type.Optional(Type.String({ description: "融合方法" })),
  }),

  execute: async (_toolCallId: string, rawParams: any) => {
    const { mode, strategies, symbols, start_date, end_date, initial_capital, ensemble_method } = rawParams;

    if (strategies.length < 2) {
      return {
        content: [{ type: "text" as const, text: "❌ 至少需要2个策略" }],
        details: undefined,
      };
    }

    if (mode === 'portfolio') {
      const totalWeight = strategies.reduce((sum: number, s: any) => sum + (s.weight || 0), 0);
      if (Math.abs(totalWeight - 1.0) > 0.01) {
        return {
          content: [{ type: "text" as const, text: `❌ 权重和必须为1，当前 ${totalWeight.toFixed(2)}` }],
          details: undefined,
        };
      }
    }

    try {
      const result = await comboBacktest({
        mode,
        strategies,
        symbols,
        start_date,
        end_date,
        initial_capital,
        ensemble_method,
      });

      const lines: string[] = [];
      lines.push(`📊 组合策略回测 (${mode.toUpperCase()})`);
      lines.push(`期间: ${result.period.start} ~ ${result.period.end}`);
      lines.push("");

      const m = result.overall_metrics;
      lines.push("🎯 整体表现:");
      lines.push(`  收益率: ${(m.total_return * 100).toFixed(2)}%`);
      lines.push(`  夏普: ${m.sharpe_ratio.toFixed(2)}`);
      lines.push(`  回撤: ${(m.max_drawdown * 100).toFixed(2)}%`);
      lines.push("");

      if (result.strategy_breakdown?.length > 0) {
        lines.push("📈 策略贡献:");
        result.strategy_breakdown.forEach((s: any) => {
          const w = s.weight || s.signal_weight || 0;
          lines.push(`  ${s.strategy_name}: ${(w * 100).toFixed(0)}% | 收益 ${(s.return * 100).toFixed(2)}%`);
        });
      }

      return { content: [{ type: "text" as const, text: lines.join("\n") }], details: undefined };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `❌ 失败: ${error instanceof Error ? error.message : String(error)}` }],
        details: undefined,
      };
    }
  },
};
