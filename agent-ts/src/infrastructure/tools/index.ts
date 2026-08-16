/**
 * Tools Registry - 自动收集所有自定义工具
 *
 * 新增工具只需：
 * 1. 在此目录或 services/ 下创建工具文件
 * 2. 在下方 import 并加入 allCustomTools 数组
 */
import type { PiToolDefinition } from "../../sdk-facade.js";
import { createReadTool } from "../../sdk-facade.js";

/**
 * Extended ToolDefinition with prompt guidance fields
 */
export interface ToolDefinition extends PiToolDefinition {
  promptSnippet?: string;
  promptGuidelines?: string[];
}

const readTool = createReadTool(process.cwd());

// ===== 六层量化投资架构工具 =====
// L1 数据管道
import { dataFetchQuoteTool } from "./data/fetch-stock-tool.js";
import { dataFetchKlineTool } from "./data/fetch-kline-tool.js";
import { dataFetchFinancialTool } from "./data/fetch-financial-tool.js";
import { dataFetchDividendTool } from "./data/fetch-dividend-tool.js";
import { dataFetchMacroTool } from "./data/fetch-macro-tool.js";  // 新增：宏观经济数据
import { dataFetchNorthFlowTool } from "./data/fetch-north-flow-tool.js";  // 新增：北向资金流向
import { dataFetchMarketSentimentTool } from "./data/fetch-market-sentiment-tool.js";  // 新增：市场情绪分析
import { dataManagerTool } from "./data/data-manager-tool.js";  // 新增：数据管理工具
import { dataQualityReportTool } from "./data/data-quality-report-tool.js";  // 新增：数据质量监控
import { dataQualityManageTool } from "./data/quality-manage-tool.js";  // 新增：数据补救管理（2026-06-04）

// 风险控制
import { riskControllerTool } from "./risk/risk-controller-tool.js";  // 新增：风险控制工具
import { riskMetricsTool } from "./risk/risk-metrics-tool.js";         // 新增：风险指标工具
import { riskBarraDecompositionTool } from "./risk/barra-decomposition-tool.js";  // 新增：Barra风险分解

// 分析工具
import { factorModelAttributionTool } from "./analysis/factor-model-attribution-tool.js";  // 新增：因子模型归因
import { strategyComparisonTool } from "./analysis/strategy-comparison-tool.js";  // 新增：策略性能对比
import { backtestStatsTool } from "./analysis/backtest-stats-tool.js";  // 新增：回测统计
import { backtestHistoryTool } from "./analysis/backtest-history-tool.js";  // 新增：回测历史查询

// 交易监控
import { tradeMonitorTool } from "./trade/trade-monitor-tool.js";  // 新增：交易监控工具

// 组合优化
import { portfolioOptimizerTool } from "./portfolio/portfolio-optimizer-tool.js";  // 新增：组合优化工具
import { portfolioTradeTool } from "./portfolio/portfolio-trade-tool.js";  // 新增：虚拟仓交易
import { portfolioStatusTool } from "./portfolio/portfolio-status-tool.js";  // 新增：虚拟仓状态
import { portfolioDailyBriefTool } from "./portfolio/portfolio-daily-brief-tool.js";  // 新增：每日对账单
import { tradeJournalTool } from "./journal/trade-journal-tool.js";  // 新增：统一交易簿记
import { portfolioAnalyzeTool } from "./portfolio/portfolio-analyze-tool.js";  // 新增：持仓分析
import { portfolioAccountTool } from "./portfolio/portfolio-account-tool.js";  // 新增：账户管理

// 性能分析
import { performanceAnalyzerTool } from "./performance/performance-analyzer-tool.js";  // 新增：性能分析工具

// 学术因子
import { factorAcademicTool } from "./academic/factor-academic-tool.js";  // 新增：学术因子工具

// 时间序列分析
import { timeseriesAnalyzerTool } from "./timeseries/timeseries-analyzer-tool.js";  // 新增：时间序列分析工具

// 市场分析
import { marketStyleDetectTool } from "./market/market-style-detect-tool.js";  // 新增：市场风格检测工具

// 博弈情报
import { opponentBehaviorTool } from "./game/opponent-behavior-tool.js";  // 新增：对手行为分析
import { poolBattlefieldTool } from "./game/pool-battlefield-tool.js";    // 新增：池子战场评估
import { manipulationDetectTool } from "./game/manipulation-detect-tool.js"; // 新增：操纵检测
import { verifyJudgmentsTool } from "./learning/verify-judgments-tool.js";     // 新增：判断自校验（学习闭环）

