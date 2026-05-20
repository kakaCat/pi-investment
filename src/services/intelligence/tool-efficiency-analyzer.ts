/**
 * 工具效能分析器
 *
 * 基于 Session 日志分析结果，评估工具效能并生成优化建议
 */

import type { SessionAnalysis, ToolStats } from '../../types/session-log.js';
import type { OptimizationSuggestion } from '../../types/evolution.js';

/**
 * 工具效能评估结果
 */
export interface ToolEfficiencyAssessment {
  /** 高失败率工具（需要修复或移除） */
  problematicTools: ToolStats[];
  /** 性能瓶颈工具（耗时过长） */
  slowTools: ToolStats[];
  /** 低使用率工具（可能不必要） */
  underusedTools: ToolStats[];
  /** 整体效能评分 (0-100) */
  overallScore: number;
  /** 优化建议 */
  suggestions: OptimizationSuggestion[];
}

/**
 * 分析工具效能并生成优化建议
 */
export function analyzeToolEfficiency(
  sessionAnalysis: SessionAnalysis,
  allAvailableTools?: string[]
): ToolEfficiencyAssessment {
  const { topTools, slowestTools, mostFailedTools, overallErrorRate, avgToolDuration } = sessionAnalysis;

  // 1. 识别问题工具
  const problematicTools = mostFailedTools.filter(t => t.errorRate > 0.2); // 错误率 > 20%
  const slowTools = slowestTools.filter(t => t.avgDuration > 10000); // 平均耗时 > 10s

  // 2. 识别低使用率工具（如果提供了可用工具列表）
  const underusedTools: ToolStats[] = [];
  if (allAvailableTools) {
    const usedToolNames = new Set(topTools.map(t => t.name));
    // 这里简化处理，实际应该从历史数据中统计
  }

  // 3. 计算整体效能评分
  const overallScore = calculateOverallScore(sessionAnalysis);

  // 4. 生成优化建议
  const suggestions = generateToolOptimizationSuggestions(
    problematicTools,
    slowTools,
    underusedTools,
    sessionAnalysis
  );

  return {
    problematicTools,
    slowTools,
    underusedTools,
    overallScore,
    suggestions,
  };
}

/**
 * 计算整体工具效能评分 (0-100)
 */
function calculateOverallScore(analysis: SessionAnalysis): number {
  let score = 100;

  // 错误率扣分：每 1% 错误率扣 2 分
  score -= analysis.overallErrorRate * 200;

  // 平均耗时扣分：超过 5s 开始扣分
  if (analysis.avgToolDuration > 5000) {
    const excessSeconds = (analysis.avgToolDuration - 5000) / 1000;
    score -= Math.min(excessSeconds * 2, 20); // 最多扣 20 分
  }

  // 高失败率工具扣分
  const highErrorTools = analysis.mostFailedTools.filter(t => t.errorRate > 0.3);
  score -= highErrorTools.length * 5;

  return Math.max(0, Math.min(100, score));
}

/**
 * 生成工具优化建议
 */
