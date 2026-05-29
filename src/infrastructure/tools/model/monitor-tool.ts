/**
 * Model Monitor Tool (L3 模型层)
 *
 * 监控模型特征漂移，检测模型是否需要重新训练
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { monitorModel } from "../../quant/quant-v2-client.js";

interface MonitorModelParams {
  model_id?: string;
}

export const modelMonitorTool: ToolDefinition = {
  name: "model_monitor",
  label: "模型监控",
  description:
    "L3 模型层工具：监控模型特征漂移，检测模型是否需要重新训练。" +
    "返回漂移分数、漂移阈值、是否漂移标志、top漂移特征和重训练建议。",
  parameters: Type.Object({
    model_id: Type.Optional(Type.String({
      description: "模型ID，默认监控最新模型（latest）"
    }))
  }),
  execute: async (_toolCallId, params: MonitorModelParams) => {
    const { model_id = "latest" } = params;

    try {
      const response = await monitorModel("xgboost", model_id);

      if (!response.success) {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: false,
              error: response.error || "监控模型失败"
            }, null, 2)
          }],
          details: undefined
        };
      }

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(response.monitor, null, 2)
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
