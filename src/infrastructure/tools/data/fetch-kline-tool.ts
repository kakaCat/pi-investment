/**
 * Data Fetch Kline Tool - L1 数据管道层
 *
 * 获取历史K线数据（OHLCV）
 * 重命名自 get_stock_history
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { detectMarket } from "../shared/validators.js";
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

// Constants
const DEFAULT_PERIOD = "daily";
const MAX_DATA_POINTS = 60;
const DEFAULT_LOOKBACK_DAYS = 90;

type Period = "daily" | "weekly" | "monthly";

interface FetchKlineParams {
  symbol: string;
  period?: Period;
  start_date?: string;
  end_date?: string;
}

interface ErrorResponse {
  success: false;
  error: string;
  invalid_format?: boolean;
}

export const dataFetchKlineTool: ToolDefinition = {
  name: "data_fetch_kline",
  label: "获取历史K线",
  description:
    "L1 数据管道工具：获取历史OHLCV数据（开盘价、最高价、最低价、收盘价、成交量、涨跌幅）。" +
    `默认返回最近 ${DEFAULT_LOOKBACK_DAYS} 天的日K线数据（前复权），最多 ${MAX_DATA_POINTS} 个数据点。` +
    "支持 A 股（6位代码）和港股（1-5位代码或 .HK 后缀）。" +
    "用于趋势分析和技术分析上下文 — 不用于查询当前价格（请使用 data_fetch_stock 的 price 字段）。" +
    "如果股票在请求的日期范围内没有交易数据，返回 {error}。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）或港股1-5位数字（如 9988 或 9988.HK）"
    }),
    period: Type.Optional(
      Type.Union([
        Type.Literal("daily"),
        Type.Literal("weekly"),
        Type.Literal("monthly")
      ], {
        description: `聚合周期。默认: '${DEFAULT_PERIOD}'`
      })
    ),
    start_date: Type.Optional(
      Type.String({
        description: `开始日期（YYYYMMDD格式）。默认: ${DEFAULT_LOOKBACK_DAYS}天前`
      })
    ),
    end_date: Type.Optional(
      Type.String({
        description: "结束日期（YYYYMMDD格式）。默认: 今天"
      })
    )
  }),

  execute: async (_toolCallId, params: FetchKlineParams) => {
    const { symbol, period = DEFAULT_PERIOD, start_date, end_date } = params;

    // 验证股票代码
    const market = detectMarket(symbol);
    if (market === "invalid") {
      const errorResponse: ErrorResponse = {
        success: false,
        error: `不支持的股票代码 "${symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`,
        invalid_format: true
      };

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(errorResponse)
        }],
        details: undefined
      };
    }

    // 调用 quantsys daemon
    try {
      const result = await callQuantSysDaemon("get_stock_history", {
        symbol,
        period,
        start_date,
        end_date
      });

      return {
        content: [{
          type: "text" as const,
          text: result
        }],
        details: undefined
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      const errorResponse: ErrorResponse = {
        success: false,
        error: `获取K线数据失败: ${errorMsg}`
      };

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(errorResponse)
        }],
        details: undefined
      };
    }
  }
};
