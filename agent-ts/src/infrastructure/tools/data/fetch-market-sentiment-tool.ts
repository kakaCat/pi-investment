/**
 * Data Fetch Market Sentiment Tool - L1 数据管道层
 *
 * 获取市场整体情绪分析数据。
 *
 * 【分析维度】
 * - 恐慌/贪婪指数：综合市场情绪指标
 * - 涨跌比：上涨股票数 / 下跌股票数
 * - 成交量：市场活跃度
 * - 强弱指标：多空力量对比
 * - 情绪评级：极度恐慌、恐慌、中性、贪婪、极度贪婪
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { wrapToolExecution } from "../shared/error-handler.js";
import { handleToolResponse, snakeize } from "../utils/index.js";

interface SentimentData {
  sentiment_score?: number;
  sentiment_level?: string;
  fear_greed_index?: number;
  market_phase?: string;
  recommendation?: string;
  degraded?: boolean;
  degraded_dimensions?: Array<{ dimension: string; reason: string }>;
  indicators?: {
    advance_decline?: {
      data_date?: string;
      up_count?: number;
      down_count?: number;
      flat_count?: number;
      ratio?: number;
      up_percentage?: number;
      error?: string;
    };
    volume?: {
      data_date?: string;
      volume_ratio?: number;
      status?: string;
      error?: string;
    };
    index_performance?: {
      data_date?: string;
      positive_count?: number;
      total_count?: number;
      avg_return_5d_pct?: number;
      market_trend?: string;
      error?: string;
    };
    volatility?: { volatility?: number; level?: string; error?: string };
    new_high_low?: {
      data_date?: string;
      new_high_count?: number;
      new_low_count?: number;
      ratio?: number;
      error?: string;
    };
  };
  [key: string]: any;
}

export const dataFetchMarketSentimentTool: ToolDefinition = {
  name: "data_fetch_market_sentiment",
  label: "获取市场情绪分析",
  description:
    "分析当前市场整体情绪，包括恐慌/贪婪指数、涨跌比、成交量等综合指标。" +
    "情绪分为5个等级：极度恐慌、恐慌、中性、贪婪、极度贪婪。" +
    "适用场景：判断市场情绪、识别超买超卖、把握反转时机、评估市场风险。",

  parameters: Type.Object({}),

  execute: async (_toolCallId, _params) => {
    try {
      // 调用 quantsys-v2 API
      const result = await runQuantV2("market.sentiment", {});

      if (!result.ok) {
        throw new Error((result as any).error || "获取市场情绪失败");
      }

      // 格式化输出并使用统一响应处理（snakeize：后端 api_response 统一 camelCase）
      const formattedOutput = formatSentimentData(snakeize<SentimentData>((result as any).data));

      return handleToolResponse({
        toolName: 'data_fetch_market_sentiment',
        data: { formattedText: formattedOutput, rawData: (result as any).data },
        formatter: (d) => d.formattedText,
        metadata: { timestamp: new Date().toISOString() },
        threshold: 10 * 1024, // 10KB (情绪数据通常较小)
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `获取市场情绪失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化市场情绪数据输出
 *
 * 契约（2026-07-28 对齐 quantsys-v2 market_sentiment_service）：
 * 指标在 indicators.* 下；维度失败时该维度含 error 且列入
 * degraded_dimensions——必须展示降级警告，不能把残缺数据当成完整判断。
 */