// 策略轮动决策工具链
import { rotationProposalTool, rotationSimulateTool, rotationExecuteTool, rotationVerifyTool } from "./rotation/index.js";

// 决策追踪
import { decisionHistoryTool } from "./decision/decision-history-tool.js";  // 新增：决策历史查询
import { decisionRecordTool } from "./decision/decision-record-tool.js";  // 新增：决策记录

// 调度器管理
import { schedulerManageTool } from "./scheduler/scheduler-manage-tool.js";  // 新增：调度器管理工具
import { feishuNotifyTool } from "./notification/feishu-notify-tool.js";  // 新增：飞书通知工具
import { notificationSendTool, notificationListChannelsTool } from "./notification/notification-tools.js";  // 新增：通知系统工具

// L2 因子工厂
import { factorCalculateTool } from "./factor/calculate-tool.js";
import { factorAnalyzeTool } from "./factor/factor-analyze-tool.js";
import { factorLayeringBacktestTool } from "./factor/layering-backtest-tool.js";
import { batchFactorLayeringBacktestTool } from "./factor/batch-layering-backtest-tool.js";
import { factorListTool } from "./factor/list-tool.js";
import { factorCorrelationTool } from "./factor/correlation-tool.js";
import { factorPortfolioOptimizeTool } from "./factor/portfolio-optimize-tool.js";
import { factorICMonitorTool } from "./factor/ic-monitor-tool.js";

// L2.5 机会雷达（基于因子的综合评分）
import { opportunityScanTool } from "./invest/opportunity-scan-tool.js";

// L2.6 ZigZag 波段买卖点分析
import { swingPointsTool } from "./invest/swing-points-tool.js";

// L2.65 实时信号扫描（解决信号滞后问题）
import { realtimeSignalTool } from "./signal/realtime-signal-tool.js";

// L2.7 股票池管理
import { poolManageTool } from "./pool/pool-manage-tool.js";
import { poolValidateTool } from "./pool/pool-validate-tool.js";

// L2.8 组合策略回测
import { comboBacktestTool } from "./backtest/combo-backtest-tool.js";

// L3 模型层
import { modelTrainTool } from "./model/train-tool.js";
import { modelPredictTool } from "./model/predict-tool.js";
import { modelEvaluateTool } from "./model/evaluate-tool.js";
import { modelMonitorTool } from "./model/monitor-tool.js";
import { modelListTool } from "./model/list-tool.js";

// L3.5 策略（独立工具）
import { strategyListTool } from "./strategy/list-tool.js";
import { strategyDetailTool } from "./strategy/detail-tool.js";
import { strategyStatusTool } from "./strategy/status-tool.js";
import { strategyExecuteTool } from "./strategy/execute-tool.js";
import { strategyWriteTool } from "./strategy/write-tool.js";
import { strategyOptimizeTool } from "./strategy/optimize-tool.js";
import { strategyBatchValidateTool } from "./strategy/batch-validate-tool.js";
import { strategyDeleteTool } from "./strategy/delete-tool.js";
import { strategyDiscoveryTool } from "./strategy/strategy-discovery-tool.js";  // 新增：策略发现工具

// 指标工具（独立工具）
import { indicatorListTool } from "./indicator/list-tool.js";
import { indicatorDetailTool } from "./indicator/detail-tool.js";
import { indicatorCreateTool } from "./indicator/create-tool.js";
import { indicatorUpdateTool } from "./indicator/update-tool.js";
import { indicatorDeleteTool } from "./indicator/delete-tool.js";
import { indicatorBacktestTool } from "./indicator/backtest-tool.js";

// L4 组合构建层
// 注：portfolioRebalanceTool 已移除（2026-05-27，依赖已废弃的本地服务）

// L5 执行引擎层
// 注：tradeManageOrdersTool 已移除（2026-05-27，依赖已废弃的本地服务）
import { algoExecuteTool } from "./trade/algo-execute-tool.js";
import { signalExecutionTool } from "./execution/signal-execution-tool.js";

// L6 监控运维
import { monitorAlertTool } from "./monitor/alert-tool.js";
import { marketAlertTool } from "./alert/market-alert-tool.js";

