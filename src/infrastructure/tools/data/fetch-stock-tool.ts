/**
 * Data Fetch Stock Tool - L1 数据管道层
 *
 * 专注于实时行情查询，支持多数据源 fallback。
 *
 * 【实时数据支持】
 * - 通过新浪财经等多个数据源获取实时行情（延迟 < 3秒）
 * - 返回数据包含 source 字段标识数据来源（sina/eastmoney/tencent=实时，db_fallback=数据库）
 * - 非交易时段自动 fallback 到数据库最近收盘价
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { detectMarket } from "../shared/validators.js";
import { getStockData } from "../../adapters/quant/quant-v2-client.js";
import { formatStockPrice } from "../../adapters/quant/formatters.js";

/**
 * 判断当前是否是 A 股交易时段
 * 交易时间：周一至周五 9:30-11:30, 13:00-15:00
 * 注意：不考虑节假日
 */
function isTradingTime(): boolean {
  const now = new Date();
  const day = now.getDay(); // 0=Sunday, 1=Monday, ..., 6=Saturday
  const hour = now.getHours();
  const minute = now.getMinutes();

  // 周末不交易
  if (day === 0 || day === 6) {
    return false;
  }

  // 早盘：9:30-11:30
  if (hour === 9 && minute >= 30) return true;
  if (hour === 10) return true;
  if (hour === 11 && minute <= 30) return true;

  // 午盘：13:00-15:00
  if (hour === 13 || hour === 14) return true;
  if (hour === 15 && minute === 0) return true;

  return false;
}

interface FetchStockParams {
  symbol: string;
  source?: 'realtime' | 'db' | 'auto';
}

export const dataFetchQuoteTool: ToolDefinition = {
  name: "data_fetch_quote",
  label: "获取股票实时行情",
  description:
    "获取股票实时行情数据。仅支持 A 股（6位数字代码），港股数据暂不可用。" +
    "支持多数据源：realtime（仅实时行情），db（仅数据库收盘价），auto（自动选择，默认）。" +
    "实时数据源包括：新浪财经、东方财富、腾讯财经、网易财经、AKShare。" +
    "返回数据包含 source 字段标识实际数据来源，timestamp（实时）或 tradeDate（数据库）字段标识数据时间。" +
    "非交易时段（周末、收盘后）自动返回最近收盘价。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）。港股暂不可用。"
    }),
    source: Type.Optional(
      Type.Union([
        Type.Literal("realtime"),
        Type.Literal("db"),
        Type.Literal("auto")
      ], {
        description: "数据源选择：realtime=仅实时行情，db=仅数据库收盘价，auto=自动选择（默认）"
      })
    )
  }),

  execute: async (_toolCallId, params: FetchStockParams) => {
    const { symbol, source = 'auto' } = params;

    // 验证股票代码
    const market = detectMarket(symbol);
    if (market === "invalid") {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            error: `不支持的股票代码 "${symbol}"。本系统仅支持A股（6位数字，如 600519）。港股数据暂不可用。`,
            invalid_format: true
          })
        }],
        details: null
      };
    }

    // 调用 v2 API（仅查询 price 字段）
    try {
      const result = await getStockData(symbol, ['price'], 10, source);

      // 检查是否有数据
      if (result.price) {
        const formattedPrice = formatStockPrice(result.price);
        return {
          content: [{
            type: "text" as const,
            text: formattedPrice
          }],
          details: null
        };
      }

      // 如果有错误，添加友好提示
      if (result.price_error) {
        let errorMsg = result.price_error;

        // 如果是实时行情失败，且当前非交易时段，添加友好提示
        if ((errorMsg.includes('502') || errorMsg.includes('实时行情') || errorMsg.includes('无法获取')) && !isTradingTime()) {
          errorMsg += '\n\n💡 提示：当前非交易时段（A股交易时间：周一至周五 9:30-11:30, 13:00-15:00）。';
          errorMsg += '\n   实时行情不可用是正常现象。系统已自动尝试返回最近收盘价。';
          errorMsg += '\n   若需明确指定数据源，可使用 source="db" 参数直接获取数据库数据。';
        }

        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: false,
              error: errorMsg
            }, null, 2)
          }],
          details: null
        };
      }

      // 未知错误
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: '未能获取股票行情数据'
          })
        }],
        details: null
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `获取股票行情失败: ${errorMsg}`
          })
        }],
        details: null
      };
    }
  }
};
