/**
 * Tool Groups - 按 Agent 角色分组工具
 *
 * 四组：
 * - SHARED_BASE_TOOLS: 所有 agent 都可用的基础工具（任务/计划/记忆读写/调度）
 * - FIN_TOOLS: 金融 Agent 工具组（数据/交易/分析/池/风控等）
 * - EVOLUTION_TOOLS: 进化 Agent 工具组（进化/适应度/代码审查）
 * - MEMORY_TOOLS: 记忆 Agent 工具组（记忆搜索/写入）
 */

// ===== MEMORY_TOOLS =====
import { memoryWriteTool, memorySearchTool } from './agent/memory-tool.js';
import { recallAuditTool } from './agent/recall-audit-tool.js';

export const MEMORY_TOOLS = [
  memoryWriteTool,
  memorySearchTool,
  recallAuditTool,
] as const;

// ===== EVOLUTION_TOOLS =====
import { evolutionRunTool } from './agent/evolution-tool.js';
import { evolutionLeaderboardTool } from './performance/evolution-leaderboard-tool.js';
import { claudeCodeTool } from './agent/claude-code-tool.js';
import { skillFileTool } from './evolution/skill-file-tool.js';

export const EVOLUTION_TOOLS = [
  evolutionRunTool,
  evolutionLeaderboardTool,
  claudeCodeTool,
  skillFileTool,
] as const;

// ===== SHARED_BASE_TOOLS =====
import { planTool } from './agent/plan-tool.js';
import {
  taskCreateTool,
  taskUpdateTool,
  taskExecuteAsyncTool,
  taskListTool,
  taskCheckBackgroundTool,
} from './agent/task-tools.js';
import { schedulerManageTool } from './scheduler/scheduler-manage-tool.js';
import { modelSwitchTool } from './agent/model-switch-tool.js';

// 注意：restart_agent 不在 SHARED——进程控制权只归 fin（FIN_TOOLS）。
// 批次6实证（2026-08-13）：memory agent 在工具连续失败后自主调用 restart_agent
// 试图重启整个 agent 进程，受限域 agent 不应持有此权柄。
export const SHARED_BASE_TOOLS = [
  planTool,
  taskCreateTool,
  taskUpdateTool,
  taskExecuteAsyncTool,
  taskListTool,
  taskCheckBackgroundTool,
  schedulerManageTool,
  modelSwitchTool,
] as const;

