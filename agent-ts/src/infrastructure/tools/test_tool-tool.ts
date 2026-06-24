import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

export const test_toolTool: ToolDefinition = {
  name: "test_tool",
  label: "test_tool",
  description: "测试工具",
  parameters: Type.Object({
    input: Type.Optional(Type.String({ description: "测试输入" })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    const input = typeof params?.input === "string" ? params.input : "";
    const text = input ? `测试工具执行成功: ${input}` : "测试工具执行成功";

    return {
      content: [{ type: "text" as const, text }],
      details: {
        success: true,
        input,
      },
    };
  },
};