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
import { notificationTools } from "../../tools/notification-tools.js";
import { evolutionRunTool } from "./evolution-tool.js";
import { analyze_sector_rotationTool } from "./analyze_sector_rotation-tool.js";
import { check_stop_loss_triggerTool } from "./check_stop_loss_trigger-tool.js";
import { checkPendingOrdersTool } from "./check-pending-orders.js";
import { manageOrdersTool } from "./order-tools.js";
import { testMarketSentimentTool } from "./test-market-sentiment-tool.js";
import { queryExperienceTool } from "./query-experience-tool.js";
import { tradeLogTool } from "./trade-log-tools.js";
import { restartAgentTool } from "./restart-agent-tool.js";
import { manageWatchlistTool } from "./watchlist-tools.js";
// 量化工具 - 新架构
import { quantDecisionTools } from "./quant-decision-tools.js";
import { quantAnalysisTools } from "./quant-analysis-tools.js";
import { quantStrategyTools } from "./quant-strategy-tools.js";
// 量化工具 - 旧版本（已弃用，保持向后兼容）
import { quantTools } from "./quant-tools.js";

export { initCompactTool, initBrowserTool, initTaskTools, initBackgroundManager, getBackgroundManager };
export { initMemoryTools } from "./memory-tool.js";

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
  analyze_sector_rotationTool,    // 行业轮动分析
  check_stop_loss_triggerTool,    // 止损检查
  checkPendingOrdersTool,         // 挂单检查（自动成交）
  manageOrdersTool,               // 挂单管理（创建/撤销/查看/成交）
  tradeLogTool,                   // 交易日志管理（创建/更新/追加记录）
  manageWatchlistTool,            // 关注列表管理（自选池）
  testMarketSentimentTool,        // NEW: 市场情绪分析
  // 量化工具 — 决策分析（新架构）
  ...quantDecisionTools,          // analyze_stock_quant, compare_stocks_quant, validate_trade_decision
  ...quantAnalysisTools,          // get_technical_signals, get_quant_score, query_similar_cases, backtest_strategy
  ...quantStrategyTools,          // list_quant_strategies, get_strategy_performance
  // 量化工具 — 旧版本（已弃用，保持向后兼容）
  // ...quantTools,
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
