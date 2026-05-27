/**
 * 策略执行工具 - 运行单个策略并返回信号（含风险管理参数）
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { executeStrategy } from "../../quant/quant-v2-client.js";
import { formatStrategySignal } from "../../quant/formatters.js";

export const strategyExecuteTool: ToolDefinition = {
  name: "strategy_execute",
  label: "执行策略",
  description:
    "执行单个量化策略，返回交易信号和完整的风险管理参数。\n" +
    "支持的策略包括：VolatilityBreakout（波动突破）、Turtle（海龟）、" +
    "DonchianChannel（唐奇安通道）、Momentum（动量）等。\n" +
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
