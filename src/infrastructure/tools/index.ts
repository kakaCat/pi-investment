/**
 * Tools Registry - 自动收集所有自定义工具
 *
 * 新增工具只需：
 * 1. 在此目录或 services/ 下创建工具文件
 * 2. 在下方 import 并加入 allCustomTools 数组
 */
import type { ToolDefinition as BaseToolDefinition } from "@mariozechner/pi-coding-agent";

/**
 * Extended ToolDefinition with prompt guidance fields
 */
export interface ToolDefinition extends BaseToolDefinition {
  promptSnippet?: string;
  promptGuidelines?: string[];
}
import { readTool } from "@mariozechner/pi-coding-agent";
// Agent 元工具
import { compactTool, initCompactTool } from "./agent/compact-tool.js";
import { browserTool, initBrowserTool } from "./agent/browser-tool.js";
import { taskCreateTool, taskUpdateTool, taskListTool, taskGetTool, taskExecuteAsyncTool, taskCheckBackgroundTool, initTaskTools, initBackgroundManager, getBackgroundManager } from "./agent/task-tools.js";
import { planTool } from "./agent/plan-tool.js";
import { clarifyTool } from "./agent/clarify-tool.js";
import { reflectTool } from "./agent/reflect-tool.js";
import { memoryWriteTool, memorySearchTool } from "./agent/memory-tool.js";
import { evolutionRunTool } from "./agent/evolution-tool.js";
import { queryExperienceTool } from "./agent/query-experience-tool.js";
import { restartAgentTool } from "./agent/restart-agent-tool.js";
// 核心基础设施工具
import { investTools } from "./core/invest-tools.js";
import { quantCliTool } from "./core/quant-cli-tool.js";
// 数据管理工具
import { stockDBTools } from "./data/stock-db-tools.js";
// 量化分析工具
import { analyzeSectorRotationTool } from "./analysis/analyze-sector-rotation-tool.js";
import { checkStopLossTriggerTool } from "./analysis/check-stop-loss-trigger-tool.js";
import { testMarketSentimentTool } from "./analysis/test-market-sentiment-tool.js";
// 交易管理工具
import { checkPendingOrdersTool } from "./trading/check-pending-orders.js";
import { manageOrdersTool } from "./trading/order-tools.js";
import { tradeLogTool } from "./trading/trade-log-tools.js";
import { manageWatchlistTool } from "./trading/watchlist-tools.js";
// 工具支持
import { wrapInvestToolWithSkillGuard } from "./skill-guard.js";
import { monitorTools } from "../../tools/monitor-tools.js";
import { notificationTools } from "../../tools/notification-tools.js";
// 风险管理工具 - 风控与仓位管理
import { riskTools } from "./invest/risk-tools.js";

export { initCompactTool, initBrowserTool, initTaskTools, initBackgroundManager, getBackgroundManager };
export { initMemoryTools } from "./agent/memory-tool.js";
export { initRestartAgentTool } from "./agent/restart-agent-tool.js";

/**
 * 内置工具列表
 *
 * 顺序说明：
 * - 此数组的顺序 = 系统提示词中的工具列表顺序
 * - 高频工具在前（plan, clarify, task 等）
 * - 投资分析工具居中
 * - 低频工具在后（compact, browser 等）
 *
 * 调整顺序：直接在此数组中移动工具位置即可
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
  queryExperienceTool,            // 查询历史经验库
  analyzeSectorRotationTool,      // 行业轮动分析
  checkStopLossTriggerTool,       // 止损检查
  checkPendingOrdersTool,         // 挂单检查（自动成交）
  manageOrdersTool,               // 挂单管理（创建/撤销/查看/成交）
  tradeLogTool,                   // 交易日志管理（创建/更新/追加记录）
  manageWatchlistTool,            // 关注列表管理（自选池）
  testMarketSentimentTool,        // NEW: 市场情绪分析
  // 量化工具 — 统一通过 QuantSys CLI 调用
  quantCliTool,                   // quant_cli
  // 风险管理工具 — 风控与仓位管理
  ...riskTools,                   // check_trade_risk, calculate_position_size, calculate_stop_loss
  // 通知工具 — 消息推送
  ...notificationTools,
  // 监控工具 — 实时盯盘
  ...monitorTools,
  // 进化工具 — 自我优化
  evolutionRunTool,
  // 重启工具 — 运维操作
  restartAgentTool,
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
