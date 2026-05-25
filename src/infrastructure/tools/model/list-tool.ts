/**
 * Model List Tool - L3 模型层
 *
 * 列出所有训练好的模型及其版本信息
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

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

  execute: async (_toolCallId, params: ModelListParams) => {
    const { status = "all" } = params;

    try {
      const result = await callQuantSysDaemon("list_models", {
        status
      });

      return {
        content: [{
          type: "text" as const,
          text: result
        }],
        details: undefined
      };
    } catch (error: any) {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: error.message
          }, null, 2)
        }],
        details: undefined
      };
    }
  }
};
