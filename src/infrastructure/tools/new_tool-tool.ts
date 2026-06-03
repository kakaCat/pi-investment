import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

export const new_toolTool: ToolDefinition = {
  name: "new_tool",
  label: "new_tool",
  description: "新工具",
  parameters: Type.Object({
    input: Type.Optional(Type.String()),
  }),
  execute: async (_toolCallId, params: any) => {
    const input = typeof params?.input === "string" ? params.input : "";
    const resultText = input ? `结果文本: ${input}` : "结果文本";

    return {
      content: [{ type: "text" as const, text: resultText }],
      details: {
        success: true,
        input,
      },
    };
  },
};