// ===== Agent 元工具 =====
import { compactTool, initCompactTool } from "./agent/compact-tool.js";
import { browserTool, initBrowserTool } from "./agent/browser-tool.js";
import { taskCreateTool, taskUpdateTool, taskListTool, taskExecuteAsyncTool, taskCheckBackgroundTool, initTaskTools, initBackgroundManager, getBackgroundManager, getTaskManager } from "./agent/task-tools.js";
import { planTool } from "./agent/plan-tool.js";
import { clarifyTool } from "./agent/clarify-tool.js";
import { reflectTool } from "./agent/reflect-tool.js";
import { memoryWriteTool, memorySearchTool } from "./agent/memory-tool.js";
import { recallAuditTool } from "./agent/recall-audit-tool.js";
import { evolutionRunTool } from "./agent/evolution-tool.js";
import { queryExperienceTool } from "./agent/query-experience-tool.js";
import { experienceWriteTool } from "./agent/experience-write-tool.js";
import { restartAgentTool } from "./agent/restart-agent-tool.js";
import { backendControlTool } from "./agent/backend-control-tool.js";
import { claudeCodeTool } from './agent/claude-code-tool.js';
import { toolStatsQueryTool } from './agent/tool-stats-tool.js';
import { modelSwitchTool } from './agent/model-switch-tool.js';
import { skillFileTool } from './evolution/skill-file-tool.js';

// ===== Skill Hub 工具（Agent OS 集成）=====
import { skillListTool } from './skill/skill-list-tool.js';
import { skillGetTool } from './skill/skill-get-tool.js';
import { skillUpdateTool } from './skill/skill-update-tool.js';

// ===== CLI 领域工具已全部移除（2026-07-19 P0 清理）=====
// market_cli/stock_cli/sentiment_cli/analysis_cli/watchlist_cli 从未注册进
// allCustomTools（死代码），统计数据中的调用为历史化石。数据访问请走
// data_fetch_* / factor_* / opportunity_scan 等 v2 工具。

// ===== 从 quant_cli 拆分的独立工具 =====
import { screeningTool } from "./screening/screening-tool.js";
import { sectorAnalysisTool } from "./analysis/sector-analysis-tool.js";
import { benchmarkCompareTool } from "./analysis/benchmark-compare-tool.js";
import { chanAnalyzeTool } from "./analysis/chan-analyze-tool.js";
import { chipAnalysisTool } from "./analysis/chip-analysis-tool.js";
import { evolutionLeaderboardTool } from "./performance/evolution-leaderboard-tool.js";
import { watchAlertTool } from "./monitor/watch-alert-tool.js";
import { watchManageTool } from "./monitor/watch-manage-tool.js";
import { tradeVerifyTool } from "./trade/trade-verify-tool.js";
import { dailyReportTool } from "./report/daily-report-tool.js";
import { asyncJobsTool } from "./core/async-jobs-tool.js";
import { calibrateTool } from "./model/calibrate-tool.js";
import { trainingReportsTool } from "./model/training-reports-tool.js";

// ===== 数据管理工具 =====
// manageStockDBTool 已删除 - 使用独立的 data 工具替代

