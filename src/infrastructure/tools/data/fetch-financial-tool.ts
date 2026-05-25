/**
 * Data Fetch Financial Tool - L1 数据管道层
 *
 * 获取财务指标数据（ROE、毛利率、净利率等）
 * 重命名自 get_financial_data
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { requireAshare } from "../shared/validators.js";
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";
import { writeFile } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";

// Constants
const DEFAULT_STATEMENT = "all";
const DEFAULT_RECENT_N = 8;
const MAX_INLINE_LENGTH = 2000;

type StatementType = "income" | "balance" | "cashflow" | "all";

interface FetchFinancialParams {
  symbol: string;
  statement?: StatementType;
  recent_n?: number;
}

interface ErrorResponse {
  success: false;
  error: string;
  unsupported_for_hk?: boolean;
  invalid_format?: boolean;
}

/**
 * 如果数据过大，写入临时文件并返回预览
 */
async function handleLargeData(data: string, symbol: string): Promise<string> {
  if (data.length <= MAX_INLINE_LENGTH) {
    return data;
  }

  // 写入临时文件
  const timestamp = Date.now();
  const filename = `financial_${symbol}_${timestamp}.json`;
  const filepath = join(tmpdir(), filename);

  await writeFile(filepath, data, "utf-8");

  // 返回预览 + 文件路径（预览为原始字符串，不解析为避免截断导致的JSON错误）
  const preview = data.substring(0, MAX_INLINE_LENGTH);
  return JSON.stringify({
    note: "数据过大，已写入临时文件",
    file: filepath,
    preview_text: preview,
    full_length: data.length
  }, null, 2);
}

export const dataFetchFinancialTool: ToolDefinition = {
  name: "data_fetch_financial",
  label: "获取财务指标",
  description:
    "L1 数据管道工具：获取关键财务指标（ROE、毛利率、净利率、负债率、流动比率等）。" +
    `默认返回最近 ${DEFAULT_RECENT_N} 期的所有财务报表数据。` +
    "仅支持 A 股（6位代码）— 财务报表数据源不支持港股。" +
    "用于快速盈利能力和偿债能力筛选 — 是深度分析前的理想第一道过滤器。" +
    "如果数据超过 2000 字符，将写入临时文件并返回预览 + 文件路径。" +
    "如果公司没有发布财务数据，返回 {error}。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：仅支持A股6位数字（如 600519）"
    }),
    statement: Type.Optional(
      Type.Union([
        Type.Literal("income"),
        Type.Literal("balance"),
        Type.Literal("cashflow"),
        Type.Literal("all")
      ], {
        description: `报表类型：'income'(利润表), 'balance'(资产负债表), 'cashflow'(现金流量表), 'all'(全部)。默认: '${DEFAULT_STATEMENT}'`
      })
    ),
    recent_n: Type.Optional(
      Type.Integer({
        description: `最近N期报表。默认: ${DEFAULT_RECENT_N}`,
        minimum: 1,
        maximum: 20
      })
    )
  }),

  execute: async (_toolCallId, params: FetchFinancialParams) => {
    const { symbol, statement = DEFAULT_STATEMENT, recent_n = DEFAULT_RECENT_N } = params;

    // 验证A股代码
    const validationError = requireAshare(symbol);
    if (validationError) {
      return {
        content: [{
          type: "text" as const,
          text: validationError
        }],
        details: undefined
      };
    }

    // 调用 quantsys daemon
    try {
      const result = await callQuantSysDaemon("get_financial_statements", {
        symbol,
        statement,
        recent_n
      });

      // 处理大数据
      const finalResult = await handleLargeData(result, symbol);

      return {
        content: [{
          type: "text" as const,
          text: finalResult
        }],
        details: undefined
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      const errorResponse: ErrorResponse = {
        success: false,
        error: `获取财务数据失败: ${errorMsg}`
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
