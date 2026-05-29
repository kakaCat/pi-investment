/**
 * Data Fetch Stock Tool - L1 数据管道层
 *
 * 整合 get_stock_info, get_stock_price, get_stock_news, get_announcements
 * 为单一工具，支持多字段组合查询。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { detectMarket } from "../shared/validators.js";
import { getStockData } from "../../quant/quant-v2-client.js";
import type { StockData } from "../../quant/types.js";

// Constants
const DEFAULT_NEWS_COUNT = 10;

type DataField = "info" | "price" | "news" | "announcements";

interface FetchStockParams {
  symbol: string;
  fields?: DataField[];
  news_num?: number;
}


export const dataFetchStockTool: ToolDefinition = {
  name: "data_fetch_stock",
  label: "获取股票数据",
  description:
    "L1 数据管道工具：一站式获取股票基础数据（info/price/news/announcements）。" +
    "支持 A 股（6位代码）和港股（1-5位代码或 .HK 后缀）。" +
    "默认获取 info + price；可通过 fields 参数指定需要的字段组合。" +
    "返回 JSON 格式，包含请求的所有字段数据。" +
    "如果某个字段获取失败，该字段值为 null，错误信息存储在 {field}_error 字段中。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）或港股1-5位数字（如 9988 或 9988.HK）"
    }),
    fields: Type.Optional(
      Type.Array(
        Type.Union([
          Type.Literal("info"),
          Type.Literal("price"),
          Type.Literal("news"),
          Type.Literal("announcements")
        ]),
        {
          description: "要获取的数据字段。默认: ['info', 'price']"
        }
      )
    ),
    news_num: Type.Optional(
      Type.Integer({
        description: `新闻条数（仅当 fields 包含 'news' 时有效）。默认: ${DEFAULT_NEWS_COUNT}`,
        minimum: 1,
        maximum: 50
      })
    )
  }),

  execute: async (_toolCallId, params: FetchStockParams) => {
    const { symbol, fields = ["info", "price"], news_num = DEFAULT_NEWS_COUNT } = params;

    // 验证股票代码
    const market = detectMarket(symbol);
    if (market === "invalid") {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            error: `不支持的股票代码 "${symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`,
            invalid_format: true
          })
        }],
        details: undefined
      };
    }

    // 调用 v2 API
    try {
      const result = await getStockData(symbol, fields, news_num);

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(result, null, 2)
        }],
        details: undefined
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `获取股票数据失败: ${errorMsg}`
          })
        }],
        details: undefined
      };
    }
  }
};
