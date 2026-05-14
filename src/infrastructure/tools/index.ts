/**
 * Tools Registry - 自动收集所有自定义工具
 *
 * 新增工具只需：
 * 1. 在此目录或 services/ 下创建工具文件
 * 2. 在下方 import 并加入 allCustomTools 数组
 */
export type { ToolDefinition } from "@mariozechner/pi-coding-agent";
import { readTool } from "@mariozechner/pi-coding-agent";
import { compactTool, initCompactTool } from "./compact-tool.js";
import { browserTool, initBrowserTool } from "./browser-tool.js";
import { taskCreateTool, taskUpdateTool, taskListTool, taskGetTool, taskExecuteAsyncTool, taskCheckBackgroundTool, initTaskTools, initBackgroundManager, getBackgroundManager } from "./task-tools.js";
import { planTool } from "./plan-tool.js";
import { clarifyTool } from "./clarify-tool.js";
import { reflectTool } from "./reflect-tool.js";
import { memoryWriteTool, memorySearchTool } from "./memory-tool.js";
import { investTools } from "./invest-tools.js";
import { stockDBTools } from "./stock-db-tools.js";
import { wrapInvestToolWithSkillGuard } from "./skill-guard.js";
import { monitorTools } from "../../tools/monitor-tools.js";

export { initCompactTool, initBrowserTool, initTaskTools, initBackgroundManager, getBackgroundManager };
export { initMemoryTools } from "./memory-tool.js";

/**
 * 所有自定义工具列表 — agent-loop 直接使用此数组
 *
 * 排序原则：高频工具靠前，专用/低频工具靠后。
 * LLM 对工具列表靠前的条目权重更高，高频工具放前面可降低选错工具的概率。
 *
 * 高频（每个任务都要用）:    plan_task → clarify → task_create → task_update → task_list → reflect
 * 投资工具（核心业务）:      market overview → stock info → analysis → screening → portfolio
 * 中频（大多数任务用到）:    memory_write / memory_search
 * 低频/专用（按需使用）:     task_get / spawn / compact
 */
export const allCustomTools = [
  // 高频 — 工作流核心
  planTool,
  clarifyTool,
  taskCreateTool,
  taskUpdateTool,
  taskExecuteAsyncTool,  // 新增：异步并行执行
  taskListTool,
  reflectTool,
  // 投资工具 — 核心业务
  ...investTools.map(wrapInvestToolWithSkillGuard),
  ...stockDBTools,
  // 监控工具 — 实时盯盘
  ...monitorTools,
  // 中频 — 记忆
  memoryWriteTool,
  memorySearchTool,
  // 低频/专用
  taskGetTool,
  taskCheckBackgroundTool,  // 新增：检查后台任务
  compactTool,
  browserTool,
  readTool,
];
