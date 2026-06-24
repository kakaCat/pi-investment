/**
 * Model List Tool - L3 模型层
 *
 * 列出所有训练好的模型及其版本信息
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { listModels } from "../../adapters/quant/quant-v2-client.js";

interface ModelListParams {
  status?: string;
}

export const modelListTool: ToolDefinition = {
  name: "model_list",
  label: "模型列表",
  description:
    "L3 模型层工具：列出所有训练好的模型及其版本信息。" +
    "返回模型列表，包括：" +
    "1. 模型ID（时间戳）" +
    "2. 模型类型（xgboost/lightgbm）" +
    "3. 模型路径" +
    "4. 训练时间戳" +
    "5. 测试集准确率" +
    "6. 测试集F1分数" +
    "7. 特征数量" +
    "支持过滤：status='all'（所有模型，默认）或 'latest'（仅最新模型）。",

  parameters: Type.Object({
    status: Type.Optional(
      Type.String({
        description: "过滤状态：'all'（所有模型，默认）或 'latest'（仅最新模型）"
      })
    )
  }),

  execute: async (_toolCallId: string, params: ModelListParams) => {
    const { status = "all" } = params;

    try {
      const response = await listModels(undefined, status === "all" ? undefined : status);

      if (!response.success) {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: false,
              error: response.error || "获取模型列表失败"
            }, null, 2)
          }],
          details: null
        };
      }

      // 格式化输出
      const formatted = {
        success: true,
        total: response.total,
        models: response.models.map(m => ({
          model_type: m.model_type,
          version: m.version,
          train_date: m.train_date,
          accuracy: m.test_accuracy,
          f1_score: m.f1_score,
          features: m.feature_count,
          samples: m.train_samples,
          status: m.status
        }))
      };

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(formatted, null, 2)
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