// ===== 工具支持 =====

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
  dataFetchQuoteTool,             // data_fetch_quote - 获取股票实时行情
  dataFetchKlineTool,             // data_fetch_kline - 获取K线数据
  dataFetchFinancialTool,         // data_fetch_financial - 获取财务数据
  dataFetchDividendTool,          // data_fetch_dividend - 获取分红送股数据
  dataFetchMacroTool,             // data_fetch_macro - 获取宏观经济数据（新增）
  dataFetchNorthFlowTool,         // data_fetch_north_flow - 获取北向资金流向（新增）
  dataFetchMarketSentimentTool,   // data_fetch_market_sentiment - 获取市场情绪分析（新增）
  dataManagerTool,                // data_manager - 数据管理工具（新增：从quant_cli拆分）
  dataQualityReportTool,          // data_quality_report - 数据质量监控（新增）
  dataQualityManageTool,          // data_quality_manage - 数据补救管理（新增：2026-06-04）

  // L2 因子工厂
  factorCalculateTool,            // factor_calculate - 计算技术/基本面因子
  factorAnalyzeTool,              // factor_analyze - 分析因子IC/覆盖率/稳定性
  factorLayeringBacktestTool,     // factor_layering_backtest - 因子分层回测验证有效性
  batchFactorLayeringBacktestTool, // batch_factor_layering_backtest - 批量因子分层回测
  factorListTool,                 // factor_list - 查看所有可用因子及分类（新增）
  factorCorrelationTool,          // factor_correlation - 因子相关性分析（新增）
  factorPortfolioOptimizeTool,    // factor_portfolio_optimize - 因子组合优化（新增）
  factorICMonitorTool,            // factor_ic_monitor - 因子IC时序监控（新增）

  // L2.5 机会雷达（基于因子的综合评分）
  opportunityScanTool,            // opportunity_scan - 多维评分扫描交易机会（支持固定/自定义/动态权重）
  swingPointsTool,                // analysis_swing_points - ZigZag 波段买卖点
  realtimeSignalTool,             // realtime_signal_scan - 实时信号扫描（解决信号滞后问题）

  // L2.7 股票池管理
  poolManageTool,                 // pool_manage - 股票池 CRUD + 筛选建池
  poolValidateTool,               // pool_validate - 多策略批量回测验证

  // L2.8 组合策略回测
  comboBacktestTool,              // strategy_combo_backtest - 多策略组合回测

  // L3 模型层
  modelTrainTool,                 // model_train - 训练机器学习模型
  modelPredictTool,               // model_predict - 模型预测信号
  modelEvaluateTool,              // model_evaluate - 评估模型性能
  modelMonitorTool,               // model_monitor - 监控模型漂移
  modelListTool,                  // model_list - 列出所有模型

  // L3.5 策略（独立工具）
  strategyListTool,               // strategy_list - 列出所有策略
  strategyDetailTool,             // strategy_detail - 查看策略详情
  strategyWriteTool,              // strategy_write - 编写/更新策略代码（创建+更新）
  strategyExecuteTool,            // strategy_execute - 统一策略执行（single/batch/pipeline）
  strategyStatusTool,             // strategy_status - 查询策略运行状态
  strategyOptimizeTool,           // strategy_optimize - 策略参数优化
  strategyBatchValidateTool,      // strategy_batch_validate - 批量验证策略有效性
  strategyDeleteTool,             // strategy_delete - 软删除策略（设置 is_active=false）
  strategyDiscoveryTool,          // strategy_discovery - 策略发现工具（新增）

  // 指标工具
  indicatorListTool,              // indicator_list - 列出可用指标
  indicatorDetailTool,            // indicator_detail - 查看指标详情
  indicatorCreateTool,            // indicator_create - 创建自定义指标
  indicatorUpdateTool,            // indicator_update - 更新指标
  indicatorDeleteTool,            // indicator_delete - 删除指标
  indicatorBacktestTool,          // indicator_backtest - 指标历史回测

  // L4 组合构建层（已移除工具：portfolio_rebalance）
  // L5 执行引擎层（已移除工具：trade_manage_orders）
  algoExecuteTool,                // trade_algo_execute - 算法交易执行
  signalExecutionTool,            // signal_execution - 信号执行管理

  // L6 监控运维
  monitorAlertTool,               // monitor_alert - 告警通知
  marketAlertTool,                // market_alert - 市场预警查询（盘前/盘后例行检查）

  // ===== 经验库工具 =====
  queryExperienceTool,            // experience_query - 查询历史经验库
  experienceWriteTool,            // experience_write - 写入投资经验

  // ===== 筛选与分析工具（从 quant_cli 拆分）=====
  screeningTool,                  // screening - 股票筛选（sector/quality）
  sectorAnalysisTool,             // sector_analysis - 行业聚合分析
  benchmarkCompareTool,           // benchmark_compare - 基准比较
  chanAnalyzeTool,                // chan_analyze - 缠论分析（走势/买卖点+历史胜率）
  chipAnalysisTool,               // chip_analysis - 筹码分布（成本分布）分析
  evolutionLeaderboardTool,       // evolution_leaderboard - 双侧捕获适应度排行（行为进化 P1）

  // ===== 监控与预警工具（从 quant_cli 拆分）=====
  watchAlertTool,                 // watch_price_alert - 价格预警
  watchManageTool,                // watch_manage - 实时盯盘规则管理

  // ===== 交易验证工具（从 quant_cli 拆分）=====
  tradeVerifyTool,                // trade_verify - 交易记录验证

  // ===== 报告工具（从 quant_cli 拆分）=====
  dailyReportTool,                // daily_report - 日报生成/读取

  // ===== 模型工具（从 quant_cli 拆分）=====
  calibrateTool,                  // calibrate_confidence - 置信度校准
  trainingReportsTool,            // training_reports - 训练报告查询

  // ===== 系统工具（从 quant_cli 拆分）=====
  asyncJobsTool,                  // async_jobs - 异步任务管理

  // ===== 策略轮动决策工具链 =====
  rotationProposalTool,           // rotation_proposal - 获取轮动方案（决策链第1步）
  rotationSimulateTool,           // rotation_simulate - 模拟轮动执行（决策链第2步）
  rotationExecuteTool,            // rotation_execute - 执行轮动（决策链第3步）
  rotationVerifyTool,             // rotation_verify - 验证轮动效果（决策链第4步）

  // ===== 独立业务工具 =====
  riskMetricsTool,               // risk_metrics - 风险指标分析（empyrical）
  riskControllerTool,             // risk_controller - 风险控制工具
  riskBarraDecompositionTool,     // risk_barra_decomposition - Barra风险分解（新增）
  factorModelAttributionTool,     // factor_model_attribution - 因子模型归因（新增）
  marketStyleDetectTool,          // market_style_detect - 市场风格检测（新增）
  opponentBehaviorTool,           // opponent_behavior - 对手行为分析（博弈情报）
  poolBattlefieldTool,            // pool_battlefield - 池子战场评估（博弈情报）
  manipulationDetectTool,         // manipulation_detect - 操纵检测（博弈情报）
  verifyJudgmentsTool,            // verify_judgments - 判断自校验（学习闭环）
  decisionHistoryTool,            // decision_history - 决策历史查询（决策追踪）
  decisionRecordTool,             // decision_record - 决策记录（审计轨迹落库）
  schedulerManageTool,            // scheduler_manage - 调度器管理（新增）
  feishuNotifyTool,               // feishu_notify - 飞书通知工具（新增）
  notificationSendTool,           // notification_send - 通知系统发送（新增）
  notificationListChannelsTool,   // notification_list_channels - 查询通知渠道（新增）
  strategyComparisonTool,         // strategy_performance_comparison - 策略性能对比（新增）
  backtestStatsTool,              // backtest_stats - 回测统计（新增）
  backtestHistoryTool,            // backtest_history - 回测历史查询（新增）
  tradeMonitorTool,               // trade_monitor - 交易监控工具
  portfolioOptimizerTool,         // portfolio_optimizer - 组合优化工具
  portfolioTradeTool,             // portfolio_trade - Agent虚拟仓交易
  portfolioStatusTool,            // portfolio_status - 查看虚拟仓状态
  portfolioDailyBriefTool,        // portfolio_daily_brief - 每日对账单（复盘入口）
  tradeJournalTool,               // trade_journal - 统一交易簿记（record/experience/status/daily_report）
  portfolioAnalyzeTool,           // portfolio_analyze - 分析持仓给出建议
  portfolioAccountTool,           // portfolio_account - 账户管理（开户）
  performanceAnalyzerTool,        // performance_analyzer - 性能分析工具
  factorAcademicTool,             // factor_academic - 学术因子工具
  timeseriesAnalyzerTool,         // timeseries_analyzer - 时间序列分析工具

  // ===== 通知 & 监控工具 — 消息推送、实时盯盘 =====

  // ===== 进化工具 — 自我优化 =====
  evolutionRunTool,

  // ===== 重启工具 — 运维操作 =====
  restartAgentTool,
  backendControlTool,
  claudeCodeTool,
  toolStatsQueryTool,             // tool_stats_query - 工具使用统计查询
  modelSwitchTool,                // model_switch - LLM provider 热切换

  // ===== 中频 — 记忆 =====
  memoryWriteTool,
  memorySearchTool,
  recallAuditTool,

  // ===== 中频 — 进化 =====
  skillFileTool,

  // ===== Skill Hub 工具（Agent OS 集成）=====
  skillListTool,              // skill_list - 列出所有可用 skills
  skillGetTool,               // skill_get - 获取 skill 完整内容
  skillUpdateTool,            // skill_update - 更新 skill（进化系统用）

  // ===== 低频/专用 =====
  taskCheckBackgroundTool,  // 检查后台任务
  compactTool,
  browserTool,
  readTool,
];

// ===== 工具分组导出 =====
export { SHARED_BASE_TOOLS, FIN_TOOLS, EVOLUTION_TOOLS, MEMORY_TOOLS } from './groups.js';
