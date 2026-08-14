/**
 * Tool Catalog（T8 / W2.1 Tool Search 三段式）
 *
 * 设计参照：OpenClaw docs/tools/tool-search.md
 * 动机：121 个工具全量塞 system prompt + 每请求全量 JSON schema，
 *       冷启动信封 ~40K token（见 docs/superpowers/specs/2026-08-13-prompt-cache-audit.md）。
 *       三段式把 schema 面压到 core 常驻集 + 3 个元工具：
 *       目录只放 name+一行简述（tool_search），schema 延迟到 tool_describe，调用走 tool_call。
 *
 * 本模块是唯一权威：core 集名单、目录条目、检索、按名取工具。
 */

import { allCustomTools, type ToolDefinition } from "./index.js";

/**
 * Tool Search 模式开关。默认开启（T8 落地后基线）；
 * PI_TOOL_SEARCH=off 一键回退全量工具注入（实测闸不过时的逃生门）。
 */
export function isToolSearchMode(): boolean {
  return process.env.PI_TOOL_SEARCH !== "off";
}

/**
 * Core 常驻集（全量 schema 每请求携带）。
 * 选入标准（2026-08-13 主抓定稿）：
 * - 工作流脊柱（plan/task/reflect/clarify）——所有会话类型每轮都用
 * - cron 任务 prompt 直接引用（实证：agent-decision-tasks.ts 引用统计）
 * - 记忆/经验闭环（W1 系列依赖，召回→写入每轮发生）
 * - 自运维（compact/restart_agent/feishu_notify）
 * 其余 ~95 个工具走 tool_search 目录。
 */
export const CORE_TOOL_NAMES: ReadonlySet<string> = new Set([
  // 工作流脊柱
  "plan_task",
  "clarify",
  "task_create",
  "task_update",
  "task_list",
  "task_execute_async",
  "reflect",
  // 记忆与经验（W1 闭环）
  "memory_write",
  "memory_search",
  "query_experience",
  "experience_write",
  // 持仓与交易（cron 高频）
  "portfolio_status",
  "portfolio_trade",
  "portfolio_analyze",
  // 数据（最高频两个）
  "data_fetch_quote",
  "data_fetch_kline",
  // 盯盘与调度
  "watch_manage",
  "scheduler_manage",
  // 决策审计（cron 引用）
  "decision_record",
  "decision_history",
  // 告警通知
  "market_alert",
  "feishu_notify",
  "notification_send",
  // 文件与上下文自运维
  "read",
  "compact",
  "restart_agent",
]);

/** 目录条目：name + 一行简述（从 description 首行截取） */
export interface ToolCatalogEntry {
  name: string;
  label: string;
  summary: string;
  /** true = core 常驻（schema 已在上下文，无需 tool_describe） */
  core: boolean;
}

function toSummary(description: string): string {
  const firstLine = (description || "").split("\n")[0].trim();
  return firstLine.length > 80 ? firstLine.slice(0, 80) + "…" : firstLine;
}

let catalogCache: ToolCatalogEntry[] | null = null;

/** 全量目录（含 core 标记），构建一次后缓存 */
export function getToolCatalog(): ToolCatalogEntry[] {
  if (catalogCache) return catalogCache;
  catalogCache = allCustomTools.map((t) => ({
    name: t.name,
    label: t.label || t.name,
    summary: toSummary(t.description),
    core: CORE_TOOL_NAMES.has(t.name),
  }));
  return catalogCache;
}

/** 全量注册表（allCustomTools 是异构联合类型——含 TypeBox AgentTool，统一断言为 ToolDefinition） */
function registry(): ToolDefinition[] {
  return allCustomTools as unknown as ToolDefinition[];
}

/** core 常驻工具定义（保持 allCustomTools 原顺序 = 提示词顺序） */
export function getCoreTools(): ToolDefinition[] {
  return registry().filter((t) => CORE_TOOL_NAMES.has(t.name));
}

/** 按名取工具（tool_call/tool_describe 用）；未知名返回 undefined */
export function getToolByName(name: string): ToolDefinition | undefined {
  return registry().find((t) => t.name === name);
}

/**
 * 目录检索：名字精确/前缀 > 名字子串 > 简述关键词重叠。
 * 纯字符串打分（目录仅 ~121 条，无需 BM25）。
 */
export function searchCatalog(query: string, limit = 8): ToolCatalogEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const terms = q.split(/[\s,，、]+/).filter(Boolean);
  const catalog = getToolCatalog();

  const scored = catalog.map((entry) => {
    const name = entry.name.toLowerCase();
    const summary = entry.summary.toLowerCase();
    let score = 0;
    if (name === q) score += 100;
    if (name.startsWith(q)) score += 50;
    if (name.includes(q)) score += 30;
    for (const term of terms) {
      if (term.length < 2) continue;
      if (name.includes(term)) score += 10;
      if (summary.includes(term)) score += 4;
    }
    return { entry, score };
  });

  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((s) => s.entry);
}

/** tool_describe 的完整描述载荷：description + parameters schema + 使用细则 */
export function describeTool(name: string): {
  name: string;
  label: string;
  description: string;
  parameters: Record<string, unknown>;
  promptGuidelines?: string[];
  core: boolean;
} | undefined {
  const tool = getToolByName(name);
  if (!tool) return undefined;
  return {
    name: tool.name,
    label: tool.label || tool.name,
    description: tool.description,
    parameters: tool.parameters,
    ...(tool.promptGuidelines ? { promptGuidelines: tool.promptGuidelines } : {}),
    core: CORE_TOOL_NAMES.has(tool.name),
  };
}
