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

// ===== 六层量化投资架构工具 =====
// L1 数据管道
import { dataFetchStockTool } from "./data/fetch-stock-tool.js";
import { dataFetchKlineTool } from "./data/fetch-kline-tool.js";
import { dataFetchFinancialTool } from "./data/fetch-financial-tool.js";

// L2 因子工厂
import { factorCalculateTool } from "./factor/calculate-tool.js";

// L4 组合构建
import { portfolioRebalanceTool } from "./portfolio/rebalance-tool.js";

// L5 执行引擎
import { tradeManageOrdersTool } from "./trade/manage-orders-tool.js";

// L6 监控运维
import { monitorAlertTool } from "./monitor/alert-tool.js";

// ===== Agent 元工具 =====
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

// ===== 核心基础设施工具（向后兼容，待迁移） =====
import { quantCliTool } from "./core/quant-cli-tool.js";

// ===== 数据管理工具 =====
import { stockDBTools } from "./data/stock-db-tools.js";

// ===== 工具支持 =====
import { monitorTools } from "../../tools/monitor-tools.js";
import { notificationTools } from "../../tools/notification-tools.js";

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
  // ===== 高频 — 工作流核心 =====
  planTool,
  clarifyTool,
  taskCreateTool,
  taskUpdateTool,
  taskExecuteAsyncTool,  // 新增：异步并行执行
  taskListTool,
  reflectTool,

  // ===== 六层量化投资架构工具 =====
  /**
   * L1 数据管道: 行情数据、财务数据获取
   * L2 因子工厂: 因子计算、IC分析
   * L3 模型层: 特征工程、模型训练（待实现）
   * L4 组合构建: 持仓管理、再平衡
   * L5 执行引擎: 订单管理、交易执行
   * L6 监控运维: 告警通知、风险监控
   */
  // L1 数据管道
  dataFetchStockTool,             // data_fetch_stock - 获取股票基本信息
  dataFetchKlineTool,             // data_fetch_kline - 获取K线数据
  dataFetchFinancialTool,         // data_fetch_financial - 获取财务数据

  // L2 因子工厂
  factorCalculateTool,            // factor_calculate - 计算技术/基本面因子

  // L4 组合构建
  portfolioRebalanceTool,         // portfolio_rebalance - 组合再平衡

  // L5 执行引擎
  tradeManageOrdersTool,          // trade_manage_orders - 订单管理

  // L6 监控运维
  monitorAlertTool,               // monitor_alert - 告警通知

  // ===== 保留的旧工具（向后兼容，待迁移） =====
  ...stockDBTools,
  queryExperienceTool,            // 查询历史经验库

  // ===== 量化工具 — 统一通过 QuantSys CLI 调用 =====
  quantCliTool,                   // quant_cli

  // ===== 通知工具 — 消息推送 =====
  ...notificationTools,

  // ===== 监控工具 — 实时盯盘 =====
  ...monitorTools,

  // ===== 进化工具 — 自我优化 =====
  evolutionRunTool,

  // ===== 重启工具 — 运维操作 =====
  restartAgentTool,

  // ===== 中频 — 记忆 =====
  memoryWriteTool,
  memorySearchTool,

  // ===== 低频/专用 =====
  taskGetTool,
  taskCheckBackgroundTool,  // 新增：检查后台任务
  compactTool,
  browserTool,
  readTool,
];
