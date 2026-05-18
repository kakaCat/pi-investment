/**
 * 进化功能类型定义
 */

// ─── 减法器新增类型 ────────────────────────────────────────────────────────

/** 阶段性能（周/月/全周期） */
export interface PeriodPerformance {
  /** 周期标签：如 "2026-W19"、"2026-05"、"全周期" */
  label: string;
  /** 周期起始日期（ISO date） */
  startDate: string;
  /** 周期结束日期（ISO date） */
  endDate: string;
  /** 该周期内已平仓盈亏（元） */
  realizedPnL: number;
  /** 该周期内持仓浮盈变化（元）——仅全周期可用，周/月标注为 null */
  unrealizedPnLChange: number | null;
  /** 该周期总盈亏（元）= realizedPnL + unrealizedPnLChange */
  totalPnL: number;
  /** 该周期期初总投入（元）= 买入成本 */
  beginningCapital: number;
  /** 该周期收益率（%）= totalPnL / beginningCapital * 100 */
  returnPct: number;
  /** 该周期交易笔数（含买卖） */
  tradeCount: number;
  /** 该周期胜率（已平仓） */
  winRate: number;
  /** 数据可靠性标记 */
  reliability: 'full' | 'partial' | 'estimated';
}

/** 总收益汇总 */
export interface TotalReturn {
  /** 已实现盈亏（元） */
  realizedPnL: number;
  /** 当前持仓浮盈（元）——实时行情估算 */
  unrealizedPnL: number;
  /** 总盈亏（元）= realizedPnL + unrealizedPnL */
  totalPnL: number;
  /** 累积总投入（元）= 所有买入交易金额总和（含已清仓） */
  totalInvestment: number;
  /** 当前活跃资金（元）= 仅当前持仓的成本总和 */
  activeInvestment: number;
  /** 历史峰值资金占用（元）= 帐户余额历史最大值 */
  peakInvestment: number;
  /** 总收益率（%）= totalPnL / totalInvestment * 100 */
  totalReturnPct: number;
  /** 活跃资金收益率（%）= totalPnL / activeInvestment * 100 */
  activeReturnPct: number;
}

/** 数据完整性报告 */
export interface DataQualityReport {
  /** 最早交易日期 */
  earliestTradeDate: string | null;
  /** 最近交易日期 */
  latestTradeDate: string | null;
  /** 交易记录总数 */
  tradeCount: number;
  /** 持仓数量 */
  positionCount: number;
  /** 是否有持仓数据 */
  hasPortfolioData: boolean;
  /** 是否有完整的买入记录 */
  hasCompleteBuyRecords: boolean;
  /** 可靠性评级 */
  reliability: 'high' | 'medium' | 'low';
  /** 警告信息列表 */
  warnings: string[];
}

/** 减法器比较结果 */
export interface ComparisonResult {
  /** 总收益 */
  totalReturn: TotalReturn;
  /** 阶段对比（周切片） */
  weeklyComparison: PeriodPerformance[];
  /** 阶段对比（月切片） */
  monthlyComparison: PeriodPerformance[];
  /** 全周期 */
  allTimeComparison: PeriodPerformance;
  /** 数据完整性 */
  dataQuality: DataQualityReport;
}

// ─── 原有类型（保持不变） ───────────────────────────────────────────────────

// 性能差距
export interface PerformanceGap {
  target: number;           // 目标收益率
  actual: number;           // 实际收益率
  gap: number;              // 差距 = target - actual
  market: number;           // 大盘收益率
  alpha: number;            // 超额收益 = actual - market
}

// 归因结果
export interface AttributionResult {
  rootCause: 'target_unrealistic' | 'capability_insufficient';
  confidence: number;
  reasons: string[];
  recommendation: 'adjust_target' | 'trigger_optimizer';
  suggestedTarget?: number;
}

// 目标合理性检查
export interface TargetRealisticCheck {
  realistic: boolean;
  reasons: string[];
  suggestedTarget?: number;
}

// 能力评估
export interface CapabilityCheck {
  capable: boolean;
  reasons: string[];
  weaknesses: string[];
}

// 决策质量指标
export interface DecisionQualityMetrics {
  recentReturns: number[];
  errorRate: number;
  stopLossExecutionRate: number;
}

