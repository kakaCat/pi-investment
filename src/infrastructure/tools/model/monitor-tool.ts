/**
 * Model Monitor Tool (L3 模型层)
 *
 * 监控模型特征漂移，检测模型是否需要重新训练
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

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
    try {
      const result = await callQuantSysDaemon("monitor_model", {
        model_id: params.model_id || "latest"
      });

      // Parse the result to ensure it's valid JSON
      const parsedResult = JSON.parse(result);

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(parsedResult, null, 2)
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
