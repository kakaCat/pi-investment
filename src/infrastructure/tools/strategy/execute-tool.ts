/**
 * Strategy Execute Tool — 统一策略执行
 *
 * 支持三种执行模式：
 * - single: 单股票执行，返回详细信号和风险参数
 * - batch: 批量执行，返回汇总统计
 * - pipeline: 完整流水线（信号生成 → 风控筛选 → 订单创建）
 *
 * 从 quant_cli 的 strategy.execute 提取为独立工具，
 * 包含市场风格检测和格式化输出逻辑。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../quant/quant-v2-client.js";
import {
  formatSingleSignal,
  formatBatchSignals,
  formatPipelineResult,
} from "../../quant/formatters.js";

interface ExecuteParams {
  action: "single" | "batch" | "pipeline";
  strategy: string;
  symbol?: string;
  symbols?: string[];
  params?: Record<string, unknown>;
  risk_check?: boolean;
  auto_order?: boolean;
}

// ── 市场风格名称映射 ──

const STYLE_NAMES: Record<string, string> = {
  momentum: "动量市",
  oscillation: "震荡市",
  low_volatility: "低波市",
  value: "价值市",
  mixed_market: "混合市场",
  unknown: "未知市场",
};

/**
 * 查询当前市场风格及策略权重调整（静默失败）
 */
async function detectMarketStyle(
  strategyName: string
): Promise<{ market_style: string; weight_adjustment: number; style_recommendation: string } | null> {
  try {
    const baseUrl = process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001";

    const marketStyleResponse = await fetch(`${baseUrl}/api/market/style`, {
      signal: AbortSignal.timeout(5_000),
    });
    if (!marketStyleResponse.ok) return null;

    const marketStyleData = (await marketStyleResponse.json()) as any;
    if (!marketStyleData.success || !marketStyleData.data) return null;

    const marketStyle = marketStyleData.data.style;

    const weightResponse = await fetch(
      `${baseUrl}/api/strategies/${strategyName}/weight?market_style=${marketStyle}`,
      { signal: AbortSignal.timeout(5_000) }
    );

    if (!weightResponse.ok) return null;

    const weightData = (await weightResponse.json()) as any;
    if (!weightData.success || !weightData.data) return null;

    const styleName = STYLE_NAMES[marketStyle] || marketStyle;
    return {
      market_style: marketStyle,
      weight_adjustment: weightData.data.weight_adjustment,
      style_recommendation: `当前为${styleName}，策略权重调整为${weightData.data.weight_adjustment.toFixed(2)}`,
    };
  } catch {
    // 市场风格查询失败不影响主流程
    return null;
  }
}

export const strategyExecuteTool: ToolDefinition = {
  name: "strategy_execute",
  label: "执行策略",
  description:
    "统一策略执行工具，支持三种模式：\n" +
    "- single: 单股票执行，返回详细信号和风险参数\n" +
    "- batch: 批量执行，返回汇总统计\n" +
    "- pipeline: 完整流水线（信号生成 → 风控筛选 → 订单创建）\n\n" +
    "single 模式需要 symbol 参数；batch/pipeline 模式需要 symbols 参数。" +
    "自动集成市场风格检测，附加权重调整建议。",

  parameters: Type.Object({
    action: Type.Union(
      [
        Type.Literal("single"),
        Type.Literal("batch"),
        Type.Literal("pipeline"),
      ],
      {
        description:
          "执行模式：single=单股票, batch=批量, pipeline=完整流水线",
      }
    ),
    strategy: Type.String({
      description: "策略ID或名称",
    }),
    symbol: Type.Optional(
      Type.String({
        description: "股票代码（single 模式必填，如 600000）",
      })
    ),
    symbols: Type.Optional(
      Type.Array(Type.String(), {
        description: "股票代码列表（batch/pipeline 模式必填）",
      })
    ),
    params: Type.Optional(
      Type.Record(Type.String(), Type.Unknown(), {
        description: "策略参数覆盖（可选）",
      })
    ),
    risk_check: Type.Optional(
      Type.Boolean({
        description: "是否启用风控检查（pipeline 模式，默认 true）",
      })
    ),
    auto_order: Type.Optional(
      Type.Boolean({
        description: "是否自动创建订单（pipeline 模式，默认 false）",
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: ExecuteParams) => {
    const { action, strategy, symbol, symbols } = rawParams;

    // ── 参数校验 ──

    if (action === "single" && !symbol) {
      return {
        content: [{
          type: "text" as const,
          text: "缺少必填参数: symbol。single 模式需要指定单个股票代码。",
        }],
        details: undefined,
      };
    }

    if ((action === "batch" || action === "pipeline") && !symbols) {
      return {
        content: [{
          type: "text" as const,
          text: `缺少必填参数: symbols。${action} 模式需要指定股票列表。`,
        }],
        details: undefined,
      };
    }

    try {
      // ── 执行策略 ──
      const response = await runQuantV2(
        "strategy.execute",
        rawParams as unknown as Record<string, unknown>
      );

      // ── 市场风格检测（静默） ──
      const marketStyleInfo = await detectMarketStyle(strategy);

      // ── 格式化输出 ──
      let formattedText: string;

      if (action === "single") {
        formattedText = formatSingleSignal(response as any);
      } else if (action === "batch") {
        formattedText = formatBatchSignals(response as any);
      } else if (action === "pipeline") {
        formattedText = formatPipelineResult(response as any);
      } else {
        formattedText = JSON.stringify(response, null, 2);
      }

      // ── 附加市场风格信息 ──
      if (marketStyleInfo) {
        formattedText += `\n\n【市场风格分析】\n${marketStyleInfo.style_recommendation}`;
      }

      const enrichedResponse = marketStyleInfo
        ? { ...response, ...marketStyleInfo }
        : response;

      return {
        content: [{ type: "text" as const, text: formattedText }],
        details: enrichedResponse,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `策略执行失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
