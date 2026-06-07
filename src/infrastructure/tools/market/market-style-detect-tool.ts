/**
 * Market Style Detect Tool - 市场风格检测工具
 *
 * 自动识别当前市场风格：
 * - 牛市（Bull Market）
 * - 熊市（Bear Market）
 * - 震荡市（Sideways Market）
 *
 * 应用场景：
 * - 策略自适应：根据市场风格切换策略
 * - 风险控制：熊市降低仓位
 * - 择时交易：牛市加仓，熊市减仓
 * - 风格轮动：价值vs成长风格切换
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface MarketStyleParams {
  lookback_days?: number;
}

interface MarketStyleResult {
  current_style?: string;
  confidence?: number;
  trend_slope?: number;
  volatility?: number;
  momentum_score?: number;
  support_level?: number;
  resistance_level?: number;
  recommendation?: string;
  style_history?: Array<{
    date: string;
    style: string;
  }>;
  [key: string]: any;
}

export const marketStyleDetectTool: ToolDefinition = {
  name: "market_style_detect",
  label: "市场风格检测",
  description:
    "自动检测当前市场风格（牛市/熊市/震荡市），提供趋势分析和投资建议。" +
    "基于多维度指标综合判断：趋势斜率、波动率、动量、成交量等。" +
    "适用场景：策略自适应、风险控制、择时交易、风格轮动。",

  parameters: Type.Object({
    lookback_days: Type.Optional(Type.Integer({
      description: "回溯天数，用于计算趋势。默认：60天",
      minimum: 20,
      maximum: 252
    }))
  }),

  execute: async (_toolCallId, params: MarketStyleParams) => {
    try {
      const { lookback_days = 60 } = params;

      // 调用 quantsys-v2 API
      const result = await runQuantV2("market.style", {
        lookback_days
      });

      if (!result.ok) {
        const errorMsg = typeof result.error === 'string'
          ? result.error
          : result.error?.message || "市场风格检测失败";
        throw new Error(errorMsg);
      }

      // 格式化输出
      const formattedOutput = formatMarketStyleResult(
        result.data as MarketStyleResult,
        lookback_days
      );

      return {
        content: [{
          type: "text" as const,
          text: formattedOutput
        }],
        details: result.data
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 市场风格检测失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化市场风格结果
 */
function formatMarketStyleResult(
  data: MarketStyleResult,
  lookbackDays: number
): string {
  if (!data) {
    return "❌ 未获取到市场风格数据";
  }

  let output = "📊 **市场风格检测报告**\n\n";

  // 分析周期
  output += `### 分析周期\n\n`;
  output += `- **回溯天数**：${lookbackDays}天\n`;
  output += `- **分析日期**：${new Date().toISOString().split('T')[0]}\n\n`;

  // 当前市场风格
  if (data.current_style) {
    output += `### 🎯 当前市场风格\n\n`;

    const styleInfo = getStyleInfo(data.current_style);
    const confidence = data.confidence ? (data.confidence * 100).toFixed(1) : '未知';

    output += `**市场风格**：${styleInfo.emoji} **${styleInfo.name}**\n`;
    output += `**置信度**：${confidence}%\n`;
    output += `**特征**：${styleInfo.description}\n\n`;
  }

  // 市场指标
  output += `### 📈 市场指标\n\n`;
  output += "| 指标 | 数值 | 解读 |\n";
  output += "|------|------|------|\n";

  if (data.trend_slope !== undefined) {
    const slope = (data.trend_slope * 100).toFixed(2);
    const trendDesc = getTrendDescription(data.trend_slope);
    output += `| 趋势斜率 | ${slope}% | ${trendDesc} |\n`;
  }

  if (data.volatility !== undefined) {
    const vol = (data.volatility * 100).toFixed(2);
    const volDesc = getVolatilityDescription(data.volatility);
    output += `| 波动率 | ${vol}% | ${volDesc} |\n`;
  }

  if (data.momentum_score !== undefined) {
    const momentum = data.momentum_score.toFixed(2);
    const momentumDesc = getMomentumDescription(data.momentum_score);
    output += `| 动量评分 | ${momentum} | ${momentumDesc} |\n`;
  }

  output += "\n";

  // 支撑阻力位
  if (data.support_level !== undefined || data.resistance_level !== undefined) {
    output += `### 📍 关键位置\n\n`;

    if (data.support_level !== undefined) {
      output += `- **支撑位**：${data.support_level.toFixed(2)} 点\n`;
    }

    if (data.resistance_level !== undefined) {
      output += `- **阻力位**：${data.resistance_level.toFixed(2)} 点\n`;
    }

    output += "\n";
  }

  // 投资建议
  if (data.recommendation || data.current_style) {
    output += `### 💡 投资建议\n\n`;

    if (data.recommendation) {
      output += `${data.recommendation}\n\n`;
    } else if (data.current_style) {
      const advice = getStyleAdvice(data.current_style);
      output += advice.map(a => `- ${a}`).join('\n');
      output += "\n\n";
    }
  }

  // 策略建议
  if (data.current_style) {
    output += `### 🎲 策略建议\n\n`;
    const strategies = getRecommendedStrategies(data.current_style);
    output += `**适合策略**：\n`;
    output += strategies.map(s => `- ${s}`).join('\n');
    output += "\n\n";
  }

  // 风格历史
  if (data.style_history && data.style_history.length > 0) {
    output += `### 📅 风格历史（最近10次变化）\n\n`;
    output += "| 日期 | 市场风格 |\n";
    output += "|------|----------|\n";

    const recentHistory = data.style_history.slice(-10);
    for (const record of recentHistory) {
      const styleInfo = getStyleInfo(record.style);
      output += `| ${record.date} | ${styleInfo.emoji} ${styleInfo.name} |\n`;
    }

    output += "\n";
  }

  // 风险提示
  output += `⚠️ **风险提示**：市场风格检测基于历史数据和统计模型，不能预测未来。投资需谨慎。\n`;

  return output;
}

