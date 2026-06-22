/**
 * Model Train Tool - L3 模型层
 *
 * 训练机器学习模型（XGBoost/LightGBM），用于股票信号预测
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { trainModel } from "../../adapters/quant/quant-v2-client.js";

interface TrainModelParams {
  model_type?: "xgboost" | "lightgbm";
  days?: number;
  future_days?: number;
  return_threshold?: number;
  symbols?: string[];
  cv_splits?: number;
}

export const modelTrainTool: ToolDefinition = {
  name: "model_train",
  label: "训练模型",
  description:
    "L3 模型层工具：训练机器学习模型（XGBoost/LightGBM），用于股票信号预测。" +
    "支持自定义训练数据天数、预测天数、涨幅阈值、训练股票列表和交叉验证折数。" +
    "返回训练报告，包含模型性能指标、特征重要性、交叉验证结果等。",

  parameters: Type.Object({
    model_type: Type.Optional(
      Type.Union([Type.Literal("xgboost"), Type.Literal("lightgbm")], {
        description: "模型类型，默认 xgboost"
      })
    ),
    days: Type.Optional(
      Type.Integer({
        description: "训练数据天数，默认 180",
        minimum: 1
      })
    ),
    future_days: Type.Optional(
      Type.Integer({
        description: "预测未来N天收益，默认 5",
        minimum: 1
      })
    ),
    return_threshold: Type.Optional(
      Type.Number({
        description: "涨幅阈值（小数形式），默认 0.05（5%）",
        minimum: 0,
        maximum: 1
      })
    ),
    symbols: Type.Optional(
      Type.Array(Type.String(), {
        description: "训练股票列表，不指定则使用全部可用股票"
      })
    ),
    cv_splits: Type.Optional(
      Type.Integer({
        description: "交叉验证折数，默认 5",
        minimum: 2
      })
    )
  }),

  execute: async (_toolCallId, params: TrainModelParams) => {
    const {
      model_type = "xgboost",
      days = 180,
      future_days = 5,
      return_threshold = 0.05,
      symbols,
      cv_splits = 5
    } = params;

    try {
      const response = await trainModel({
        model_type,
        symbols,
        params: {
          days,
          future_days,
          return_threshold,
          cv_splits
        }
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