function formatSentimentData(data: SentimentData): string {
  if (!data) {
    return "❌ 未获取到市场情绪数据";
  }
  if (data.error) {
    return `❌ 市场情绪分析失败: ${data.error}`;
  }

  const ind = data.indicators || {};
  let output = "🎭 **市场情绪分析**\n\n";

  // 降级警告（最重要，放最前）
  if (data.degraded && data.degraded_dimensions?.length) {
    output += "⚠️ **部分维度数据不可用，以下判断基于残缺数据**：\n";
    for (const d of data.degraded_dimensions) {
      output += `- ${d.dimension}: ${d.reason}\n`;
    }
    output += "\n";
  }

  // 1. 核心指标
  output += "### 📊 核心指标\n\n";
  if (data.fear_greed_index !== undefined) {
    const index = data.fear_greed_index;
    const { level, emoji, description } = getSentimentLevel(index || 0);
    output += `**恐慌/贪婪指数**\n`;
    output += `- 数值：${emoji} **${index}** / 100\n`;
    output += `- 评级：${level}（${data.sentiment_level || '-'}）\n`;
    output += `- 说明：${description}\n\n`;
  }
  if (data.market_phase) {
    output += `**市场阶段**：${data.market_phase}\n\n`;
  }

  // 2. 涨跌统计（真实字段：up_count/down_count/flat_count）
  const ad = ind.advance_decline;
  if (ad && !ad.error && ad.up_count !== undefined) {
    output += "### 📈 涨跌统计（全市场）\n\n";
    const up = ad.up_count || 0;
    const down = ad.down_count || 0;
    const flat = ad.flat_count || 0;
    const total = up + down + flat;
    output += `| 类型 | 数量 | 占比 |\n|------|------|------|\n`;
    output += `| 上涨 | ${up} | ${((up / total) * 100).toFixed(1)}% |\n`;
    output += `| 下跌 | ${down} | ${((down / total) * 100).toFixed(1)}% |\n`;
    output += `| 平盘 | ${flat} | ${((flat / total) * 100).toFixed(1)}% |\n`;
    output += `| **涨跌比** | **${ad.ratio}** | - |\n\n`;
    output += `数据日期：${ad.data_date || '-'}\n\n`;
  }

  // 3. 成交量
  const vol = ind.volume;
  if (vol && !vol.error && vol.volume_ratio !== undefined) {
    const s = getVolumeStatus(vol.volume_ratio);
    output += "### 💹 成交量（全市场，近5日 vs 前20日）\n\n";
    output += `- **量比**：${s.emoji} ${vol.volume_ratio.toFixed(2)}（${vol.status || s.description}）\n`;
    output += `- 数据日期：${vol.data_date || '-'}\n\n`;
  }

  // 4. 市场趋势与波动率
  const trend = ind.index_performance;
  if (trend && !trend.error) {
    output += "### 📉 市场趋势（全市场等权，近5日）\n\n";
    output += `- 上涨天数：${trend.positive_count}/${trend.total_count}，5日均收益：${trend.avg_return_5d_pct}%\n`;
    output += `- 趋势：${trend.market_trend}（数据日期：${trend.data_date || '-'}）\n\n`;
  }
  const vola = ind.volatility;
  if (vola && !vola.error && vola.volatility !== undefined) {
    output += `**波动率**：${vola.volatility}%（${vola.level}）\n\n`;
  }

  // 5. 新高新低
  const nhl = ind.new_high_low;
  if (nhl && !nhl.error) {
    output += `**一年新高/新低**：${nhl.new_high_count} / ${nhl.new_low_count}（比值 ${nhl.ratio}，数据日期：${nhl.data_date || '-'}）\n\n`;
  }

  // 6. 后端建议
  if (data.recommendation) {
    output += `### 💡 综合建议\n\n${data.recommendation}\n\n`;
  }

  output += "⚠️ **风险提示**：市场情绪分析仅供参考，不构成投资建议。\n\n";

  return output;
}

/**
 * 获取情绪等级
 */
function getSentimentLevel(index: number): { level: string; emoji: string; description: string } {
  if (index <= 20) {
    return {
      level: "极度恐慌",
      emoji: "😱",
      description: "市场极度悲观，可能是抄底机会"
    };
  } else if (index <= 40) {
    return {
      level: "恐慌",
      emoji: "😰",
      description: "市场悲观情绪浓厚，风险偏好低"
    };
  } else if (index <= 60) {
    return {
      level: "中性",
      emoji: "😐",
      description: "市场情绪平稳，多空均衡"
    };
  } else if (index <= 80) {
    return {
      level: "贪婪",
      emoji: "😃",
      description: "市场乐观情绪升温，注意风险"
    };
  } else {
    return {
      level: "极度贪婪",
      emoji: "🤑",
      description: "市场过度乐观，警惕回调风险"
    };
  }
}

/**
 * 获取成交量状态
 */
function getVolumeStatus(ratio: number): { emoji: string; description: string } {
  if (ratio >= 3) {
    return { emoji: "🚀", description: "巨量放量，市场极度活跃" };
  } else if (ratio >= 2) {
    return { emoji: "📈", description: "显著放量，市场活跃" };
  } else if (ratio >= 1.5) {
    return { emoji: "📊", description: "温和放量，成交正常" };
  } else if (ratio >= 0.8) {
    return { emoji: "➡️", description: "量能平稳，成交平淡" };
  } else {
    return { emoji: "📉", description: "缩量明显，市场冷清" };
  }
}
