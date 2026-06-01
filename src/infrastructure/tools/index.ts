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
import { dataFetchDividendTool } from "./data/fetch-dividend-tool.js";

// L2 因子工厂
import { factorCalculateTool } from "./factor/calculate-tool.js";
import { factorAnalyzeTool } from "./factor/factor-analyze-tool.js";

// L2.5 机会雷达（基于因子的综合评分）
import { opportunityScanTool } from "./invest/opportunity-scan-tool.js";

// L2.6 ZigZag 波段买卖点分析
import { swingPointsTool } from "./invest/swing-points-tool.js";

// L2.7 股票池管理
import { poolManageTool } from "./pool/pool-manage-tool.js";
import { poolValidateTool } from "./pool/pool-validate-tool.js";

// L3 模型层
import { modelTrainTool } from "./model/train-tool.js";
import { modelPredictTool } from "./model/predict-tool.js";
import { modelEvaluateTool } from "./model/evaluate-tool.js";
import { modelMonitorTool } from "./model/monitor-tool.js";
import { modelListTool } from "./model/list-tool.js";

// L3.5 策略执行
import { strategyBatchValidateTool } from "./strategy/batch-validate-tool.js";
import { strategyOptimizeTool } from "./strategy/optimize-tool.js";

// 指标工具（独立工具，从 quant_cli 提取）
import { indicatorListTool } from "./indicator/list-tool.js";
import { indicatorDetailTool } from "./indicator/detail-tool.js";
import { indicatorCreateTool } from "./indicator/create-tool.js";
import { indicatorUpdateTool } from "./indicator/update-tool.js";
import { indicatorDeleteTool } from "./indicator/delete-tool.js";
import { indicatorRunTool } from "./indicator/run-tool.js";
import { indicatorBacktestTool } from "./indicator/backtest-tool.js";
import { strategyWriteTool } from "./indicator/strategy-write-tool.js";
import { indicatorCompareTool } from "./indicator/compare-tool.js";
import { indicatorSandboxColumnsTool } from "./indicator/sandbox-columns-tool.js";

// L4 组合构建
// portfolioRebalanceTool 已删除（依赖已移除的服务）

// L5 执行引擎
// tradeManageOrdersTool 已删除（依赖已移除的服务）
import { algoExecuteTool } from "./trade/algo-execute-tool.js";
import { signalExecutionTool } from "./execution/signal-execution-tool.js";

// L6 监控运维
import { monitorAlertTool } from "./monitor/alert-tool.js";

// ===== Agent 元工具 =====
import { compactTool, initCompactTool } from "./agent/compact-tool.js";
import { browserTool, initBrowserTool } from "./agent/browser-tool.js";
import { taskCreateTool, taskUpdateTool, taskListTool, taskExecuteAsyncTool, taskCheckBackgroundTool, initTaskTools, initBackgroundManager, getBackgroundManager, getTaskManager } from "./agent/task-tools.js";
import { planTool } from "./agent/plan-tool.js";
import { clarifyTool } from "./agent/clarify-tool.js";
import { reflectTool } from "./agent/reflect-tool.js";
import { memoryWriteTool, memorySearchTool } from "./agent/memory-tool.js";
import { evolutionRunTool } from "./agent/evolution-tool.js";
import { queryExperienceTool } from "./agent/query-experience-tool.js";
import { experienceWriteTool } from "./agent/experience-write-tool.js";
import { restartAgentTool } from "./agent/restart-agent-tool.js";
import { backendControlTool } from "./agent/backend-control-tool.js";
import { claudeCodeTool } from './agent/claude-code-tool.js';

// ===== 核心基础设施工具（向后兼容，待迁移） =====
import { quantCliTool } from "./core/quant-cli-tool.js";

// ===== 数据管理工具 =====
// manageStockDBTool 已删除 - 使用 quant_cli 的 data.update 或 v2 pipeline API 替代

// ===== 工具支持 =====
import { scheduleNextCheckTool } from "../../tools/monitor-tools.js";

