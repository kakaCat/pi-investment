import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

export const new_toolTool: ToolDefinition = {
  name: "new_tool",
  label: "new_tool",
  description: "新工具",
  parameters: Type.Object(
    {
      input: Type.Optional(Type.String({ description: "输入文本" })),
    },
    { additionalProperties: true }
  ),
  execute: async (_toolCallId, params: any) => {
    const safeParams = params && typeof params === "object" ? params : {};

    return {
      content: [{ type: "text" as const, text: "结果文本" }],
      details: {
        success: true,
        params: safeParams,
      },
    };
  },
};