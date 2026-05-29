/**
 * Model Evaluate Tool - L3 模型层
 *
 * 评估模型性能，查看训练报告、测试指标、特征重要性
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { evaluateModel } from "../../quant/quant-v2-client.js";

interface ModelEvaluateParams {
  model_id?: string;
}

export const modelEvaluateTool: ToolDefinition = {
  name: "model_evaluate",
  label: "模型评估",
  description:
    "L3 模型层工具：评估模型性能，查看训练报告、测试指标、特征重要性。" +
    "返回完整的训练报告，包括：" +
    "1. 训练数据统计（样本数、特征数、正负样本比例）" +
    "2. 交叉验证结果（各折准确率、F1分数）" +
    "3. 测试集指标（准确率、精确率、召回率、F1、AUC）" +
    "4. 特征重要性排序" +
    "5. 混淆矩阵" +
    "默认评估最新模型（model_id='latest'）。",

  parameters: Type.Object({
    model_id: Type.Optional(
      Type.String({
        description: "模型ID，默认评估最新模型（'latest'）"
      })
    )
  }),

  execute: async (_toolCallId, params: ModelEvaluateParams) => {
    const { model_id = "latest" } = params;

    try {
      const response = await evaluateModel("xgboost", model_id);

      if (!response.success) {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: false,
              error: response.error || "评估模型失败"
            }, null, 2)
          }],
          details: undefined
        };
      }

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(response.evaluation, null, 2)
        }],
        details: undefined
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
        details: undefined
      };
    }
  }
};
