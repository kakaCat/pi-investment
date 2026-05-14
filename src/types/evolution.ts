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

export type OptimizerAction =
  | 'adjust_parameters'
  | 'update_experience'
  | 'add_tools'
  | 'remove_tools'
  | 'update_algorithms'
  | 'redesign_strategy';

// 工具调整
export interface ToolAddition {
  name: string;
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

// 优化建议
export interface OptimizationSuggestion {
  id: string;
  type: 'add_tool' | 'remove_tool' | 'update_experience' | 'adjust_parameter';
  priority: 'high' | 'medium' | 'low';
  description: string;
  reason: string;
  expectedImpact: string;
  data?: any;
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
