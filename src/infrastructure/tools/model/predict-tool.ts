/**
 * Model Predict Tool - L3 模型层
 *
 * 使用训练好的模型预测股票信号和置信度
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { detectMarket } from "../shared/validators.js";
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

interface PredictParams {
  symbol: string;
  model_id?: string;
  features?: string[];
}

export const modelPredictTool: ToolDefinition = {
  name: "model_predict",
  label: "模型预测",
  description:
    "L3 模型层工具：使用训练好的机器学习模型预测股票信号和置信度。" +
    "支持 A 股（6位代码）和港股（1-5位代码或 .HK 后缀）。" +
    "默认使用最新训练的模型；可通过 model_id 参数指定特定模型版本。" +
    "返回预测信号（buy/sell/hold）、置信度（0-1）、特征值等信息。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）或港股1-5位数字（如 9988 或 9988.HK）"
    }),
    model_id: Type.Optional(
      Type.String({
        description: "模型ID，默认使用最新模型（latest）"
      })
    ),
    features: Type.Optional(
      Type.Array(Type.String(), {
        description: "指定使用的特征列表，不指定则使用模型的全部特征"
      })
    )
  }),

  execute: async (_toolCallId, params: PredictParams) => {
    const { symbol, model_id = "latest", features } = params;

    // 参数验证：symbol 必需
    if (!symbol || symbol.trim() === "") {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: "symbol 参数是必需的"
          })
        }],
        details: undefined
      };
    }

    // 验证股票代码格式
    const market = detectMarket(symbol);
    if (market === "invalid") {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `不支持的股票代码 "${symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`,
            invalid_format: true
          })
        }],
        details: undefined
      };
    }

    try {
      // 调用后端 daemon 方法
      const result = await callQuantSysDaemon("predict_signal_confidence", {
        symbol,
        model_name: model_id,
        features: features || undefined
      });

      // 解析响应
      const prediction = JSON.parse(result);

      // 验证响应格式
      if (!prediction || typeof prediction !== "object") {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: false,
              error: "模型预测返回了无效的响应格式"
            })
          }],
          details: undefined
        };
      }

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(prediction, null, 2)
        }],
        details: undefined
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);

      // 特定错误处理
      let errorResponse: Record<string, any> = {
        success: false,
        error: errorMsg
      };

      // 模型不存在错误
      if (errorMsg.includes("not found") || errorMsg.includes("不存在")) {
        errorResponse.model_not_found = true;
        errorResponse.error = `模型 "${model_id}" 不存在。请使用 model_list 工具查看可用模型。`;
      }
      // Daemon 连接失败
      else if (errorMsg.includes("daemon") || errorMsg.includes("timeout")) {
        errorResponse.daemon_error = true;
        errorResponse.error = `无法连接到量化系统后端：${errorMsg}`;
      }

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
