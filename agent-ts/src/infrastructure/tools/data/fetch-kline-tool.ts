/**
 * Data Fetch Kline Tool - L1 数据管道层
 *
 * 获取历史K线数据（OHLCV）
 * 重命名自 get_stock_history
 *
 * 🆕 集成统一响应处理系统：长周期数据自动持久化
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { detectMarket } from "../shared/validators.js";
import { getKlineHistory } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

// Constants
const DEFAULT_PERIOD = "daily";
// 以下常量仅用于工具描述文档，实际限制由 quantsys-v2 API 后端控制
const MAX_DATA_POINTS = 60;        // 后端返回的最大数据点数
const DEFAULT_LOOKBACK_DAYS = 90;  // 后端默认查询的回溯天数

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
    "支持 A 股个股（6位代码，如 600519/000001/300750）和深市指数（399xxx，如创业板指 399006、深成指 399001）。" +
    "注意：000001 是平安银行（深市个股），不是上证指数；上证指数K线暂不支持。港股 K 线暂不可用。" +
    "用于趋势分析和技术分析上下文 — 不用于查询当前价格（请使用 data_fetch_stock 的 price 字段）。" +
    "\n\n❌ 失败处理：返回的 error 中包含结构化 JSON，" +
    "provider_errors 字段逐一列出每个数据源（database/tencent/akshare）的具体失败原因，" +
    "suggestion 字段给出修复建议。请根据原因自我纠正：" +
    "代码无法映射→检查代码前缀是否符合上述规则；网络型失败→稍后重试或缩短日期范围；" +
    "数据库无缓存但网络源可用→属正常现象不影响结果。" +
    "\n\n💾 长周期数据（> 30天）自动保存到本地文件。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）或深市指数 399xxx（如 399006 创业板指）。000001=平安银行而非上证指数。港股暂不可用。"
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

  execute: async (_toolCallId: string, params: FetchKlineParams) => {
    const { symbol, period = DEFAULT_PERIOD, start_date, end_date } = params;

    // 验证股票代码
    const market = detectMarket(symbol);
    if (market === "invalid") {
      const errorResponse: ErrorResponse = {
        success: false,
        error: `不支持的股票代码 "${symbol}"。本系统仅支持A股（6位数字，如 600519）。港股数据暂不可用。`,
        invalid_format: true
      };

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(errorResponse)
        }],
        details: null
      };
    }

    // 调用 v2 API
    try {
      const result = await getKlineHistory(symbol, period, start_date, end_date);

      // 使用统一响应处理（长周期数据持久化）
      return handleToolResponse({
        toolName: 'data_fetch_kline',
        data: result,
        formatter: _formatKlineData,
        metadata: {
          symbol,
          period,
          start_date,
          end_date,
        },
        threshold: 20 * 1024, // 20KB，约对应30-40天日K线数据
      });
    } catch (error) {
      return createErrorResponse(error);
    }
  }
};

/**
 * 格式化K线数据
 */
function _formatKlineData(result: any): string {
  if (!(result as any).success) {
    return JSON.stringify(result);
  }

  const data = (result as any).data;
  if (!data || !Array.isArray(data) || data.length === 0) {
    return JSON.stringify(result);
  }

  const lines: string[] = [];
  lines.push(`📊 K线数据: ${result.symbol || ''}`);
  lines.push(`周期: ${result.period || 'daily'}`);
  lines.push(`数据点数: ${data.length}`);

  // 后端提示（如 000xxx 歧义警告）必须展示给 agent
  if ((result as any).note) {
    lines.push(`⚠️ ${(result as any).note}`);
  }

  if (data.length > 0) {
    const first = data[0];
    const last = data[data.length - 1];
    lines.push(`时间范围: ${first.trade_date || first.date} ~ ${last.trade_date || last.date}`);

    // 显示最近5个数据点
    lines.push('\n最近数据:');
    const recent = data.slice(-5);
    recent.forEach(item => {
      const date = item.trade_date || item.date;
      const close = item.close?.toFixed(2) || 'N/A';
      const change = item.pct_chg !== undefined ? `${item.pct_chg > 0 ? '+' : ''}${item.pct_chg.toFixed(2)}%` : 'N/A';
      lines.push(`  ${date}: 收盘 ${close} (${change})`);
    });
  }

  return lines.join('\n');
}