function generateToolOptimizationSuggestions(
  problematicTools: ToolStats[],
  slowTools: ToolStats[],
  underusedTools: ToolStats[],
  analysis: SessionAnalysis
): OptimizationSuggestion[] {
  const suggestions: OptimizationSuggestion[] = [];
  let idCounter = 1;

  // 1. 高失败率工具建议
  for (const tool of problematicTools.slice(0, 3)) { // 最多 3 个
    if (tool.errorRate > 0.5) {
      // 错误率 > 50%，建议移除或重写
      suggestions.push({
        id: `tool_opt_${idCounter++}`,
        type: 'update_code',
        priority: 'high',
        description: `修复高失败率工具：${tool.name}`,
        reason: `工具失败率 ${(tool.errorRate * 100).toFixed(1)}%，严重影响决策质量`,
        expectedImpact: '提升工具可靠性，减少决策中断',
        codeUpdate: {
          file: `src/infrastructure/tools/${tool.name.replace(/_/g, '-')}-tool.ts`,
          function: tool.name,
          issue: `失败率过高（${(tool.errorRate * 100).toFixed(1)}%），需要增强错误处理和数据验证`,
          modification: '添加输入验证、增强错误处理、添加降级策略',
          reason: `当前失败率 ${(tool.errorRate * 100).toFixed(1)}%，目标 < 10%`
        }
      });
    } else {
      // 错误率 20-50%，建议优化
      suggestions.push({
        id: `tool_opt_${idCounter++}`,
        type: 'update_code',
        priority: 'medium',
        description: `优化工具稳定性：${tool.name}`,
        reason: `工具失败率 ${(tool.errorRate * 100).toFixed(1)}%，需要改进错误处理`,
        expectedImpact: '降低工具失败率，提升系统稳定性',
        codeUpdate: {
          file: `src/infrastructure/tools/${tool.name.replace(/_/g, '-')}-tool.ts`,
          function: tool.name,
          issue: `失败率 ${(tool.errorRate * 100).toFixed(1)}%，需要优化`,
          modification: '改进错误处理、添加重试机制、优化数据验证',
          reason: `目标将失败率降至 < 10%`
        }
      });
    }
  }

  // 2. 性能瓶颈工具建议
  for (const tool of slowTools.slice(0, 2)) { // 最多 2 个
    suggestions.push({
      id: `tool_opt_${idCounter++}`,
      type: 'update_code',
      priority: 'medium',
      description: `优化工具性能：${tool.name}`,
      reason: `工具平均耗时 ${(tool.avgDuration / 1000).toFixed(1)}s，影响决策效率`,
      expectedImpact: '提升响应速度，改善用户体验',
      codeUpdate: {
        file: `src/infrastructure/tools/${tool.name.replace(/_/g, '-')}-tool.ts`,
        function: tool.name,
        issue: `平均耗时 ${(tool.avgDuration / 1000).toFixed(1)}s，性能瓶颈`,
        modification: '添加缓存、优化数据查询、减少网络请求、并行处理',
        reason: `目标将耗时降至 < 5s`
      }
    });
  }

  // 3. 整体错误率过高建议
  if (analysis.overallErrorRate > 0.15) {
    suggestions.push({
      id: `tool_opt_${idCounter++}`,
      type: 'update_code',
      priority: 'high',
      description: '改进工具层错误处理机制',
      reason: `整体工具错误率 ${(analysis.overallErrorRate * 100).toFixed(1)}%，需要系统性改进`,
      expectedImpact: '提升系统稳定性，减少决策中断',
      codeUpdate: {
        file: 'src/infrastructure/tools/shared/error-handler.ts',
        function: 'handleToolError',
        issue: '缺少统一的错误处理和降级策略',
        modification: '实现统一错误处理、添加降级策略、增强日志记录',
        reason: `当前整体错误率 ${(analysis.overallErrorRate * 100).toFixed(1)}%，目标 < 10%`
      }
    });
  }

  // 4. 平均耗时过长建议
  if (analysis.avgToolDuration > 8000) {
    suggestions.push({
      id: `tool_opt_${idCounter++}`,
      type: 'update_code',
      priority: 'medium',
      description: '优化工具层整体性能',
      reason: `工具平均耗时 ${(analysis.avgToolDuration / 1000).toFixed(1)}s，影响决策效率`,
      expectedImpact: '提升整体响应速度，改善用户体验',
      codeUpdate: {
        file: 'src/infrastructure/tools/shared/performance-optimizer.ts',
        function: 'optimizeToolPerformance',
        issue: '缺少统一的性能优化机制',
        modification: '实现请求缓存、批量处理、并行调用、超时控制',
        reason: `当前平均耗时 ${(analysis.avgToolDuration / 1000).toFixed(1)}s，目标 < 5s`
      }
    });
  }

  return suggestions;
}

/**
 * 评估工具是否需要优化
 */
export function shouldOptimizeTool(tool: ToolStats): boolean {
  return (
    tool.errorRate > 0.2 ||           // 错误率 > 20%
    tool.avgDuration > 10000 ||       // 平均耗时 > 10s
    (tool.callCount > 10 && tool.errorRate > 0.1) // 高频工具且错误率 > 10%
  );
}

/**
 * 生成工具效能报告摘要
 */
export function generateToolEfficiencySummary(assessment: ToolEfficiencyAssessment): string {
  const lines: string[] = [];

  lines.push(`工具效能评分: ${assessment.overallScore}/100`);

  if (assessment.problematicTools.length > 0) {
    lines.push(`高失败率工具: ${assessment.problematicTools.length} 个`);
  }

  if (assessment.slowTools.length > 0) {
    lines.push(`性能瓶颈工具: ${assessment.slowTools.length} 个`);
  }

  if (assessment.suggestions.length > 0) {
    lines.push(`优化建议: ${assessment.suggestions.length} 条`);
  }

  return lines.join(', ');
}
