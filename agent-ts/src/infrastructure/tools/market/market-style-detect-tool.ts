/**
 * Market Style Detect Tool - 市场风格检测工具
 *
 * 自动识别当前市场风格轮动状态：
 * - 价值（value）：银行/地产/高股息领涨
 * - 成长（growth）：科技/新能源/高ROE领涨
 * - 周期（cycle）：煤炭/钢铁/大宗商品领涨
 *
 * 后端契约（quantsys-v2 /api/market/style，api_response 统一 camelCase）：
 *   { style, confidence, scores: {value,growth,cycle},
 *     indicators: { bankingPerformance, techPerformance, cyclePerformance,
 *                   marketVolumeChange, marketVolatility },
 *     recommendedFactors: string[], detectionDate }
 *
 * 应用场景：
 * - 策略自适应：根据市场风格切换策略
 * - 风格轮动：价值vs成长vs周期切换
 * - 因子配置：按推荐因子调整选股权重
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface MarketStyleParams {
  lookback_days?: number;
}

interface MarketStyleIndicators {
  bankingPerformance?: number;   // 银行板块涨幅 %
  techPerformance?: number;      // 科技板块涨幅 %
  cyclePerformance?: number;     // 周期板块涨幅 %
  marketVolumeChange?: number;   // 成交量变化 %
  marketVolatility?: number;     // 市场波动率（小数）
  [key: string]: any;
}

interface MarketStyleResult {
  style?: string;                          // value / growth / cycle
  confidence?: number;                     // 0-1
  scores?: Record<string, number>;         // 各风格评分
  indicators?: MarketStyleIndicators;
  recommendedFactors?: string[];           // camelCase（FastAPI api_response）
  recommended_factors?: string[];          // snake_case 兜底
  detectionDate?: string;
  detection_date?: string;
  [key: string]: any;
}

export const marketStyleDetectTool: ToolDefinition = {
  name: "market_style_detect",
  label: "市场风格检测",
  description:
    "自动检测当前市场风格（价值/成长/周期轮动），给出各风格评分、板块指标与推荐因子。" +
    "适用场景：策略自适应、风格轮动、因子权重调整。",

  parameters: Type.Object({
    lookback_days: Type.Optional(Type.Integer({
      description: "回溯天数，用于计算风格评分。默认：60天",
      minimum: 20,
      maximum: 252
    }))
  }),

  execute: async (_toolCallId: string, params: MarketStyleParams) => {
    try {
      const { lookback_days = 60 } = params;

      // 调用 quantsys-v2 API
      const result = await runQuantV2("market.style", {
        lookback_days
      });

      if (!result.ok) {
        const errorMsg = typeof (result as any).error === 'string'
          ? (result as any).error
          : (result as any).error?.message || "市场风格检测失败";
        throw new Error(errorMsg);
      }

      // 格式化输出
      const formattedOutput = formatMarketStyleResult(
        (result as any).data as MarketStyleResult,
        lookback_days
      );

      return {
        content: [{
          type: "text" as const,
          text: formattedOutput
        }],
        details: (result as any).data
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
  if (!data || !data.style) {
    return "❌ 未获取到市场风格数据";
  }

  let output = "📊 **市场风格检测报告**\n\n";

  // 分析周期
  output += `### 分析周期\n\n`;
  output += `- **回溯天数**：${lookbackDays}天\n`;
  output += `- **分析日期**：${data.detectionDate || data.detection_date || new Date().toISOString().split('T')[0]}\n\n`;

  // 当前市场风格
  output += `### 🎯 当前市场风格\n\n`;

  const styleInfo = getStyleInfo(data.style);
  const confidence = data.confidence !== undefined ? (data.confidence * 100).toFixed(1) : '未知';

  output += `**市场风格**：${styleInfo.emoji} **${styleInfo.name}**\n`;
  output += `**置信度**：${confidence}%\n`;
  output += `**特征**：${styleInfo.description}\n\n`;

  // 各风格评分
  if (data.scores && Object.keys(data.scores).length > 0) {
    output += `### ⚖️ 风格评分\n\n`;
    output += "| 风格 | 评分 |\n";
    output += "|------|------|\n";
    for (const [style, score] of Object.entries(data.scores)) {
      const info = getStyleInfo(style);
      output += `| ${info.emoji} ${info.name} | ${(score * 100).toFixed(1)}% |\n`;
    }
    output += "\n";
  }

  // 市场指标
  const ind = data.indicators;
  if (ind && Object.keys(ind).length > 0) {
    output += `### 📈 市场指标\n\n`;
    output += "| 指标 | 数值 | 解读 |\n";
    output += "|------|------|------|\n";

    const rows: Array<[number | undefined, string, (v: number) => string, (v: number) => string]> = [
      [ind.bankingPerformance ?? ind.banking_performance, "银行板块涨幅", v => `${v.toFixed(1)}%`, v => v > 3 ? "🏦 价值风格走强" : v < 0 ? "📉 价值板块走弱" : "➡️ 平稳"],
      [ind.techPerformance ?? ind.tech_performance, "科技板块涨幅", v => `${v.toFixed(1)}%`, v => v > 3 ? "🚀 成长风格走强" : v < 0 ? "📉 成长板块走弱" : "➡️ 平稳"],
      [ind.cyclePerformance ?? ind.cycle_performance, "周期板块涨幅", v => `${v.toFixed(1)}%`, v => v > 3 ? "⚙️ 周期风格走强" : v < 0 ? "📉 周期板块走弱" : "➡️ 平稳"],
      [ind.marketVolumeChange ?? ind.market_volume_change, "成交量变化", v => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`, v => v > 10 ? "🔥 明显放量" : v < -10 ? "🧊 明显缩量" : "➡️ 量能平稳"],
      [ind.marketVolatility ?? ind.market_volatility, "市场波动率", v => `${(v * 100).toFixed(2)}%`, getVolatilityDescription],
    ];

    for (const [value, label, fmt, desc] of rows) {
      if (value !== undefined && value !== null) {
        output += `| ${label} | ${fmt(value)} | ${desc(value)} |\n`;
      }
    }
    output += "\n";
  }

  // 推荐因子
  const factors = data.recommendedFactors || data.recommended_factors;
  if (factors && factors.length > 0) {
    output += `### 🧬 推荐因子\n\n`;
    output += factors.map(f => `- \`${f}\``).join('\n');
    output += "\n\n";
  }

  // 投资建议
  output += `### 💡 投资建议\n\n`;
  const advice = getStyleAdvice(data.style);
  output += advice.map(a => `- ${a}`).join('\n');
  output += "\n\n";

  // 策略建议
  output += `### 🎲 策略建议\n\n`;
  const strategies: string[] = getRecommendedStrategies(data.style);
  output += `**适合策略**：\n`;
  output += strategies.map(s => `- ${s}`).join('\n');
  output += "\n\n";

  // 风险提示
  output += `⚠️ **风险提示**：市场风格检测基于历史数据和统计模型，不能预测未来。投资需谨慎。\n`;

  return output;
}

/**
 * 获取市场风格信息
 */
