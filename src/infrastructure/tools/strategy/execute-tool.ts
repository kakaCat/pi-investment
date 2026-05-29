/**
 * 策略执行工具 - 运行单个策略并返回信号（含风险管理参数）
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { executeStrategy } from "../../quant/quant-v2-client.js";
import { formatStrategySignal } from "../../quant/formatters.js";

// 策略列表缓存
let strategiesCache: Array<{
  strategyType: string;
  className: string;
  category: string;
  description: string;
}> | null = null;

/**
 * 清除策略缓存（用于测试）
 */
export function clearStrategiesCache() {
  strategiesCache = null;
}

/**
 * 获取可用策略列表（带缓存）
 */
async function getAvailableStrategies() {
  if (strategiesCache) {
    return strategiesCache;
  }

  try {
    const apiUrl = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
    const response = await fetch(`${apiUrl}/api/strategies/list?source=builtin`);

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    const data: any = await response.json();
    if (data.success && data.data?.strategies) {
      strategiesCache = data.data.strategies;
      return strategiesCache;
    }

    return [];
  } catch (error) {
    console.error('Failed to fetch strategies:', error);
    return [];
  }
}

/**
 * 格式化策略列表错误消息
 */
function formatStrategiesError(strategies: Array<{ strategyType: string; category: string; description?: string }>) {
  // 按分类分组
  const categoryMap: Record<string, string> = {
    'trend_following': '趋势跟踪',
    'mean_reversion': '均值回归',
    'volatility': '波动率',
    'multi_factor': '多因子',
    'breakout': '突破',
    'momentum': '动量'
  };

  const grouped = strategies.reduce((acc, s) => {
    const category = s.category || 'other';
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(s);
    return acc;
  }, {} as Record<string, typeof strategies>);

  let message = '策略不存在或执行失败。\n\n可用策略列表：\n\n';

  for (const [category, items] of Object.entries(grouped)) {
    const categoryName = categoryMap[category] || category;
    message += `【${categoryName}】\n`;
    for (const item of items) {
      message += `  - ${item.strategyType}`;
      if (item.description) {
        message += ` (${item.description})`;
      }
      message += '\n';
    }
    message += '\n';
  }

  return message;
}

export const strategyExecuteTool: ToolDefinition = {
  name: "strategy_execute",
  label: "执行策略",
  description:
    "执行单个量化策略，返回交易信号和完整的风险管理参数。\n" +
    "支持 18+ 种内置策略，包括趋势跟踪、均值回归、波动率、多因子等类型。\n" +
    "返回内容：买卖信号、置信度、止损价格、仓位建议、技术指标。\n" +
    "适用场景：获取策略对特定股票的判断和风控建议。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码，支持带后缀（600519.SH）或不带后缀（600519）"
    }),
    strategy: Type.String({
      description: "策略名称，如：VolatilityBreakout, Turtle, DonchianChannel, Momentum"
    }),
    date: Type.Optional(Type.String({
      description: "可选：指定日期（YYYY-MM-DD格式），默认使用最新数据"
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      // 参数验证
      if (!params?.symbol || typeof params.symbol !== 'string') {
        return {
          content: [{
            type: "text" as const,
            text: "错误：缺少必需参数 symbol（股票代码）"
          }],
          details: undefined
        };
      }

      if (!params?.strategy || typeof params.strategy !== 'string') {
        return {
          content: [{
            type: "text" as const,
            text: "错误：缺少必需参数 strategy（策略名称）"
          }],
          details: undefined
        };
      }

      // 标准化股票代码（确保有后缀）
      let symbol = params.symbol.trim();
      if (!/\.(SH|SZ|BJ)$/.test(symbol)) {
        // 6开头 → 上海，0/3开头 → 深圳，8开头 → 北京
        if (symbol.startsWith('6')) {
          symbol = `${symbol}.SH`;
        } else if (symbol.startsWith('0') || symbol.startsWith('3')) {
          symbol = `${symbol}.SZ`;
        } else if (symbol.startsWith('8')) {
          symbol = `${symbol}.BJ`;
        } else {
          return {
            content: [{
              type: "text" as const,
              text: `错误：无法识别股票代码格式: ${symbol}`
            }],
            details: undefined
          };
        }
      }

      // 调用 v2 API
      const signal = await executeStrategy({
        symbol,
        strategy_name: params.strategy,
        date: params.date
      });

      // 检查 API 返回状态
      if (!signal.success) {
        // 如果是策略不存在错误，返回可用策略列表
        if (signal.error && (signal.error.includes('not found') || signal.error.includes('不存在'))) {
          const strategies = await getAvailableStrategies();
          if (strategies && strategies.length > 0) {
            return {
              content: [{
                type: "text" as const,
                text: formatStrategiesError(strategies)
              }],
              details: undefined
            };
          }
        }

        return {
          content: [{
            type: "text" as const,
            text: `策略执行失败: ${signal.error || '未知错误'}`
          }],
          details: undefined
        };
      }

      // 格式化输出
      const formattedText = formatStrategySignal(signal);

      return {
        content: [{
          type: "text" as const,
          text: formattedText
        }],
        details: signal  // 保留原始信号数据
      };

    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `策略执行失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
};