// 优化策略
export interface OptimizerStrategy {
  level: 'minor' | 'moderate' | 'major';
  actions: OptimizerAction[];
}

// 工具调整
export interface ToolAddition {
  name: string;
  label?: string;
  description: string;
  reason: string;
  expectedImpact: string;
}

export interface ToolRemoval {
  name: string;
  reason: string;
  evidence: {
    callCount: number;
    winRate: number;
    avgReturn: number;
  };
}

// 经验库
export interface Experience {
  id: string;
  scenario: string;
  pattern: {
    conditions: string[];
    action: 'buy' | 'sell' | 'hold';
  };
  outcomes: {
    total_cases: number;
    win_rate: number;
    avg_return: number;
    max_gain?: number;
    max_loss?: number;
  };
  recommendation: 'aggressive' | 'moderate' | 'cautious' | 'avoid';
  reason: string;
  examples: Array<{
    date: string;
    symbol: string;
    session_id: string;
    result: number;
  }>;
  confidence: number;
  last_updated: string;
}

export interface ExperienceBase {
  version: string;
  last_updated: string;
  experiences: Experience[];
}

// 决策链路
export interface ToolCall {
  tool_name: string;
  arguments: Record<string, any>;
  result?: any;
  timestamp: string;
}

export interface DecisionChain {
  session_id: string;
  timestamp: string;
  user_query: string;
  tool_calls: ToolCall[];
  reasoning?: string;
  decision: {
    action: string;
    symbol: string;
    reason: string;
  };
  resources: {
    tokens: number;
    cost: number;
    duration_ms: number;
  };
}

// 工具效能
export interface ToolEfficiency {
  tool_name: string;
  call_count: number;
  decisions_after_call: number;
  win_rate: number;
  avg_return: number;
  avg_tokens: number;
  cost_per_call: number;
  roi: number;
  rating: 1 | 2 | 3 | 4 | 5;
}

// 优化建议类型
export type OptimizerAction =
  | 'add_tool'           // 生成新工具（能力缺失）
  | 'remove_tool'        // 移除工具（能力冗余）
  | 'update_experience'  // 更新经验库（经验不足）
  | 'update_prompt'      // 修改提示词（决策逻辑偏差）
  | 'update_code'        // 修改代码（实现缺陷/性能问题）
  | 'adjust_parameter';  // 调整参数（配置优化）

// 提示词更新
export interface PromptUpdate {
  file: string;           // 提示词文件路径（相对于 .pi-invest/bootstrap/）
  section?: string;       // 要修改的章节（可选）
  modification: string;   // 修改内容描述
  newContent: string;     // 新的内容
  reason: string;         // 修改原因
}

// 代码更新
export interface CodeUpdate {
  file: string;           // 代码文件路径
  function?: string;      // 要修改的函数名（可选）
  issue: string;          // 问题描述
  modification: string;   // 修改内容描述
  reason: string;         // 修改原因
}

// 优化建议
export interface OptimizationSuggestion {
  id: string;
  type: OptimizerAction;
  priority: 'high' | 'medium' | 'low';
  description: string;
  reason: string;
  expectedImpact: string;
  data?: any;

  // 类型特定数据
  promptUpdate?: PromptUpdate;
  codeUpdate?: CodeUpdate;
}

// 进化报告
export interface EvolutionReport {
  period: string;
  performance: {
    target: number;
    actual: number;
    gap: number;
    market: number;
    winRate: number;
    maxDrawdown: number;
    sharpeRatio: number;
  };
  attribution: AttributionResult;
  sessionAnalysis: {
    totalSessions: number;
    successPatterns: Array<{
      pattern: string;
      count: number;
      winRate: number;
      avgReturn: number;
    }>;
    failurePatterns: Array<{
      pattern: string;
      count: number;
      winRate: number;
      avgLoss: number;
    }>;
  };
  toolEfficiency: ToolEfficiency[];
  suggestions: OptimizationSuggestion[];
  marketContext?: import('./market-context.js').MarketContext; // 新增：市场环境数据
  sessionLog?: import('./session-log.js').SessionAnalysis; // 新增：Session 日志分析
  toolEfficiencyAssessment?: import('../services/intelligence/tool-efficiency-analyzer.js').ToolEfficiencyAssessment; // 新增：工具效能评估
  holdingAnalysis?: import('./holding-analysis.js').HoldingDimensionAnalysis; // 新增：持仓维度分析
  appliedChanges?: Array<{
    suggestionId: string;
    appliedAt: string;
    version: number;
  }>;
}