export { initCompactTool, initBrowserTool, initTaskTools, initBackgroundManager, getBackgroundManager, getTaskManager };
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
   * L3 模型层: 模型训练、预测、评估、监控
   * L4 组合构建: 持仓管理、再平衡
   * L5 执行引擎: 订单管理、交易执行
   * L6 监控运维: 告警通知、风险监控
   */
  // L1 数据管道
  dataFetchStockTool,             // data_fetch_stock - 获取股票基本信息
  dataFetchKlineTool,             // data_fetch_kline - 获取K线数据
  dataFetchFinancialTool,         // data_fetch_financial - 获取财务数据
  dataFetchDividendTool,          // data_fetch_dividend - 获取分红送股数据

  // L2 因子工厂
  factorCalculateTool,            // factor_calculate - 计算技术/基本面因子
  factorAnalyzeTool,              // factor_analyze - 分析因子IC/覆盖率/稳定性

  // L2.5 机会雷达（基于因子的综合评分）
  opportunityScanTool,            // opportunity_scan - 多维评分扫描交易机会
  swingPointsTool,                // analysis_swing_points - ZigZag 波段买卖点

  // L2.7 股票池管理
  poolManageTool,                 // pool_manage - 股票池 CRUD + 筛选建池
  poolValidateTool,               // pool_validate - 多策略批量回测验证

  // L3 模型层
  modelTrainTool,                 // model_train - 训练机器学习模型
  modelPredictTool,               // model_predict - 模型预测信号
  modelEvaluateTool,              // model_evaluate - 评估模型性能
  modelMonitorTool,               // model_monitor - 监控模型漂移
  modelListTool,                  // model_list - 列出所有模型

  // L3.5 策略执行
  strategyOptimizeTool,           // strategy_optimize - 策略参数优化
  strategyBatchValidateTool,      // strategy_batch_validate - 批量验证策略有效性

  // 指标工具
  indicatorListTool,              // indicator_list - 列出可用指标
  indicatorDetailTool,            // indicator_detail - 查看指标详情
  indicatorCreateTool,            // indicator_create - 创建自定义指标
  indicatorUpdateTool,            // indicator_update - 更新指标
  indicatorDeleteTool,            // indicator_delete - 删除指标
  indicatorRunTool,               // indicator_run - 运行指标
  indicatorBacktestTool,          // indicator_backtest - 指标历史回测
  strategyWriteTool,              // strategy_write - 编写/更新策略代码，配合回测迭代
  indicatorCompareTool,           // indicator_compare - 对比两个指标
  indicatorSandboxColumnsTool,    // indicator_sandbox_columns - 沙箱可用列

  // L4 组合构建
  // portfolioRebalanceTool 已删除

  // L5 执行引擎
  // tradeManageOrdersTool 已删除
  algoExecuteTool,                // trade_algo_execute - 算法交易执行
  signalExecutionTool,            // signal_execution - 信号执行管理

  // L6 监控运维
  monitorAlertTool,               // monitor_alert - 告警通知

  // ===== 经验库工具 =====
  queryExperienceTool,            // experience_query - 查询历史经验库
  experienceWriteTool,            // experience_write - 写入投资经验

  // ===== 量化工具 — 统一通过 QuantSys CLI 调用 =====
  quantCliTool,                   // quant_cli

  // ===== 通知 & 监控工具 — 消息推送、实时盯盘 =====
  scheduleNextCheckTool,          // schedule_next_check - 设置下次盯盘时间

  // ===== 进化工具 — 自我优化 =====
  evolutionRunTool,

  // ===== 重启工具 — 运维操作 =====
  restartAgentTool,
  backendControlTool,
  claudeCodeTool,

  // ===== 中频 — 记忆 =====
  memoryWriteTool,
  memorySearchTool,

  // ===== 低频/专用 =====
  taskCheckBackgroundTool,  // 检查后台任务
  compactTool,
  browserTool,
  readTool,
];
