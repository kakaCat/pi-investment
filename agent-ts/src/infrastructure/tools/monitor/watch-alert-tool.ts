/**
 * Watch Alert Tool - 价格监控预警工具
 *
 * 从 quant_cli 拆分出来，专注于价格监控预警业务
 * 校验股票价格是否触发上破、下破或涨跌幅预警
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

export const watchAlertTool: ToolDefinition = {
  name: "watch_price_alert",
  label: "价格预警",
  description: "校验股票价格是否触发预警条件：上破某价格、下破某价格、涨跌幅超过阈值",
  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码，例如：600000、000001、00700"
    }),
    price: Type.Number({
      description: "当前价格"
    }),
    above: Type.Optional(Type.Number({
      description: "上破预警价格（价格 >= above 时触发）"
    })),
    below: Type.Optional(Type.Number({
      description: "下破预警价格（价格 <= below 时触发）"
    })),
    change_pct: Type.Optional(Type.Number({
      description: "涨跌幅预警阈值（绝对值，如 0.05 表示 5%）"
    })),
    last_price: Type.Optional(Type.Number({
      description: "上一次价格（用于计算涨跌幅）"
    }))
  }),
  execute: async (_toolCallId: string, params: any) => {
    // 参数验证
    if (!params.symbol!) {
      return {
        content: [{
          type: "text" as const,
          text: "缺少必填参数: symbol"
        }],
        details: { success: false, error: "MISSING_SYMBOL" }
      };
    }

    if (params.price === undefined) {
      return {
        content: [{
          type: "text" as const,
          text: "缺少必填参数: price"
        }],
        details: { success: false, error: "MISSING_PRICE" }
      };
    }

    // 至少需要一个预警条件
    if (!params.above && !params.below && !params.change_pct) {
      return {
        content: [{
          type: "text" as const,
          text: "至少需要设置一个预警条件：above（上破）、below（下破）或 change_pct（涨跌幅）"
        }],
        details: { success: false, error: "NO_ALERT_CONDITION" }
      };
    }

    try {
      const response = await runQuantV2("watch.price-alert", params);
      return handleToolResponse({
        toolName: 'watch_price_alert',
        data: response,
        formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
        metadata: { params }
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `价格预警检查失败: ${errorMsg}`
        }],
        details: {
          success: false,
          error: errorMsg,
          params
        }
      };
    }
  }
};
