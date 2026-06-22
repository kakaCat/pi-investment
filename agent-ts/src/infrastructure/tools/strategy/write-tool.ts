/**
 * Strategy Write Tool — 策略编写
 *
 * 创建或更新交易策略代码（indicator 类型），是"写→测→迭代"工作流的第一步。
 * - 不提供 indicator_id → 创建新策略，返回 strategy_id
 * - 提供 indicator_id → 更新已有策略代码
 *
 * 创建后可用 indicator_backtest 立即回测验证。
 *
 * 从 quant_cli 的 indicators.create / indicators.update 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { createIndicator, updateIndicator } from "../../adapters/quant/quant-v2-client.js";

// ── 参数类型 ─

interface StrategyWriteParams {
  name?: string;
  code: string;
  indicator_id?: number;
  description?: string;
  category?: string;
  strategy_profile?: Record<string, unknown>;
}

// ── 工具定义 ─

export const strategyWriteTool: ToolDefinition = {
  name: "strategy_write",
  label: "写策略",
  description:
    "创建或更新交易策略（indicator 类型）。" +
    "不提供 indicator_id = 创建新策略（需 name + code）；" +
    "提供 indicator_id = 更新已有策略代码。" +
    "\n\n策略代码格式：Python 函数式指标，需定义 my_indicator_name、calc_indicator(ctx) 函数，" +
    "并在返回的 DataFrame 中设置买卖信号列。" +
    "\n\n📊 买卖信号格式（支持两种）：" +
    "\n1️⃣ 简单信号（全仓模式）：" +
    "\n   df['buy'] = condition   # 买入信号（全仓）" +
    "\n   df['sell'] = condition  # 卖出信号（全清）" +
    "\n\n2️⃣ 分批信号（分步建仓/止盈）：" +
    "\n   # 分批买入（最多3级）" +
    "\n   df['buy_tier1'] = condition1" +
    "\n   df['buy_tier1_pct'] = 0.3  # 首仓30%" +
    "\n   df['buy_tier2'] = condition2" +
    "\n   df['buy_tier2_pct'] = 0.3  # 加仓30%" +
    "\n   df['buy_tier3'] = condition3" +
    "\n   df['buy_tier3_pct'] = 0.4  # 重仓40%" +
    "\n\n   # 分批卖出（最多3级）" +
    "\n   df['sell_tier1'] = condition4" +
    "\n   df['sell_tier1_pct'] = 0.5  # 减半仓" +
    "\n   df['sell_tier2'] = condition5" +
    "\n   df['sell_tier2_pct'] = 0.3  # 再减30%" +
    "\n   df['sell_tier3'] = condition6" +
    "\n   df['sell_tier3_pct'] = 1.0  # 全清" +
    "\n\n   注意：不能混用两种格式；_pct 列可选（默认值：tier1=1.0, tier2/3=0.3）" +
    "\n\n✨ 因子库支持（104个因子）：策略执行时自动注入到 DataFrame，可直接使用。" +
    "\n常用因子：" +
    "\n  - 超买超卖: rsi14 (< 30 超卖, > 70 超买), cci (< -100 超卖), mfi14 (< 20 超卖)" +
    "\n  - 趋势强度: adx (> 25 强趋势), momentum_6m (> 0.1 强势), dmi (> 0 多头)" +
    "\n  - 波动突破: bollinger_upper/lower, atr14 (止损用), volatility_20" +
    "\n  - 成交量: volume_ratio (> 1.5 放量), obv (资金流向), vwap" +
    "\n  - 均线: ma5/ma10/ma20/ma60 (趋势), ema5/ema10 (更敏感)" +
    "\n  - 反转: reversal_5d (< -0.05 大跌), overnight_return (跳空)" +
    "\n\n示例（简单信号）: df['buy'] = (df['momentum_6m'] > 0.1) & (df['adx'] > 25) & (df['rsi14'] < 70)" +
    "\n示例（分批信号）: " +
    "\n  df['buy_tier1'] = df['rsi14'] < 30; df['buy_tier1_pct'] = 0.3  # 超卖首仓" +
    "\n  df['buy_tier2'] = (df['rsi14'] < 40) & (df['close'] < df['ma20']); df['buy_tier2_pct'] = 0.3  # 回踩加仓" +
    "\n  df['sell_tier1'] = df['rsi14'] > 70; df['sell_tier1_pct'] = 0.5  # 超买减半" +
    "\n\n完整因子列表和使用说明: docs/FACTOR_LIBRARY_REFERENCE.md（包含计算方法、数值范围、使用场景）" +
    "\n\n典型工作流：strategy_write → indicator_backtest → 调整参数 → strategy_write → indicator_backtest → ...",

  parameters: Type.Object({
    name: Type.Optional(
      Type.String({
        description: "策略名称（新建时必填，更新时可选）",
      })
    ),
    code: Type.String({
      description:
        "策略代码（Python）。需包含 calc_indicator(ctx) 函数，" +
        "通过 ctx.kline_df 获取K线，返回包含买卖信号列的 DataFrame。" +
        "\n支持两种信号格式：" +
        "\n1. 简单信号：df['buy'] 和 df['sell']（全仓模式）" +
        "\n2. 分批信号：df['buy_tier1/2/3'] 和 df['sell_tier1/2/3']（配合 _pct 列设置仓位比例）" +
        "\n不能混用两种格式。",
    }),
    indicator_id: Type.Optional(
      Type.Integer({
        description: "要更新的策略ID。不提供则创建新策略。",
        minimum: 1,
      })
    ),
    description: Type.Optional(
      Type.String({
        description: "策略描述（可选）",
      })
    ),
    category: Type.Optional(
      Type.String({
        description: "分类标签（可选，默认 'custom'）",
      })
    ),
    strategy_profile: Type.Optional(
      Type.Record(Type.String(), Type.Unknown(), {
        description: "策略画像（可选）。支持字段: tags（标签列表）, strategy_type, risk_level, market_condition, stop_loss_pct, take_profit_pct 等",
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: StrategyWriteParams) => {
    const { name, code, indicator_id, description, category, strategy_profile } = rawParams;

    // ── 代码统计（用于简化输出）──
    const codeLines = code.split('\n').length;
    const codeChars = code.length;
    const codePreview = code.split('\n').slice(0, 3).join('\n') + (codeLines > 3 ? '\n...' : '');

    try {
      if (indicator_id !== undefined) {
        // ── 更新已有策略 ──
        const result = await updateIndicator(indicator_id, {
          code,
          name,
          description,
          category,
          strategy_profile,
        });

        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(
                {
                  action: "update",
                  indicator_id,
                  name: name || result.data?.name,
                  code_stats: {
                    lines: codeLines,
                    chars: codeChars,
                    preview: codePreview,
                  },
                  success: result.success,
                  message: result.message,
                  hint: "已更新。用 indicator_backtest 验证新代码。",
                },
                null,
                2
              ),
            },
          ],
          details: null,
        };
      } else {
        // ── 创建新策略 ──
        if (!name) {
          return {
            content: [
              {
                type: "text" as const,
                text: "创建策略需要 name 参数。如需更新已有策略，请提供 indicator_id。",
              },
            ],
            details: null,
          };
        }

        const result = await createIndicator({
          name,
          code,
          description,
          category,
        });

        const strategyId = result.data?.strategy_id;
        const valid = result.data?.validation?.valid;
        const hasBuy = result.data?.validation?.has_buy_signal;
        const hasSell = result.data?.validation?.has_sell_signal;
        const validationError = result.data?.validation?.error;

        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(
                {
                  action: "create",
                  strategy_id: strategyId,
                  name,
                  code_stats: {
                    lines: codeLines,
                    chars: codeChars,
                    preview: codePreview,
                  },
                  validation: {
                    valid,
                    has_buy_signal: hasBuy,
                    has_sell_signal: hasSell,
                    error: validationError || null,
                  },
                  success: result.success,
                  message: result.message,
                  hint: valid
                    ? "创建成功。用 indicator_backtest({ indicator_id: " +
                      strategyId +
                      ", ... }) 验证。"
                    : "代码验证失败，策略已保存但标记为无效。请修正后更新。",
                },
                null,
                2
              ),
            },
          ],
          details: null,
        };
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [
          {
            type: "text" as const,
            text: `策略写入失败: ${errorMsg}`,
          },
        ],
        details: null,
      };
    }
  },
};
