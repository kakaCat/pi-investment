/**
 * Calibrate Tool - 置信度校准工具
 *
 * 从 quant_cli 拆分出来，专注于置信度校准业务
 * 运行置信度校准：从历史因子数据计算各技术指标的 IC 和最优阈值
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

export const calibrateTool: ToolDefinition = {
  name: "calibrate_confidence",
  label: "置信度校准",
  description: "运行置信度校准，计算各技术指标的 IC 和最优阈值，生成配置文件供信号生成器使用",
  parameters: Type.Object({
    forward_days: Type.Optional(Type.Integer({
      description: "前向收益天数",
      default: 5,
      minimum: 1
    })),
    return_threshold: Type.Optional(Type.Number({
      description: "收益率阈值",
      default: 0.02,
      minimum: 0
    })),
    lookback_days: Type.Optional(Type.Integer({
      description: "回溯天数",
      default: 180,
      minimum: 30
    })),
    max_symbols: Type.Optional(Type.Integer({
      description: "最大股票数量",
      default: 100,
      minimum: 50
    }))
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const response = await runQuantV2("calibrate.run", params);
      return handleToolResponse({
        toolName: 'calibrate_confidence',
        data: response,
        formatter: (data) => typeof data === 'string' ? data : JSON.stringify(data, null, 2),
        metadata: { params }
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `置信度校准失败: ${errorMsg}`
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
