import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

export const new_toolTool: ToolDefinition = {
  name: "new_tool",
  label: "new_tool",
  description: "新工具",
  parameters: Type.Object({
    input: Type.Optional(Type.String({ description: "可选输入" })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    const input = typeof params?.input === "string" ? params.input : "";
    const text = input ? `结果文本: ${input}` : "结果文本";

    return {
      content: [{ type: "text" as const, text }],
      details: {
        toolCallId: _toolCallId,
        input,
        success: true,
      },
    };
  },
};