// ─── 进化历史学习系统 ────────────────────────────────────────────────────

// 进化历史记录
export interface EvolutionHistory {
  evolutionId: string;
  date: string;
  branchName: string;
  suggestions: OptimizationSuggestion[];
  applied: string[]; // 已应用的建议 ID

  // 应用前的基线
  baseline: {
    return: number;
    winRate: number;
    maxDrawdown: number;
    toolStats: ToolEfficiency[];
  };

  // 应用后的效果（下次进化时填充）
  outcome?: {
    return: number;
    winRate: number;
    maxDrawdown: number;
    toolStats: ToolEfficiency[];
    improvement: {
      returnDelta: number;
      winRateDelta: number;
      maxDrawdownDelta: number;
    };
  };

  // 效果评估
  evaluation?: {
    score: number; // 0-100分
    effective: boolean;
    effectiveTools: string[];
    ineffectiveTools: string[];
    reasons: string[];
    suggestionScores: SuggestionScore[];
  };
}

// 单个建议评分
export interface SuggestionScore {
  suggestionId: string;
  toolName: string;
  score: number; // 0-100分
  metrics: {
    callCount: number;
    winRate: number;
    avgReturn: number;
    contribution: number;
  } | null;
  verdict: 'excellent' | 'good' | 'neutral' | 'poor' | 'harmful';
}

// 经验总结
export interface ExperienceSummary {
  version: string;
  lastUpdated: string;
  totalEvolutions: number;

  toolPatterns: ToolPattern[];
  suggestionTypeStats: SuggestionTypeStat[];
  learnings: Learning[];
  antiPatterns: AntiPattern[];
}

export interface ToolPattern {
  toolName: string;
  addedCount: number;
  removedCount: number;
  avgScore: number;
  successRate: number;
  bestContext: string;
  recommendation: 'highly_recommended' | 'recommended' | 'neutral' | 'not_recommended';
}

export interface SuggestionTypeStat {
  type: 'add_tool' | 'remove_tool' | 'update_experience';
  totalCount: number;
  avgScore: number;
  successRate: number;
}

export interface Learning {
  id: string;
  rule: string;
  confidence: number;
  evidence: string[];
  examples: string[];
}

export interface AntiPattern {
  pattern: string;
  reason: string;
  occurrences: number;
  avgNegativeImpact: number;
}

// ─── 操作质量评估类型 ──────────────────────────────────────────────────

/**
 * 单笔交易的操作质量评分
 * 利用减法器已有的 FIFO MatchedTrade 结果进行分析
 */
export interface OperationQualityReview {
  /** 该股票的整体评分 0-100 */
  overallScore: number;
  symbol: string;
  name: string;
  /** 是否已清仓（已清仓的股票评分更完整） */
  isClosed: boolean;
  /** 批次止盈梯度评分：卖出价是否合理递进 */
  batchExitScore: number;
  /** 高点捕获率：卖出价占区间最高位的百分比 */
  peakCapturePct: number;
  /** 卖出价格价差（最高卖价 - 最低卖价） */
  priceSpread: number;
  /** 卖出均价 */
  avgSellPrice: number;
  /** 优化提示列表 */
  optimizationTips: OptimizationTip[];
}

/**
 * 优化提示
 */
export interface OptimizationTip {
  type: 'sold_too_early' | 'sold_below_peak' | 'batch_price_regression' | 'uneven_position_sizing' | 'good_execution';
  severity: 'info' | 'warning' | 'improvement';
  message: string;
  detail?: string;
  data?: {
    price?: number;
    suggestedPrice?: number;
    pnlImpact?: number;   // 可优化的额外收益（估算）
    quantity?: number;
  };
}

/**
 * 整体操作质量报告
 */
export interface OperationQualityReport {
  /** 各股票的操作质量 */
  stocks: OperationQualityReview[];
  /** 总体评分 */
  averageScore: number;
  /** 主要优化方向（TOP-3） */
  topOptimizations: OptimizationTip[];
  /** 总共可优化的收益空间（估算） */
  totalOptimizablePnL: number;
}
