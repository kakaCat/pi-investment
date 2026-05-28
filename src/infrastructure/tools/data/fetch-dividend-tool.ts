/**
 * 分红数据获取工具 - L1 数据管道层
 *
 * 支持三种模式：
 * 1. single - 查询单只股票历史分红记录
 * 2. screen - 筛选高股息股票
 * 3. calendar - 查询分红日历
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { getDividends } from "../../quant/quant-v2-client.js";
import { formatDividendData } from "../../quant/formatters.js";

export const dataFetchDividendTool: ToolDefinition = {
  name: "data_fetch_dividend",
  label: "获取分红数据",
  description:
    "L1 数据管道工具：获取股票分红数据。支持三种模式：" +
    "1) single - 查询单只股票历史分红记录；" +
    "2) screen - 筛选高股息股票；" +
    "3) calendar - 查询分红日历（即将除权除息的股票）。",

  parameters: Type.Object({
    mode: Type.Union([
      Type.Literal("single"),
      Type.Literal("screen"),
      Type.Literal("calendar")
    ], {
      description: "查询模式：single=单股查询, screen=批量筛选, calendar=分红日历"
    }),

    // single 模式参数
    symbol: Type.Optional(Type.String({
      description: "股票代码（single模式必填，如 600519.SH）"
    })),
    years: Type.Optional(Type.Number({
      description: "查询最近N年（single模式，默认10年）"
    })),

    // screen 模式参数
    min_yield: Type.Optional(Type.Number({
      description: "最低股息率%（screen模式）"
    })),
    min_years: Type.Optional(Type.Number({
      description: "最少连续分红年数（screen模式）"
    })),
    min_payout_ratio: Type.Optional(Type.Number({
      description: "最低分红率%（screen模式）"
    })),
    max_payout_ratio: Type.Optional(Type.Number({
      description: "最高分红率%（screen模式）"
    })),
    limit: Type.Optional(Type.Number({
      description: "返回数量限制（screen模式，默认50）"
    })),

    // calendar 模式参数
    start_date: Type.Optional(Type.String({
      description: "开始日期 YYYY-MM-DD（calendar模式必填）"
    })),
    end_date: Type.Optional(Type.String({
      description: "结束日期 YYYY-MM-DD（calendar模式必填）"
    })),
    event: Type.Optional(Type.String({
      description: "事件类型（calendar模式）：ex_dividend=除权除息日, record_date=股权登记日, pay_date=派息日"
    }))
  }),

  execute: async (_toolCallId, params: {
    mode: 'single' | 'screen' | 'calendar';
    symbol?: string;
    years?: number;
    min_yield?: number;
    min_years?: number;
    min_payout_ratio?: number;
    max_payout_ratio?: number;
    limit?: number;
    start_date?: string;
    end_date?: string;
    event?: string;
  }) => {
    try {
      // 参数验证
      if (params.mode === 'single' && !params.symbol) {
        return {
          content: [{ type: "text" as const, text: "single 模式必须提供 symbol 参数" }],
          details: undefined
        };
      }

      if (params.mode === 'calendar' && (!params.start_date || !params.end_date)) {
        return {
          content: [{ type: "text" as const, text: "calendar 模式必须提供 start_date 和 end_date 参数" }],
          details: undefined
        };
      }

      // 调用 v2 API
      const data = await getDividends(params);

      if (!data.success) {
        return {
          content: [{ type: "text" as const, text: `查询失败: ${data.error || '未知错误'}` }],
          details: undefined
        };
      }

      // 格式化输出
      const formattedText = formatDividendData(data, params.mode);

      return {
        content: [{ type: "text" as const, text: formattedText }],
        details: undefined
      };
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `分红数据获取失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
};
