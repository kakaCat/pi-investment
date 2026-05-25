/**
 * Data Fetch Stock Tool - L1 数据管道层
 *
 * 整合 get_stock_info, get_stock_price, get_stock_news, get_announcements
 * 为单一工具，支持多字段组合查询。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { detectMarket } from "../shared/validators.js";
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

type DataField = "info" | "price" | "news" | "announcements";

interface FetchStockParams {
  symbol: string;
  fields?: DataField[];
  news_num?: number;
}

/**
 * 智能路由：根据字段类型调用对应的 daemon 方法
 */
async function fetchField(
  field: DataField,
  symbol: string,
  newsNum: number = 10
): Promise<{ key: string; value: any; error?: string }> {
  try {
    let result: string;

    switch (field) {
      case "info":
        result = await callQuantSysDaemon("get_stock_info", { symbol });
        return { key: "info", value: JSON.parse(result) };

      case "price":
        result = await callQuantSysDaemon("get_stock_realtime_price", { symbol });
        return { key: "price", value: JSON.parse(result) };

      case "news":
        result = await callQuantSysDaemon("get_stock_news", { symbol, num: newsNum });
        return { key: "news", value: JSON.parse(result) };

      case "announcements":
        result = await callQuantSysDaemon("get_announcements", { symbol });
        return { key: "announcements", value: JSON.parse(result) };

      default:
        return { key: field, value: null, error: `Unknown field: ${field}` };
    }
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    return { key: `${field}_error`, value: null, error: errorMsg };
  }
}

export const dataFetchStockTool: ToolDefinition = {
  name: "data_fetch_stock",
  label: "获取股票数据",
  description:
    "L1 数据管道工具：一站式获取股票基础数据（info/price/news/announcements）。" +
    "支持 A 股（6位代码）和港股（1-5位代码或 .HK 后缀）。" +
    "默认获取 info + price；可通过 fields 参数指定需要的字段组合。" +
    "返回 JSON 格式，包含请求的所有字段数据。" +
    "如果某个字段获取失败，会在响应中包含 {field}_error 字段。",

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
        description: "新闻条数（仅当 fields 包含 'news' 时有效）。默认: 10",
        minimum: 1,
        maximum: 50
      })
    )
  }),

  execute: async (_toolCallId, params: FetchStockParams) => {
    const { symbol, fields = ["info", "price"], news_num = 10 } = params;

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

    // 并行获取所有请求的字段
    const fetchPromises = fields.map(field => fetchField(field, symbol, news_num));
    const results = await Promise.all(fetchPromises);

    // 组装响应对象
    const response: Record<string, any> = {};
    let hasAnySuccess = false;

    for (const result of results) {
      if (result.error) {
        response[result.key] = result.error;
      } else {
        response[result.key] = result.value;
        hasAnySuccess = true;
      }
    }

    // 如果所有字段都失败了，添加顶层 error 字段
    if (!hasAnySuccess) {
      const firstError = results.find(r => r.error);
      response.error = firstError?.error || "所有数据获取失败";
    }

    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify(response, null, 2)
      }],
      details: undefined
    };
  }
};
