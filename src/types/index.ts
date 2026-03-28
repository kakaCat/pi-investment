import type Anthropic from "@anthropic-ai/sdk";

export type Message = Anthropic.MessageParam;
export type ContentBlock = Anthropic.ContentBlock;
export type ToolUseBlock = Anthropic.ToolUseBlock;
export type TextBlock = Anthropic.TextBlock;

export interface ToolResult {
  type: "tool_result";
  tool_use_id: string;
  content: string;
}
