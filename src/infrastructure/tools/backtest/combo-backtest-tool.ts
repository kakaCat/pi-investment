/**
 * 组合策略回测工具
 *
 * 🆕 集成统一响应处理系统：回测结果自动持久化
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { comboBacktest } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

export const comboBacktestTool: ToolDefinition = {
  name: "strategy_combo_backtest",
  label: "组合策略回测",
  description:
    "多策略组合回测，支持三种模式：" +
    "1) portfolio - 仓位分配：多策略按权重分配资金独立运行；" +
    "2) ensemble - 信号融合：多策略信号加权融合后统一执行；" +
    "3) pipeline - 流程编排：策略按阶段串行执行（选股→择时→风控）。" +
    "\n\n📊 策略信号支持：" +
    "\n- 简单信号：df['buy']/df['sell']（全仓模式）" +
    "\n- 分批信号：df['buy_tier1/2/3']/df['sell_tier1/2/3']（分步建仓/止盈，最多3级）" +
    "\n组合中的每个策略可独立使用简单或分批信号。" +
    "\n\n💾 回测结果自动保存到本地文件。",

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
        details: null,
      };
    }

    if (mode === 'portfolio') {
      const totalWeight = strategies.reduce((sum: number, s: any) => sum + (s.weight || 0), 0);
      if (Math.abs(totalWeight - 1.0) > 0.01) {
        return {
          content: [{ type: "text" as const, text: `❌ 权重和必须为1，当前 ${totalWeight.toFixed(2)}` }],
          details: null,
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

      // 使用统一响应处理（自动持久化）
      return handleToolResponse({
        toolName: 'strategy_combo_backtest',
        data: result,
        formatter: _formatComboBacktestResult,
        metadata: {
          mode,
          strategy_count: strategies.length,
          symbol_count: symbols.length,
          period: `${start_date || 'auto'} ~ ${end_date || 'today'}`,
        },
        threshold: 60 * 1024, // 60KB，组合回测数据通常较大
      });
    } catch (error) {
      return createErrorResponse(error);
    }
  },
};

/**
 * 格式化组合回测结果
 */
function _formatComboBacktestResult(result: any): string {
  const lines: string[] = [];
  lines.push(`📊 组合策略回测 (${result.mode?.toUpperCase() || 'N/A'})`);
  lines.push(`期间: ${result.period?.start || 'N/A'} ~ ${result.period?.end || 'N/A'}`);
  lines.push("");

  const m = result.overall_metrics;
  if (m) {
    lines.push("🎯 整体表现:");
    lines.push(`  收益率: ${(m.total_return * 100).toFixed(2)}%`);
    lines.push(`  夏普: ${m.sharpe_ratio.toFixed(2)}`);
    lines.push(`  回撤: ${(m.max_drawdown * 100).toFixed(2)}%`);
    lines.push("");
  }

  if (result.strategy_breakdown?.length > 0) {
    lines.push("📈 策略贡献:");
    result.strategy_breakdown.forEach((s: any) => {
      const w = s.weight || s.signal_weight || 0;
      lines.push(`  ${s.strategy_name}: ${(w * 100).toFixed(0)}% | 收益 ${(s.return * 100).toFixed(2)}%`);
    });
  }

  return lines.join("\n");
}
