/**
 * Strategy List Tool — 列出所有策略
 *
 * 列出系统所有已注册策略，返回策略ID、名称、状态等信息。
 *
 * 从 quant_cli 的 strategy.list 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

export const strategyListTool: ToolDefinition = {
  name: "strategy_list",
  label: "列出策略",
  description:
    "列出系统所有已注册策略。返回每个策略的 ID、名称、类型和状态。" +
    "可用于查找 strategy_id 供其他策略工具使用。",

  parameters: Type.Object({}),

  execute: async (_toolCallId) => {
    try {
      const result = await runQuantV2("strategy.list", {});
      const data = result.data ?? result;
      const items = data.items ?? data.strategies ?? data;

      // 格式化输出，显示 is_active / validation_status / tags
      const formatted = Array.isArray(items)
        ? items.map((s: any) => ({
            id: s.id ?? s.strategy_id,
            name: s.name ?? s.strategy_name ?? '?',
            type: s.type ?? s.code_type ?? '?',
            is_active: s.is_active !== undefined ? s.is_active : true,
            validation_status: s.validation_status ?? '?',
            tags: Array.isArray(s.tags) ? s.tags : [],
            status: s.status ?? '?',
            description: s.description ?? '',
          }))
        : [items];

      // 汇总统计
      const activeCount = formatted.filter((s: any) => s.is_active).length;
      const deadCount = formatted.filter((s: any) => !s.is_active).length;
      const deadTaggedCount = formatted.filter((s: any) => s.tags.includes('dead')).length;

      const summary = `📊 共 ${formatted.length} 个策略 | ✅ 活跃: ${activeCount} | ❌ 停用: ${deadCount} | 💀 标记dead: ${deadTaggedCount}`;

      const listLines = formatted.map((s: any) => {
        const activeIcon = s.is_active ? '✅' : '❌';
        const tagStr = s.tags.length > 0 ? ` [${s.tags.join(', ')}]` : '';
        return `${activeIcon} ID:${s.id} | ${s.name} | ${s.type} | ${s.validation_status}${tagStr}`;
      });

      return {
        content: [{
          type: "text" as const,
          text: summary + '\n\n' + listLines.join('\n'),
        }],
        details: { raw: formatted },
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `列出策略失败: ${errorMsg}`,
        }],
        details: null,
      };
    }
  },
};
