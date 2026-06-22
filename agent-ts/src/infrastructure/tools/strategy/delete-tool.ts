/**
 * Strategy Delete Tool — 软删除策略（设置 is_active=false）
 *
 * 不硬删除数据库记录，通过设置 is_active=false 标记策略为停用状态。
 * 同时自动在 strategy_profile.tags 中追加 "dead" 标签。
 *
 * 如需彻底删除，请使用后端 DELETE /api/strategies/{id}（硬删除）。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { updateIndicator } from "../../adapters/quant/quant-v2-client.js";

interface DeleteParams {
  indicator_id: number;
  reason?: string;
}

export const strategyDeleteTool: ToolDefinition = {
  name: "strategy_delete",
  label: "停用策略",
  description:
    "软删除策略：设置 is_active=false + 自动追加 'dead' 标签。" +
    "不会真正删除数据库记录，策略仍然可以通过 indicator_update 恢复。" +
    "\n\n需要 indicator_id（可通过 strategy_list 查询）。" +
    "\n\n可选 reason 参数记录停用原因（写入 strategy_profile.description）。",

  parameters: Type.Object({
    indicator_id: Type.Integer({
      description: "要停用的策略ID（可通过 strategy_list 查询）",
      minimum: 1,
    }),
    reason: Type.Optional(
      Type.String({
        description: "停用原因（可选，会记录到 strategy_profile 中）",
      })
    ),
  }),

  execute: async (_toolCallId, rawParams: DeleteParams) => {
    try {
      const { indicator_id, reason } = rawParams;

      // 构建 strategy_profile 更新：追加 "dead" 标签
      const strategy_profile: Record<string, any> = {
        tags: ["dead"],
      };
      if (reason) {
        strategy_profile.description = reason;
      }

      const result = await updateIndicator(indicator_id, {
        is_active: false,
        strategy_profile,
      });

      if (result.error) {
        return {
          content: [{
            type: "text" as const,
            text: `❌ 停用策略失败: ${result.error}`,
          }],
          details: { error: result.error },
        };
      }

      const data = result.data ?? result;
      return {
        content: [{
          type: "text" as const,
          text: `✅ 策略已停用\n` +
            `  ID: ${indicator_id}\n` +
            `  名称: ${data?.name ?? data?.strategy_name ?? '?'}\n` +
            `  状态: is_active=false, tags=[dead]\n` +
            `${reason ? `  原因: ${reason}\n` : ''}` +
            `\n💡 如需恢复，使用 indicator_update 设置 is_active=true 并移除 dead 标签。`,
        }],
        details: data,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `停用策略失败: ${errorMsg}`,
        }],
        details: null,
      };
    }
  },
};