// ===== FIN_TOOLS =====
import { restartAgentTool } from './agent/restart-agent-tool.js';
import { clarifyTool } from './agent/clarify-tool.js';
import { reflectTool } from './agent/reflect-tool.js';
import { dataFetchQuoteTool } from './data/fetch-stock-tool.js';
import { dataFetchKlineTool } from './data/fetch-kline-tool.js';
import { dataFetchFinancialTool } from './data/fetch-financial-tool.js';
import { dataFetchDividendTool } from './data/fetch-dividend-tool.js';
import { dataFetchMacroTool } from './data/fetch-macro-tool.js';
import { dataFetchNorthFlowTool } from './data/fetch-north-flow-tool.js';
import { dataFetchMarketSentimentTool } from './data/fetch-market-sentiment-tool.js';
import { dataManagerTool } from './data/data-manager-tool.js';
import { dataQualityReportTool } from './data/data-quality-report-tool.js';
import { dataQualityManageTool } from './data/quality-manage-tool.js';
import { factorCalculateTool } from './factor/calculate-tool.js';
import { factorAnalyzeTool } from './factor/factor-analyze-tool.js';
import { factorLayeringBacktestTool } from './factor/layering-backtest-tool.js';
import { batchFactorLayeringBacktestTool } from './factor/batch-layering-backtest-tool.js';
import { factorListTool } from './factor/list-tool.js';
import { factorCorrelationTool } from './factor/correlation-tool.js';
import { factorPortfolioOptimizeTool } from './factor/portfolio-optimize-tool.js';
import { factorICMonitorTool } from './factor/ic-monitor-tool.js';
import { opportunityScanTool } from './invest/opportunity-scan-tool.js';
import { swingPointsTool } from './invest/swing-points-tool.js';
import { realtimeSignalTool } from './signal/realtime-signal-tool.js';
import { poolManageTool } from './pool/pool-manage-tool.js';
import { poolValidateTool } from './pool/pool-validate-tool.js';
import { comboBacktestTool } from './backtest/combo-backtest-tool.js';
import { modelTrainTool } from './model/train-tool.js';
import { modelPredictTool } from './model/predict-tool.js';
import { modelEvaluateTool } from './model/evaluate-tool.js';
import { modelMonitorTool } from './model/monitor-tool.js';
import { modelListTool } from './model/list-tool.js';
import { strategyListTool } from './strategy/list-tool.js';
import { strategyDetailTool } from './strategy/detail-tool.js';
import { strategyWriteTool } from './strategy/write-tool.js';
import { strategyExecuteTool } from './strategy/execute-tool.js';
import { strategyStatusTool } from './strategy/status-tool.js';
import { strategyOptimizeTool } from './strategy/optimize-tool.js';
import { strategyBatchValidateTool } from './strategy/batch-validate-tool.js';
import { strategyDeleteTool } from './strategy/delete-tool.js';
import { strategyDiscoveryTool } from './strategy/strategy-discovery-tool.js';
import { indicatorListTool } from './indicator/list-tool.js';
import { indicatorDetailTool } from './indicator/detail-tool.js';
import { indicatorCreateTool } from './indicator/create-tool.js';
import { indicatorUpdateTool } from './indicator/update-tool.js';
import { indicatorDeleteTool } from './indicator/delete-tool.js';
import { indicatorBacktestTool } from './indicator/backtest-tool.js';
import { algoExecuteTool } from './trade/algo-execute-tool.js';
import { signalExecutionTool } from './execution/signal-execution-tool.js';
import { monitorAlertTool } from './monitor/alert-tool.js';
import { marketAlertTool } from './alert/market-alert-tool.js';
import { queryExperienceTool } from './agent/query-experience-tool.js';
import { experienceWriteTool } from './agent/experience-write-tool.js';
import { screeningTool } from './screening/screening-tool.js';
import { sectorAnalysisTool } from './analysis/sector-analysis-tool.js';
import { benchmarkCompareTool } from './analysis/benchmark-compare-tool.js';
import { chanAnalyzeTool } from './analysis/chan-analyze-tool.js';
import { chipAnalysisTool } from './analysis/chip-analysis-tool.js';
import { watchAlertTool } from './monitor/watch-alert-tool.js';
import { watchManageTool } from './monitor/watch-manage-tool.js';
import { tradeVerifyTool } from './trade/trade-verify-tool.js';
import { dailyReportTool } from './report/daily-report-tool.js';
import { calibrateTool } from './model/calibrate-tool.js';
import { trainingReportsTool } from './model/training-reports-tool.js';
import { asyncJobsTool } from './core/async-jobs-tool.js';
import {
  rotationProposalTool,
  rotationSimulateTool,
  rotationExecuteTool,
  rotationVerifyTool,
} from './rotation/index.js';
import { riskMetricsTool } from './risk/risk-metrics-tool.js';
import { riskControllerTool } from './risk/risk-controller-tool.js';
import { riskBarraDecompositionTool } from './risk/barra-decomposition-tool.js';
import { factorModelAttributionTool } from './analysis/factor-model-attribution-tool.js';
import { marketStyleDetectTool } from './market/market-style-detect-tool.js';
import { opponentBehaviorTool } from './game/opponent-behavior-tool.js';
import { poolBattlefieldTool } from './game/pool-battlefield-tool.js';
import { manipulationDetectTool } from './game/manipulation-detect-tool.js';
import { verifyJudgmentsTool } from './learning/verify-judgments-tool.js';
import { decisionHistoryTool } from './decision/decision-history-tool.js';
import { decisionRecordTool } from './decision/decision-record-tool.js';
import { feishuNotifyTool } from './notification/feishu-notify-tool.js';
import { strategyComparisonTool } from './analysis/strategy-comparison-tool.js';
import { backtestStatsTool } from './analysis/backtest-stats-tool.js';
import { backtestHistoryTool } from './analysis/backtest-history-tool.js';
import { tradeMonitorTool } from './trade/trade-monitor-tool.js';
import { portfolioOptimizerTool } from './portfolio/portfolio-optimizer-tool.js';
import { portfolioTradeTool } from './portfolio/portfolio-trade-tool.js';
import { portfolioStatusTool } from './portfolio/portfolio-status-tool.js';
import { portfolioDailyBriefTool } from './portfolio/portfolio-daily-brief-tool.js';
import { tradeJournalTool } from './journal/trade-journal-tool.js';
import { portfolioAnalyzeTool } from './portfolio/portfolio-analyze-tool.js';
import { portfolioAccountTool } from './portfolio/portfolio-account-tool.js';
import { performanceAnalyzerTool } from './performance/performance-analyzer-tool.js';
import { factorAcademicTool } from './academic/factor-academic-tool.js';
import { timeseriesAnalyzerTool } from './timeseries/timeseries-analyzer-tool.js';
import { backendControlTool } from './agent/backend-control-tool.js';
import { toolStatsQueryTool } from './agent/tool-stats-tool.js';
import { compactTool } from './agent/compact-tool.js';
import { browserTool } from './agent/browser-tool.js';
import { createReadTool } from '../../sdk-facade.js';

