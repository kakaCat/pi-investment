/**
 * Model Predict Tool - L3 模型层
 *
 * 使用训练好的模型预测股票信号和置信度
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { detectMarket } from "../shared/validators.js";
import { predictModel } from "../../adapters/quant/quant-v2-client.js";

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
    "仅支持 A 股（6位代码），港股预测暂不可用（需 K 线数据计算特征）。" +
    "默认使用最新训练的模型；可通过 model_id 参数指定特定模型版本。" +
    "返回预测信号（buy/sell/hold）、置信度（0-1）、特征值等信息。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）。港股暂不可用。"
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
            error: "参数错误：symbol 不能为空"
          }, null, 2)
        }],
        details: null
      };
    }

    // 市场检测
    const market = detectMarket(symbol);
    if (market === "invalid") {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `不支持的股票代码 "${symbol}"。本系统仅支持A股（6位数字，如 600519）。港股数据暂不可用。`
          }, null, 2)
        }],
        details: null
      };
    }

    try {
      const response = await predictModel({
        version: model_id,
        symbols: [symbol]
      });

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(response, null, 2)
        }],
        details: null
      };
    } catch (error: any) {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `API 调用失败: ${error.message}`
          }, null, 2)
        }],
        details: null
      };
    }
  }
};
