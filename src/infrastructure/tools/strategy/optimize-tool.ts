/**
 * strategy_optimize 工具
 *
 * 策略参数优化 - 调用 v2 真实回测 API
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";

interface OptimizeResult {
  strategy_id: string | number;
  symbol: string;
  metric: string;
  total_combinations: number;
  successful: number;
  best: {
    params: Record<string, unknown>;
    score: number;
    total_return?: number;
    sharpe_ratio?: number;
    max_drawdown?: number;
    win_rate?: number;
  };
  top10?: Array<{
    params: Record<string, unknown>;
    score: number;
  }>;
}

export const strategyOptimizeTool: ToolDefinition = {
  name: "strategy_optimize",
  label: "策略参数优化",
  description:
    "策略参数优化 - 使用网格搜索找到最优参数组合。" +
    "对给定策略在指定标的和时间段进行参数优化，返回最优参数和回测指标。" +
    "支持多种优化目标：sharpe（夏普比率）、return（总收益）、win_rate（胜率）、calmar（卡玛比率）。",

  parameters: Type.Object({
    strategy_id: Type.Union([Type.Integer(), Type.String()], {
      description: "策略ID（数据库中的策略记录ID，支持数字或字符串）",
    }),
    symbol: Type.String({
      description: "股票代码，如 600519.SH",
    }),
    param_grid: Type.Record(Type.String(), Type.Array(Type.Unknown()), {
      description:
        '参数网格，JSON 对象，键为参数名，值为参数候选值数组。' +
        '例如：{"rsi_low": [25, 30, 35], "rsi_high": [65, 70, 75]}',
    }),
    start_date: Type.Optional(
      Type.String({
        description: "回测开始日期，格式 YYYY-MM-DD，默认 2025-01-01",
      })
    ),
    end_date: Type.Optional(
      Type.String({
        description: "回测结束日期，格式 YYYY-MM-DD，默认当前日期",
      })
    ),
    metric: Type.Optional(
      Type.Union(
        [
          Type.Literal("sharpe"),
          Type.Literal("return"),
          Type.Literal("win_rate"),
          Type.Literal("calmar"),
        ],
        {
          description: "优化目标指标，默认 sharpe",
        }
      )
    ),
    initial_capital: Type.Optional(
      Type.Number({
        description: "初始资金，默认 1000000",
      })
    ),
    max_combinations: Type.Optional(
      Type.Integer({
        description: "最大参数组合数限制，默认 50",
      })
    ),
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      // 参数验证
      if (!params?.strategy_id) {
        return {
          content: [{
            type: "text" as const,
            text: "错误：缺少必需参数 strategy_id"
          }],
          details: undefined
        };
      }
      if (!params?.symbol) {
        return {
          content: [{
            type: "text" as const,
            text: "错误：缺少必需参数 symbol"
          }],
          details: undefined
        };
      }
      if (!params?.param_grid) {
        return {
          content: [{
            type: "text" as const,
            text: "错误：缺少必需参数 param_grid"
          }],
          details: undefined
        };
      }

      // 准备请求参数（v2 API 使用 camelCase）
      const payload: any = {
        strategyId: params.strategy_id,
        symbol: params.symbol,
        startDate: params.start_date || "2025-01-01",
        endDate: params.end_date || new Date().toISOString().split("T")[0],
        sortBy: params.metric || "sharpe_ratio",
        paramRanges: params.param_grid,
        initialCash: params.initial_capital || 1000000,
      };

      if (params.max_combinations) {
        payload.maxCombinations = params.max_combinations;
      }

      // 直接调用 v2 API
      const url = `${process.env.QUANTSYS_V2_API_URL || "http://127.0.0.1:5001"}/api/strategies/optimize`;

      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(300000), // 优化可能需要较长时间（5分钟）
      });

      if (!response.ok) {
        const text = await response.text().catch(() => "");
        return {
          content: [{
            type: "text" as const,
            text: `❌ HTTP ${response.status}: ${text || response.statusText}`
          }],
          details: undefined
        };
      }

      const rawResult = (await response.json()) as {
        success: boolean;
        results?: Array<{
          params: Record<string, unknown>;
          sharpeRatio?: number;
          totalReturn?: number;
          maxDrawdown?: number;
          winRate?: number;
          totalTrades?: number;
        }>;
        totalCombinations?: number;
        successfulCombinations?: number;
        error?: string;
      };

      if (!rawResult.success || !rawResult.results || rawResult.results.length === 0) {
        return {
          content: [{
            type: "text" as const,
            text: `❌ 优化失败: ${rawResult.error || "无有效参数组合"}`
          }],
          details: undefined
        };
      }

      // 将 camelCase API 响应转换为 OptimizeResult
      const best = rawResult.results[0]!;
      const data: OptimizeResult = {
        strategy_id: params.strategy_id,
        symbol: params.symbol,
        metric: params.metric || "sharpe",
        total_combinations: rawResult.totalCombinations ?? rawResult.results.length,
        successful: rawResult.successfulCombinations ?? rawResult.results.length,
        best: {
          params: best.params,
          score: best.sharpeRatio ?? 0,
          total_return: best.totalReturn,
          sharpe_ratio: best.sharpeRatio,
          max_drawdown: best.maxDrawdown,
          win_rate: best.winRate,
        },
        top10: rawResult.results.slice(0, 10).map((r, i) => ({
          params: r.params,
          score: r.sharpeRatio ?? i,  // fallback to index if no sharpe
        })),
      };

      // 格式化输出
      const formattedText = formatOptimizeResult(data);
      return {
        content: [{
          type: "text" as const,
          text: formattedText
        }],
        details: data
      };

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);

      // 检查是否是连接失败
      if (errorMsg.includes('fetch failed') || errorMsg.includes('ECONNREFUSED')) {
        return {
          content: [{
            type: "text" as const,
            text: (
              "❌ quantsys-v2 后端未启动\n\n" +
              "请先启动后端服务：\n" +
              "  cd quantsys-v2 && python start_all.py\n\n" +
              "或单独启动 REST API：\n" +
              "  cd quantsys-v2 && python api/server.py"
            )
          }],
          details: undefined
        };
      }

      return {
        content: [{
          type: "text" as const,
          text: `❌ 优化失败: ${errorMsg}`
        }],
        details: undefined
      };
    }
  },
};

function formatOptimizeResult(data: OptimizeResult): string {
  const lines: string[] = [];

  lines.push("✅ 策略参数优化完成\n");
  lines.push(`策略ID: ${data.strategy_id}`);
  lines.push(`标的: ${data.symbol}`);
  lines.push(`优化指标: ${data.metric}`);
  lines.push(`参数组合数: ${data.total_combinations} (成功: ${data.successful})\n`);

  // 最优参数
  lines.push("🏆 最优参数:");
  for (const [key, value] of Object.entries(data.best.params)) {
    lines.push(`  ${key}: ${value}`);
  }
  lines.push("");

  // 回测指标
  lines.push("📊 回测指标:");
  lines.push(`  评分: ${data.best.score.toFixed(2)}`);

  if (data.best.total_return !== undefined) {
    lines.push(`  总收益: ${(data.best.total_return * 100).toFixed(2)}%`);
  }
  if (data.best.sharpe_ratio !== undefined) {
    lines.push(`  Sharpe: ${data.best.sharpe_ratio.toFixed(2)}`);
  }
  if (data.best.max_drawdown !== undefined) {
    lines.push(`  最大回撤: ${(data.best.max_drawdown * 100).toFixed(2)}%`);
  }
  if (data.best.win_rate !== undefined) {
    lines.push(`  胜率: ${(data.best.win_rate * 100).toFixed(2)}%`);
  }

  // Top N 结果
  if (data.top10 && data.top10.length > 1) {
    lines.push("");
    lines.push(`📈 Top ${Math.min(data.top10.length, 5)} 参数组合:`);
    for (let i = 0; i < Math.min(data.top10.length, 5); i++) {
      const item = data.top10[i]!;
      const paramsStr = Object.entries(item.params)
        .map(([k, v]) => `${k}=${v}`)
        .join(", ");
      lines.push(`  ${i + 1}. ${paramsStr} (评分: ${item.score.toFixed(2)})`);
    }
  }

  return lines.join("\n");
}
