/**
 * Data Fetch Stock Tool - L1 数据管道层
 *
 * 整合 get_stock_info, get_stock_price, get_stock_news, get_announcements
 * 为单一工具，支持多字段组合查询。
 *
 * 【实时数据支持】
 * - price 字段通过新浪财经 API 获取实时行情（延迟 < 3秒）
 * - 返回数据包含 source 字段标识数据来源（sina=实时，db_fallback=数据库）
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { detectMarket } from "../shared/validators.js";
import { getStockData } from "../../quant/quant-v2-client.js";
import { formatStockPrice } from "../../quant/formatters.js";

// Constants
const DEFAULT_NEWS_COUNT = 10;

type DataField = "info" | "price" | "news" | "announcements";

interface FetchStockParams {
  symbol: string;
  fields?: DataField[];
  news_num?: number;
  source?: 'realtime' | 'db' | 'auto';
}


export const dataFetchStockTool: ToolDefinition = {
  name: "data_fetch_stock",
  label: "获取股票数据（支持实时行情）",
  description:
    "获取股票基础数据（info/price/news/announcements）。支持 A 股和港股。" +
    "price 字段支持多数据源：realtime（实时行情，延迟<3秒，默认），db（数据库收盘价），auto（自动选择）。" +
    "实时数据源包括：新浪财经、东方财富、腾讯财经、网易财经、AKShare。" +
    "返回数据包含 source 字段标识实际数据来源，timestamp（实时）或 trade_date（数据库）字段标识数据时间。" +
    "默认获取 info + price，可通过 fields 参数指定字段组合。",

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
    ),
    source: Type.Optional(
      Type.Union([
        Type.Literal("realtime"),
        Type.Literal("db"),
        Type.Literal("auto")
      ], {
        description: "数据源选择：realtime=实时行情（默认），db=数据库收盘价，auto=自动选择"
      })
    )
  }),

  execute: async (_toolCallId, params: FetchStockParams) => {
    const { symbol, fields = ["info", "price"], news_num = DEFAULT_NEWS_COUNT, source = 'realtime' } = params;

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
      const result = await getStockData(symbol, fields, news_num, source);

      // 如果包含 price 字段，使用格式化输出
      if (fields.includes('price') && result.price) {
        const formattedPrice = formatStockPrice(result.price);

        // 构建完整输出
        const output: string[] = [];

        // 添加格式化的价格信息
        output.push(formattedPrice);

        // 添加其他字段的 JSON 数据
        if (fields.includes('info') && result.info) {
          output.push('\n【基本信息】');
          output.push(JSON.stringify(result.info, null, 2));
        }

        if (fields.includes('news') && result.news) {
          output.push('\n【新闻资讯】');
          output.push(JSON.stringify(result.news, null, 2));
        }

        if (fields.includes('announcements') && result.announcements) {
          output.push('\n【公司公告】');
          output.push(JSON.stringify(result.announcements, null, 2));
        }

        // 添加错误信息（如果有）
        const errors: string[] = [];
        if (result.info_error) errors.push(`info: ${result.info_error}`);
        if (result.price_error) errors.push(`price: ${result.price_error}`);
        if (result.news_error) errors.push(`news: ${result.news_error}`);
        if (result.announcements_error) errors.push(`announcements: ${result.announcements_error}`);

        if (errors.length > 0) {
          output.push('\n【部分字段获取失败】');
          output.push(errors.join('\n'));
        }

        return {
          content: [{
            type: "text" as const,
            text: output.join('\n')
          }],
          details: undefined
        };
      }

      // 如果不包含 price 字段，返回原始 JSON
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
