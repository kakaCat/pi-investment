/**
 * load_tools — 动态工具加载元工具
 *
 * 当 LLM 需要 Core 之外的工具时，调用此工具加载对应的工具组。
 * 加载在当前 run 结束后生效：SDK 在 run 开始时快照工具列表，
 * 因此 run 内加载的工具不能立即调用；系统会在本任务结束后
 * 自动续跑一轮，届时新工具可用（见 promptWithDynamicTools）。
 *
 * 此工具始终在 Core 工具集中，不占用额外 token。
 */

import type { ToolDefinition } from "../index.js";
import { loadToolGroups, listGroups } from "../tool-groups.js";

export const loadToolsTool: ToolDefinition = {
  name: "load_tools",
  description:
    "加载额外的工具组。当需要执行 Core 工具不支持的操作时调用此工具。" +
    "可用工具组: factor_analysis(因子分析), strategy_dev(策略开发), indicator_dev(指标开发), " +
    "model_ml(ML模型), portfolio_ops(交易持仓), deep_analysis(深度分析), " +
    "game_theory(博弈分析), rotations(策略轮动), screening(筛选), admin(系统管理)。" +
    "可一次加载多个组。重要：加载后请勿在同一轮立即调用新工具（会报 Tool not found）——" +
    "先用现有工具继续推进，任务结束后系统会自动续跑，新工具届时生效。",
  parameters: {
    type: "object",
    properties: {
      groups: {
        type: "array",
        items: { type: "string" },
        description: "要加载的工具组名称列表，如 ['factor_analysis', 'deep_analysis']",
      },
    },
    required: ["groups"],
  },
  execute: async (_toolCallId, params) => {
    const { groups } = params as { groups: string[] };

    const availableGroups = listGroups().map(g => g.name);
    const invalid = groups.filter((g: string) => !availableGroups.includes(g));

    if (invalid.length > 0) {
      return {
        content: [{ type: "text" as const, text: `❌ 未知工具组: ${invalid.join(", ")}。可用组: ${availableGroups.join(", ")}` }],
        details: { error: `Unknown groups: ${invalid.join(", ")}` },
      };
    }

    try {
      const result = await loadToolGroups(groups);

      const text = [
        `✅ 已加载 ${result.totalTools} 个工具 (Core + ${result.loaded.join(", ")})`,
        `新增 ${result.newTools.length} 个工具: ${result.newTools.slice(0, 10).join(", ")}${result.newTools.length > 10 ? ` ...等${result.newTools.length}个` : ""}`,
        ``,
        `⚠️ 不要在本轮直接调用这些新工具（会报 Tool not found）。请先用现有工具继续推进；`,
        `本任务结束后系统会自动续跑一轮，届时新工具可直接调用。`,
      ].join("\n");

      return {
        content: [{ type: "text" as const, text }],
        details: { loaded: result.loaded, newTools: result.newTools, totalTools: result.totalTools },
      };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `❌ 加载工具组失败: ${error}` }],
        details: { error: String(error) },
      };
    }
  },
};

/**
 * 列出当前可用工具组（供 load_tools 工具描述使用）
 */
export function getLoadToolsPrompt(): string {
  const groups = listGroups();
  return groups.map(g => `  - ${g.name}: ${g.description} (${g.toolCount} tools)`).join("\n");
}
