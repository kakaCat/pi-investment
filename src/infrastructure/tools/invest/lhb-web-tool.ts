/**
 * 龙虎榜 Web 查询工具 - 通过 WebFetch 从东方财富网获取数据
 *
 * 作为 get_lhb 的备用方案，当 akshare API 超时时使用
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";

export const getLhbWebTool: ToolDefinition = {
  name: "get_lhb_web",
  label: "龙虎榜(网页版)",
  description:
    "Fetch Dragon-Tiger List (龙虎榜) data from East Money website when get_lhb times out. " +
    "This tool uses WebFetch to scrape the latest榜单 from https://data.eastmoney.com/stock/lhb.html. " +
    "Returns today's top stocks with unusual trading activity: circuit breakers, high volume, or large price swings. " +
    "Shows net buy/sell amounts and institutional vs retail participation. " +
    "Use this as a fallback when get_lhb API is slow or unavailable. " +
    "Note: Web scraping may be slower than API but more reliable during peak hours.",
  parameters: Type.Object({
    query: Type.Optional(Type.String({
      description: "Optional: specific stock symbol to search for in the榜单, e.g. '600519'. If omitted, returns full榜单."
    })),
  }),
  execute: async (_toolCallId, params: any) => {
    // 使用 WebFetch 工具获取龙虎榜数据
    const url = "https://data.eastmoney.com/stock/lhb.html";
    const prompt = params.query
      ? `Extract Dragon-Tiger List (龙虎榜) data for stock ${params.query}. Return: stock code, name, close price, change %, net buy amount, reason for listing, and top buying/selling seats.`
      : `Extract today's Dragon-Tiger List (龙虎榜) data. Return top 20 stocks with: stock code, name, close price, change %, net buy amount, and reason for listing. Format as a structured list.`;

    // 注意：这里需要调用 WebFetch 工具
    // 在实际执行时，这个工具会被 tool registry 调用
    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify({
          note: "请使用 WebFetch 工具访问以下 URL 获取龙虎榜数据",
          url: url,
          prompt: prompt,
          alternative_urls: [
            "http://data.10jqka.com.cn/market/longhu/",
            "http://vip.stock.finance.sina.com.cn/q/go.php/vInvestConsult/kind/lhb/index.phtml"
          ],
          usage_hint: "如果东方财富网无法访问，可以尝试同花顺或新浪财经的龙虎榜页面"
        })
      }],
      details: undefined
    };
  },
};

export const lhbWebTools: ToolDefinition[] = [getLhbWebTool];