/**
 * 获取市场风格信息
 */
function getStyleInfo(style: string): { name: string; emoji: string; description: string } {
  const styleMap: Record<string, { name: string; emoji: string; description: string }> = {
    "bull": {
      name: "牛市",
      emoji: "🐂",
      description: "持续上涨，市场乐观，适合做多"
    },
    "bear": {
      name: "熊市",
      emoji: "🐻",
      description: "持续下跌，市场悲观，注意风险"
    },
    "sideways": {
      name: "震荡市",
      emoji: "↔️",
      description: "横盘整理，市场观望，适合区间操作"
    },
    "bull_correction": {
      name: "牛市回调",
      emoji: "📉",
      description: "上涨趋势中的短期调整，可逢低吸纳"
    },
    "bear_rally": {
      name: "熊市反弹",
      emoji: "📈",
      description: "下跌趋势中的短期反弹，谨慎参与"
    },
    "volatile": {
      name: "高波动市",
      emoji: "⚡",
      description: "波动剧烈，风险较高，控制仓位"
    }
  };

  return styleMap[style.toLowerCase()] || {
    name: style,
    emoji: "❓",
    description: "未知市场风格"
  };
}

/**
 * 获取趋势描述
 */
function getTrendDescription(slope: number): string {
  if (slope > 0.05) return "🔥 强势上涨";
  if (slope > 0.02) return "📈 温和上涨";
  if (slope > -0.02) return "➡️ 横盘整理";
  if (slope > -0.05) return "📉 温和下跌";
  return "❄️ 快速下跌";
}

/**
 * 获取波动率描述
 */
function getVolatilityDescription(volatility: number): string {
  if (volatility > 0.03) return "⚡ 高波动";
  if (volatility > 0.02) return "🌊 中等波动";
  if (volatility > 0.01) return "➡️ 低波动";
  return "🔒 极低波动";
}

/**
 * 获取动量描述
 */
function getMomentumDescription(momentum: number): string {
  if (momentum > 0.7) return "🚀 动量强劲";
  if (momentum > 0.3) return "📈 动量积极";
  if (momentum > -0.3) return "➡️ 动量中性";
  if (momentum > -0.7) return "📉 动量疲软";
  return "❄️ 动量极弱";
}

/**
 * 获取风格投资建议
 */
function getStyleAdvice(style: string): string[] {
  const adviceMap: Record<string, string[]> = {
    "bull": [
      "✅ **积极做多**：逢低买入，持股待涨",
      "✅ **追涨策略**：动量策略有效，可适度追涨",
      "✅ **加大仓位**：在风控允许范围内提高仓位",
      "⚠️ **注意过热**：关注估值泡沫，避免盲目追高"
    ],
    "bear": [
      "⚠️ **降低仓位**：减少持股，保留现金",
      "⚠️ **防守为主**：优先配置防御性板块（消费、医药）",
      "⚠️ **严格止损**：设置止损线，控制损失",
      "💡 **等待机会**：观察市场筑底信号，准备抄底"
    ],
    "sideways": [
      "💡 **区间操作**：低买高卖，赚取波段收益",
      "💡 **短线为主**：缩短持仓周期，快进快出",
      "💡 **均衡配置**：分散投资，降低单一品种风险",
      "⚠️ **避免追涨杀跌**：横盘市容易震荡出局"
    ],
    "bull_correction": [
      "✅ **逢低加仓**：回调是加仓良机",
      "💡 **保持耐心**：短期调整不改上涨趋势",
      "✅ **持股为主**：避免频繁交易"
    ],
    "bear_rally": [
      "⚠️ **谨慎参与**：反弹不是反转",
      "💡 **快进快出**：赚取短期收益后及时离场",
      "⚠️ **不宜重仓**：反弹高度有限"
    ],
    "volatile": [
      "⚠️ **控制仓位**：降低单次交易规模",
      "⚠️ **扩大止损**：给予更大波动空间",
      "💡 **波段操作**：利用波动赚取差价"
    ]
  };

  return adviceMap[style.toLowerCase()] || [
    "💡 建议根据个股基本面和技术面综合判断",
    "⚠️ 注意风险控制，设置合理止损"
  ];
}

/**
 * 获取推荐策略
 */
function getRecommendedStrategies(style: string): string[] {
  const strategyMap: Record<string, string[]> = {
    "bull": [
      "**动量策略**：追涨强势股",
      "**成长股策略**：配置高成长板块（科技、新能源）",
      "**突破策略**：突破前高买入"
    ],
    "bear": [
      "**防御策略**：配置消费、医药等防御性板块",
      "**价值股策略**：寻找低估值、高股息股票",
      "**空仓策略**：保留现金，等待机会"
    ],
    "sideways": [
      "**网格交易**：设置网格，低买高卖",
      "**均值回归策略**：超卖买入，超买卖出",
      "**短线套利**：捕捉日内波动"
    ],
    "bull_correction": [
      "**逢低买入策略**：回调到支撑位加仓",
      "**分批建仓**：避免一次性满仓"
    ],
    "bear_rally": [
      "**反弹策略**：快进快出，不恋战",
      "**日内交易**：赚取日内波动"
    ],
    "volatile": [
      "**波段交易**：利用大幅波动",
      "**对冲策略**：降低风险暴露"
    ]
  };

  return strategyMap[style.toLowerCase()] || [
    "根据市场情况灵活调整"
  ];
}
