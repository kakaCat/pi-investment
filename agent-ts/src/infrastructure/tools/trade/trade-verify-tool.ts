/**
 * Trade Verify Tool - 交易验证工具
 *
 * 从 quant_cli 拆分出来，专注于交易验证业务
 * 对比实盘交易记录和回测交易记录，识别价格、方向和缺失差异
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

export const tradeVerifyTool: ToolDefinition = {
  name: "trade_verify",
  label: "交易验证",
  description: "对比实盘交易记录和回测交易记录，识别价格差异、方向错误和缺失交易",
  parameters: Type.Object({
    trades_json: Type.String({
      description: "实盘交易记录 JSON 字符串，格式：[{symbol, date, price, direction, quantity}]"
    }),
    backtest_json: Type.String({
      description: "回测交易记录 JSON 字符串，格式：[{symbol, date, price, direction, quantity}]"
    })
  }),
  execute: async (_toolCallId, params: any) => {
    // 参数验证
    if (!params.trades_json) {
      return {
        content: [{
          type: "text" as const,
          text: "缺少必填参数: trades_json"
        }],
        details: { success: false, error: "MISSING_TRADES_JSON" }
      };
    }

    if (!params.backtest_json) {
      return {
        content: [{
          type: "text" as const,
          text: "缺少必填参数: backtest_json"
        }],
        details: { success: false, error: "MISSING_BACKTEST_JSON" }
      };
    }

    // JSON 格式验证
    try {
      JSON.parse(params.trades_json);
    } catch {
      return {
        content: [{
          type: "text" as const,
          text: "trades_json 不是有效的 JSON 格式"
        }],
        details: { success: false, error: "INVALID_TRADES_JSON" }
      };
    }

    try {
      JSON.parse(params.backtest_json);
    } catch {
      return {
        content: [{
          type: "text" as const,
          text: "backtest_json 不是有效的 JSON 格式"
        }],
        details: { success: false, error: "INVALID_BACKTEST_JSON" }
      };
    }

    try {
      const response = await runQuantV2("trade.verify", params);
      return handleToolResponse({
        toolName: 'trade_verify',
        data: response,
        formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
        metadata: {
          trades_count: JSON.parse(params.trades_json).length,
          backtest_count: JSON.parse(params.backtest_json).length
        }
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `交易验证失败: ${errorMsg}`
        }],
        details: {
          success: false,
          error: errorMsg,
          params: { trades_count: params.trades_json.length, backtest_count: params.backtest_json.length }
        }
      };
    }
  }
};
