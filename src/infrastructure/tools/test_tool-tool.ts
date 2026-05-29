import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

export const test_toolTool: ToolDefinition = {
  name: "test_tool",
  label: "test_tool",
  description: "测试工具",
  parameters: Type.Object({
    message: Type.Optional(Type.String({ description: "测试消息" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const message = typeof params?.message === "string" ? params.message : "默认测试结果";

    return {
      content: [{ type: "text" as const, text: message }],
      details: {
        success: true,
        tool: "test_tool",
        receivedParams: params ?? {},
        message,
      },
    };
  },
};