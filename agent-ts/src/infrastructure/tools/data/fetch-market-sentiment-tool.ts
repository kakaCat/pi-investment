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
import { handleToolResponse } from "../utils/index.js";

interface SentimentData {
  fear_greed_index?: number;
  rise_fall_ratio?: number;
  volume_ratio?: number;
  advance_decline?: {
    advancing: number;
    declining: number;
    unchanged: number;
  };
  sentiment_level?: string;
  market_temperature?: number;
  sentiment_score?: number;
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

      // 格式化输出并使用统一响应处理
      const formattedOutput = formatSentimentData((result as any).data as SentimentData);

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
 */
function formatSentimentData(data: SentimentData): string {
  if (!data) {
    return "❌ 未获取到市场情绪数据";
  }

  let output = "🎭 **市场情绪分析**\n\n";

  // 1. 核心指标卡片
  output += "### 📊 核心指标\n\n";

  // 恐慌/贪婪指数
  if (data.fear_greed_index !== undefined) {
    const index = data.fear_greed_index;
    const { level, emoji, description } = getSentimentLevel(index);

    output += `**恐慌/贪婪指数**\n`;
    output += `- 数值：${emoji} **${index}** / 100\n`;
    output += `- 评级：${level}\n`;
    output += `- 说明：${description}\n\n`;
  }

  // 情绪等级（如果有单独字段）
  if (data.sentiment_level) {
    output += `**情绪等级**：${getSentimentEmoji(data.sentiment_level)} ${data.sentiment_level}\n\n`;
  }

  // 市场温度
  if (data.market_temperature !== undefined) {
    const temp = data.market_temperature;
    const tempStatus = getTemperatureStatus(temp);
    output += `**市场温度**：${tempStatus.emoji} ${temp}°C (${tempStatus.description})\n\n`;
  }

  // 2. 涨跌统计
  if (data.advance_decline) {
    output += "### 📈 涨跌统计\n\n";
    const { advancing, declining, unchanged } = data.advance_decline;
    const total = advancing + declining + unchanged;
    const ratio = declining > 0 ? (advancing / declining).toFixed(2) : "N/A";

    output += `| 类型 | 数量 | 占比 |\n`;
    output += `|------|------|------|\n`;
    output += `| 上涨 | ${advancing} | ${((advancing / total) * 100).toFixed(1)}% |\n`;
    output += `| 下跌 | ${declining} | ${((declining / total) * 100).toFixed(1)}% |\n`;
    output += `| 平盘 | ${unchanged} | ${((unchanged / total) * 100).toFixed(1)}% |\n`;
    output += `| **涨跌比** | **${ratio}** | - |\n\n`;

    // 涨跌比分析
    const ratioNum = parseFloat(ratio);
    if (!isNaN(ratioNum)) {
      if (ratioNum >= 2) {
        output += `💡 涨跌比 > 2，市场强势，多头占优\n\n`;
      } else if (ratioNum >= 1) {
        output += `💡 涨跌比 > 1，市场偏强，多头略占优\n\n`;
      } else if (ratioNum >= 0.5) {
        output += `💡 涨跌比 < 1，市场偏弱，空头略占优\n\n`;
      } else {
        output += `💡 涨跌比 < 0.5，市场弱势，空头占优\n\n`;
      }
    }
  }

  // 3. 成交量分析
  if (data.volume_ratio !== undefined) {
    output += "### 💹 成交量分析\n\n";
    const volumeRatio = data.volume_ratio;
    const volumeStatus = getVolumeStatus(volumeRatio);

    output += `- **量比**：${volumeStatus.emoji} ${volumeRatio.toFixed(2)}\n`;
    output += `- **状态**：${volumeStatus.description}\n\n`;
  }

  // 4. 综合判断
  output += generateSentimentSummary(data);

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
 * 获取情绪表情
 */
function getSentimentEmoji(level: string): string {
  const emojiMap: Record<string, string> = {
    "极度恐慌": "😱",
    "恐慌": "😰",
    "中性": "😐",
    "贪婪": "😃",
    "极度贪婪": "🤑"
  };
  return emojiMap[level] || "😐";
}

/**
 * 获取市场温度状态
 */
function getTemperatureStatus(temp: number): { emoji: string; description: string } {
  if (temp <= 20) {
    return { emoji: "❄️", description: "极冷，市场冰点" };
  } else if (temp <= 40) {
    return { emoji: "🥶", description: "偏冷，情绪低迷" };
  } else if (temp <= 60) {
    return { emoji: "😐", description: "温和，情绪平稳" };
  } else if (temp <= 80) {
    return { emoji: "🔥", description: "偏热，情绪活跃" };
  } else {
    return { emoji: "🌡️", description: "过热，谨防过热" };
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

/**
 * 生成综合判断
 */
function generateSentimentSummary(data: SentimentData): string {
  let output = "### 💡 综合判断\n\n";

  const index = data.fear_greed_index || 50;
  const volumeRatio = data.volume_ratio || 1;
  const advanceDecline = data.advance_decline;

  let signals: string[] = [];

  // 恐慌信号
  if (index <= 20) {
    signals.push("极度恐慌可能是抄底机会，但需确认止跌信号");
  } else if (index <= 40) {
    signals.push("市场恐慌情绪浓厚，可关注超跌优质股");
  }

  // 贪婪信号
  if (index >= 80) {
    signals.push("市场过度贪婪，建议降低仓位，控制风险");
  } else if (index >= 60) {
    signals.push("市场乐观情绪升温，注意追高风险");
  }

  // 量能信号
  if (volumeRatio >= 3) {
    signals.push("成交量放大明显，市场活跃度高");
  } else if (volumeRatio < 0.8) {
    signals.push("成交量萎缩，市场观望情绪浓厚");
  }

  // 涨跌比信号
  if (advanceDecline) {
    const ratio = advanceDecline.declining > 0
      ? advanceDecline.advancing / advanceDecline.declining
      : 0;

    if (ratio >= 2) {
      signals.push("涨跌比强势，多头占优，可积极操作");
    } else if (ratio < 0.5) {
      signals.push("涨跌比弱势，空头占优，谨慎操作");
    }
  }

  // 综合建议
  let advice = "";
  if (index <= 30 && volumeRatio < 1) {
    advice = "**建议**：市场处于底部区域，可分批建仓优质标的";
  } else if (index >= 70 && volumeRatio >= 2) {
    advice = "**建议**：市场过热，建议减仓或获利了结";
  } else if (index >= 40 && index <= 60) {
    advice = "**建议**：市场情绪中性，保持适度仓位，均衡配置";
  } else {
    advice = "**建议**：根据个股基本面和技术面，灵活操作";
  }

  if (signals.length > 0) {
    output += signals.map(s => `- ${s}`).join("\n");
    output += "\n\n";
  }

  output += `${advice}\n\n`;

  // 风险提示
  output += "⚠️ **风险提示**：市场情绪分析仅供参考，不构成投资建议。请结合基本面和技术面综合判断。\n\n";

  return output;
}
