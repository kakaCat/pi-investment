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
// 量化工具 - V2 新架构（通过 Python API）
import { quantDecisionTools } from "./quant-decision-tools-v2.js";
// 量化工具 - V1 旧架构（直接访问数据库，已弃用）
// import { quantDecisionTools as quantDecisionToolsV1 } from "./quant-decision-tools.js";
// import { quantAnalysisTools } from "./quant-analysis-tools.js";
// import { quantStrategyTools } from "./quant-strategy-tools.js";
// import { quantTools } from "./quant-tools.js";
// 因子分析工具 - 模型可解释性
import { factorAnalysisTools } from "../../tools/factor-analysis-tools.js";
// 风险管理工具
import { riskTools } from "./invest/risk-tools.js";

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
  // 量化工具 — V2 新架构（通过 Python API）
  ...quantDecisionTools,          // analyze_stock_quant, get_quant_signals
  // 量化工具 — V1 旧架构（已弃用）
  // ...quantAnalysisTools,
  // ...quantStrategyTools,
  // ...quantTools,
  // 因子分析工具 — 模型可解释性
  ...factorAnalysisTools,         // get_feature_importance, analyze_stock_factors, compare_stock_factors
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
