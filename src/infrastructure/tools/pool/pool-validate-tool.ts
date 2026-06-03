/**
 * Pool validation tool — run multi-strategy batch backtest against a stock pool.
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { validatePool } from "../../adapters/quant/quant-v2-client.js";

export const poolValidateTool: ToolDefinition = {
  name: "pool_validate",
  label: "股票池策略验证",
  description:
    "对股票池执行多策略批量回测对比：每个策略在池内所有股票上跑回测，" +
    "按综合评分(收益率40%+夏普20%+回撤15%+胜率15%+盈亏比10%)排名，" +
    "自动推荐最优策略+股票组合(top 5)。" +
    "strategy_ids为空时使用所有活跃策略，时间范围默认近6个月。",
  parameters: Type.Object({
    pool_id: Type.Number({ description: "股票池ID (必需)" }),
    strategy_ids: Type.Optional(
      Type.Array(Type.Number(), {
        description: "策略ID列表，为空则使用所有活跃策略",
      }),
    ),
    start_date: Type.Optional(
      Type.String({ description: "回测起始日期 YYYY-MM-DD (默认近6个月)" }),
    ),
    end_date: Type.Optional(
      Type.String({ description: "回测结束日期 YYYY-MM-DD (默认今天)" }),
    ),
  }),
  execute: async (_toolCallId: string, rawParams: any) => {
    const { pool_id, strategy_ids, start_date, end_date } = rawParams;

    if (!pool_id) {
      return {
        content: [{ type: "text" as const, text: "❌ 需要 pool_id 参数" }],
        details: undefined,
      };
    }

    try {
      const resp = await validatePool(pool_id, {
        strategy_ids,
        start_date,
        end_date,
      });
      const data = resp?.data ?? resp;
      const text = _formatValidation(data);
      return { content: [{ type: "text" as const, text }], details: undefined };
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `❌ 验证失败: ${error instanceof Error ? error.message : String(error)}`,
          },
        ],
        details: undefined,
      };
    }
  },
};

function _formatValidation(data: any): string {
  if (!data) return "验证完成（无数据）";

  const lines: string[] = [];
  lines.push(`📊 策略验证结果: ${data.pool_name || `Pool #${data.pool_id}`}`);
  lines.push(
    `  验证期间: ${data.period?.start} ~ ${data.period?.end}`,
  );
  lines.push(
    `  测试: ${data.strategies_tested} 个策略 × ${data.stocks_in_pool} 只股票`,
  );
  lines.push("");

  // Best strategy
  const best = data.best_strategy;
  if (best) {
    lines.push(`🏆 最优策略: ${best.name || `#${best.strategy_id}`}`);
    lines.push(
      `  综合评分: ${best.score} | 平均收益: ${best.avg_return}% | 胜率: ${best.avg_win_rate}% | 夏普: ${best.avg_sharpe}`,
    );
    lines.push("");
  }

  // Rankings table
  const rankings = data.rankings || [];
  if (rankings.length > 0) {
    lines.push("📈 策略排名:");
    lines.push("  排名 | 策略名称 | 评分 | 收益% | 胜率% | 夏普");
    lines.push("  " + "-".repeat(60));
    rankings.forEach((r: any, i: number) => {
      lines.push(
        `  ${String(i + 1).padStart(2)}   | ${(r.name || `#${r.strategy_id}`).padEnd(16)} | ${String(r.score).padStart(5)} | ${String(r.avg_return).padStart(6)} | ${String(r.avg_win_rate).padStart(5)} | ${String(r.avg_sharpe).padStart(5)}`,
      );
    });
    lines.push("");
  }

  // Recommended pairs
  const pairs = data.recommended_pairs || [];
  if (pairs.length > 0) {
    lines.push("💡 推荐组合 (最优策略 + 最佳股票):");
    pairs.forEach((p: any, i: number) => {
      lines.push(
        `  ${i + 1}. ${p.symbol} — 预期收益: ${p.expected_return}% | 胜率: ${p.win_rate}% | 夏普: ${p.sharpe}`,
      );
    });
  }

  return lines.join("\n");
}
