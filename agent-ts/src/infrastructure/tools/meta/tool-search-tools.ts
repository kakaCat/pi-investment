/**
 * Tool Search 元工具三件套（T8 / W2.1）
 *
 * 设计参照：OpenClaw docs/tools/tool-search.md 三段式。
 * 非 core 工具不再全量注入 schema，agent 按需三段获取：
 *   1. tool_search(query)   —— 目录检索，返回 name + 一行简述
 *   2. tool_describe(name)  —— 返回完整 description + parameters schema + 使用细则
 *   3. tool_call(name, args) —— 校验并调用目标工具
 *
 * 注意：DeepSeek 一次只处理一个 tool call（项目已知怪癖），
 * 三段式是顺序调用，不依赖并行 tool calls。
 */

import type { ToolDefinition } from "../index.js";
import { describeTool, getToolByName, searchCatalog } from "../catalog.js";

const text = (s: string) => [{ type: "text" as const, text: s }];

export const toolSearchTool: ToolDefinition = {
  name: "tool_search",
  description:
    "搜索可用工具目录。当你需要的工具不在常驻列表中时，用关键词检索（如 \"回测\"、\"factor\"、\"pool\"）。" +
    "返回匹配工具的 name 和一行简述；拿到 name 后用 tool_describe 查看完整参数，再用 tool_call 调用。",
  parameters: {
    type: "object",
    properties: {
      query: { type: "string", description: "检索关键词（工具名或功能描述，中英文均可）" },
      limit: { type: "number", description: "返回数量上限（默认 8）" },
    },
    required: ["query"],
  },
  execute: async (_id, params) => {
    const { query, limit } = params as { query: string; limit?: number };
    const hits = searchCatalog(query, limit ?? 8);
    if (hits.length === 0) {
      return {
        content: text(`未找到匹配 "${query}" 的工具。换个关键词试试（如功能领域：数据/因子/策略/股票池/风控/模型）。`),
        details: { found: 0 },
      };
    }
    const lines = hits.map(
      (h) => `- ${h.name}${h.core ? "（常驻，可直接调用）" : ""}: ${h.summary}`
    );
    return {
      content: text(`匹配 ${hits.length} 个工具：\n${lines.join("\n")}\n\n用 tool_describe(name) 查看参数，用 tool_call(name, args) 调用。`),
      details: { found: hits.length, names: hits.map((h) => h.name) },
    };
  },
};

export const toolDescribeTool: ToolDefinition = {
  name: "tool_describe",
  description:
    "查看某个工具的完整描述、参数 schema 和使用细则。tool_search 拿到工具名后用此工具了解如何调用。",
  parameters: {
    type: "object",
    properties: {
      name: { type: "string", description: "工具名（tool_search 返回的 name）" },
    },
    required: ["name"],
  },
  execute: async (_id, params) => {
    const { name } = params as { name: string };
    const info = describeTool(name);
    if (!info) {
      return {
        content: text(`工具 "${name}" 不存在。请先用 tool_search 检索正确的工具名。`),
        details: { error: "unknown_tool", name },
      };
    }
    const guidelines = info.promptGuidelines?.length
      ? `\n\n使用细则：\n${info.promptGuidelines.map((g) => `- ${g}`).join("\n")}`
      : "";
    return {
      content: text(
        `工具：${info.name}（${info.label}）${info.core ? "【常驻工具，建议直接调用而非 tool_call】" : ""}\n\n` +
          `${info.description}\n\n参数 schema：\n${JSON.stringify(info.parameters, null, 2)}${guidelines}`
      ),
      details: { name: info.name, core: info.core },
    };
  },
};

/** 禁止经 tool_call 调用的工具：元工具自身（防自递归/无限套娃） */
const META_TOOL_NAMES = new Set(["tool_search", "tool_describe", "tool_call"]);

export const toolCallTool: ToolDefinition = {
  name: "tool_call",
  description:
    "调用一个非常驻工具。先用 tool_describe 确认参数 schema，再把参数放进 args 调用。" +
    "常驻工具（提示词中已列出完整参数的）请直接调用，不要用 tool_call 包装。",
  parameters: {
    type: "object",
    properties: {
      name: { type: "string", description: "目标工具名" },
      args: { type: "object", description: "目标工具的参数对象（按 tool_describe 返回的 schema 填写）" },
    },
    required: ["name", "args"],
  },
  execute: async (toolCallId, params, signal, onUpdate) => {
    const { name, args } = params as { name: string; args: Record<string, unknown> };

    if (META_TOOL_NAMES.has(name)) {
      return {
        content: text(`"${name}" 是元工具，不能通过 tool_call 调用——直接调用它本身。`),
        details: { error: "meta_tool_recursion", name },
      };
    }

    const target = getToolByName(name);
    if (!target) {
      // 给一次近似建议，减少 agent 试错往返
      const suggestions = searchCatalog(name, 3).map((s) => s.name);
      return {
        content: text(
          `工具 "${name}" 不存在。${suggestions.length ? `你是不是想用：${suggestions.join("、")}？` : "请先用 tool_search 检索。"}`
        ),
        details: { error: "unknown_tool", name, suggestions },
      };
    }

    // 参数必填项校验（轻量：按 schema.required 检查存在性）
    const schema = target.parameters as { required?: string[] };
    const missing = (schema.required ?? []).filter(
      (k) => args == null || !(k in args)
    );
    if (missing.length > 0) {
      return {
        content: text(`参数缺失：${missing.join(", ")}。请按 tool_describe("${name}") 的 schema 补齐后重试。`),
        details: { error: "missing_args", name, missing },
      };
    }

    // 直接调用目标工具的 execute（hook 已在 tool_call 本层触发过一次，不重复拦截）
    const result = await target.execute(
      `${toolCallId}__${name}`,
      args ?? {},
      signal,
      onUpdate
    );
    return result;
  },
};

/** 三件套（注册顺序 = 提示词顺序） */
export const toolSearchMetaTools: ToolDefinition[] = [
  toolSearchTool,
  toolDescribeTool,
  toolCallTool,
];
