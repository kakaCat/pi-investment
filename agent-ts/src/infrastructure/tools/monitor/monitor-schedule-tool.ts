/**
 * Monitor Tools - 实时盯盘工具
 */
import type { ToolDefinition } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";

export const scheduleNextCheckTool: ToolDefinition = {
  name: "schedule_next_check",
  label: "设置下次检查",
  description: "根据市场状态设置下次盯盘时间",
  parameters: Type.Object({
    minutes: Type.Number({ minimum: 1, maximum: 60, description: "多少分钟后检查" }),
    reason: Type.String({ description: "为什么选择这个时间间隔" })
  }),
  execute: async (_toolCallId: string, params: any) => {
    console.log(`[Monitor] 下次检查: ${params.minutes}分钟后 (${params.reason})`);
    return { content: [{ type: "text" as const, text: JSON.stringify({
      success: true,
      next_check_minutes: params.minutes,
      reason: params.reason
    }) }], details: null };
  }
};

export const monitorTools = [scheduleNextCheckTool];
