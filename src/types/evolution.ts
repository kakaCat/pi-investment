/**
 * 进化功能类型定义
 */

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