const readTool = createReadTool(process.cwd());

export const FIN_TOOLS = [
  restartAgentTool,  // 进程控制权只归 fin（原 SHARED，批次6安全收口）
  clarifyTool,
  reflectTool,
  dataFetchQuoteTool,
  dataFetchKlineTool,
  dataFetchFinancialTool,
  dataFetchDividendTool,
  dataFetchMacroTool,
  dataFetchNorthFlowTool,
  dataFetchMarketSentimentTool,
  dataManagerTool,
  dataQualityReportTool,
  dataQualityManageTool,
  factorCalculateTool,
  factorAnalyzeTool,
  factorLayeringBacktestTool,
  batchFactorLayeringBacktestTool,
  factorListTool,
  factorCorrelationTool,
  factorPortfolioOptimizeTool,
  factorICMonitorTool,
  opportunityScanTool,
  swingPointsTool,
  realtimeSignalTool,
  poolManageTool,
  poolValidateTool,
  comboBacktestTool,
  modelTrainTool,
  modelPredictTool,
  modelEvaluateTool,
  modelMonitorTool,
  modelListTool,
  strategyListTool,
  strategyDetailTool,
  strategyWriteTool,
  strategyExecuteTool,
  strategyStatusTool,
  strategyOptimizeTool,
  strategyBatchValidateTool,
  strategyDeleteTool,
  strategyDiscoveryTool,
  indicatorListTool,
  indicatorDetailTool,
  indicatorCreateTool,
  indicatorUpdateTool,
  indicatorDeleteTool,
  indicatorBacktestTool,
  algoExecuteTool,
  signalExecutionTool,
  monitorAlertTool,
  marketAlertTool,
  queryExperienceTool,
  experienceWriteTool,
  screeningTool,
  sectorAnalysisTool,
  benchmarkCompareTool,
  chanAnalyzeTool,
  chipAnalysisTool,
  watchAlertTool,
  watchManageTool,
  tradeVerifyTool,
  dailyReportTool,
  calibrateTool,
  trainingReportsTool,
  asyncJobsTool,
  rotationProposalTool,
  rotationSimulateTool,
  rotationExecuteTool,
  rotationVerifyTool,
  riskMetricsTool,
  riskControllerTool,
  riskBarraDecompositionTool,
  factorModelAttributionTool,
  marketStyleDetectTool,
  opponentBehaviorTool,
  poolBattlefieldTool,
  manipulationDetectTool,
  verifyJudgmentsTool,
  decisionHistoryTool,
  decisionRecordTool,
  feishuNotifyTool,
  strategyComparisonTool,
  backtestStatsTool,
  backtestHistoryTool,
  tradeMonitorTool,
  portfolioOptimizerTool,
  portfolioTradeTool,
  portfolioStatusTool,
  portfolioDailyBriefTool,
  tradeJournalTool,
  portfolioAnalyzeTool,
  portfolioAccountTool,
  performanceAnalyzerTool,
  factorAcademicTool,
  timeseriesAnalyzerTool,
  backendControlTool,
  toolStatsQueryTool,
  compactTool,
  browserTool,
  readTool,
] as const;
