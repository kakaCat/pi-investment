/**
 * Evolution Service - 进化服务主入口
 *
 * 协调各个组件完成完整的进化流程
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { calculateGap, attributeGap } from './comparator';
import { determineOptimizerStrategy, generateOptimizationSuggestions } from './compensator';
import { generateEvolutionReport, formatReportAsMarkdown } from './evolution-reporter';
import type { EvolutionReport, DecisionQualityMetrics } from '../../types/evolution.js';

interface EvolutionResult {
  reportPath: string;
  report: EvolutionReport;
}

/**
 * 运行周度进化流程
 */
export async function runWeeklyEvolution(): Promise<EvolutionResult> {
  // 1. 计算性能差距（使用模拟数据）
  const target = 10;  // 目标收益率 10%
  const actual = 6.67; // 实际收益率 6.67%
  const market = 5;    // 大盘收益率 5%

  const gap = calculateGap(target, actual, market);

  // 2. 归因分析
  const historicalReturns = [8, 7.5, 9, 6.5, 7]; // 历史收益率
  const marketVolatility = 15; // 市场波动率
  const decisionQuality: DecisionQualityMetrics = {
    recentReturns: [6, 7, 5, 8, 6.67],
    errorRate: 0.4,
    stopLossExecutionRate: 0.55
  };

  const attribution = attributeGap(gap, historicalReturns, marketVolatility, decisionQuality);

  // 3. 确定优化策略
  const strategy = determineOptimizerStrategy(gap.gap);

  // 4. 生成优化建议
  const suggestions = generateOptimizationSuggestions({
    level: strategy.level,
    toolStats: [], // 简化版本，暂时不加载工具统计
    weaknesses: ['风控能力', '选股能力']
  });

  // 5. 生成报告
  const report = generateEvolutionReport({
    period: `2026-05-01 ~ ${new Date().toISOString().split('T')[0]}`,
    performance: {
      target,
      actual,
      gap: gap.gap,
      market,
      winRate: 0.6,
      maxDrawdown: -8,
      sharpeRatio: 1.2
    },
    attribution,
    toolStats: [],
    suggestions
  });

  // 6. 格式化为 Markdown
  const markdown = formatReportAsMarkdown(report);

  // 7. 保存报告
  const evolutionDir = path.join(process.cwd(), '.pi-invest', 'evolution');
  await fs.mkdir(evolutionDir, { recursive: true });

  const timestamp = new Date().toISOString().split('T')[0];
  const reportPath = path.join(evolutionDir, `evolution-${timestamp}.md`);
  await fs.writeFile(reportPath, markdown, 'utf-8');

  return {
    reportPath,
    report
  };
}