function getStyleInfo(style: string): { name: string; emoji: string; description: string } {
  const styleMap: Record<string, { name: string; emoji: string; description: string }> = {
    "value": {
      name: "价值风格",
      emoji: "🏦",
      description: "银行/地产/高股息等低估值板块领涨，防御属性强"
    },
    "growth": {
      name: "成长风格",
      emoji: "🚀",
      description: "科技/新能源/高ROE成长股领涨，进攻属性强"
    },
    "cycle": {
      name: "周期风格",
      emoji: "⚙️",
      description: "煤炭/钢铁/有色等周期板块领涨，跟踪大宗商品景气"
    }
  };

  return styleMap[style.toLowerCase()] || {
    name: style,
    emoji: "❓",
    description: "未知市场风格"
  };
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
 * 获取风格投资建议
 */
function getStyleAdvice(style: string): string[] {
  const adviceMap: Record<string, string[]> = {
    "value": [
      "✅ **配置低估值蓝筹**：银行、保险、高股息品种",
      "✅ **重视安全边际**：优先低 PE/PB、稳定分红标的",
      "💡 **关注防御板块**：消费、公用事业相对抗跌",
      "⚠️ **回避高估值成长**：估值溢价压缩风险大"
    ],
    "growth": [
      "✅ **配置成长赛道**：科技、新能源、高ROE个股",
      "✅ **动量策略有效**：趋势延续性强，可持盈",
      "💡 **关注业绩兑现**：营收/利润增速是核心驱动",
      "⚠️ **警惕风格切换**：成长拥挤度高时注意回撤"
    ],
    "cycle": [
      "✅ **跟踪商品景气**：煤炭、钢铁、有色跟随大宗价格",
      "💡 **波段操作为主**：周期股波动大，不宜长持",
      "⚠️ **严格择时**：周期顶部杀伤力大，设好止损",
      "💡 **关注宏观信号**：PPI、库存周期决定持续性"
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
    "value": [
      "**高股息策略**：筛选股息率高、分红稳定的标的",
      "**低估值修复**：PE/PB 历史低分位 + 基本面稳健",
      "**防御配置策略**：消费、医药、公用事业"
    ],
    "growth": [
      "**动量策略**：追涨强势股",
      "**成长股策略**：配置高营收/利润增速板块",
      "**突破策略**：突破前高买入"
    ],
    "cycle": [
      "**波段交易策略**：利用周期股大波动",
      "**商品联动策略**：跟踪期货价格做对应股票",
      "**均值回归策略**：周期底部超卖买入"
    ]
  };

  return strategyMap[style.toLowerCase()] || [
    "根据市场情况灵活调整"
  ];
}
