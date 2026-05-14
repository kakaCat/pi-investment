/**
 * Evolution Integration Test - 端到端集成测试
 *
 * 验证完整的进化流程：
 * 1. 从交易数据计算收益
 * 2. 运行减法器分析差距
 * 3. 运行补偿器生成建议
 * 4. 生成并保存进化报告
 * 5. 验证经验库可以被查询
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import * as fs from 'fs/promises';
import * as path from 'path';
import { calculateGap, attributeGap } from './comparator.js';
import { determineOptimizerStrategy, generateOptimizationSuggestions } from './compensator.js';
import { generateEvolutionReport, formatReportAsMarkdown } from './evolution-reporter.js';
import { addExperience, queryExperience, loadExperienceBase } from './experience-manager.js';
import type { DecisionQualityMetrics, Experience } from '../../types/evolution.js';

describe('Evolution System - End-to-End Integration', () => {
  const testBaseDir = path.join(process.cwd(), '.pi-invest-test');
  const evolutionDir = path.join(testBaseDir, 'evolution');
  const experienceDir = path.join(testBaseDir, 'experience');

  beforeEach(async () => {
    // 创建测试目录
    await fs.mkdir(evolutionDir, { recursive: true });
    await fs.mkdir(experienceDir, { recursive: true });
  });

  afterEach(async () => {
    // 清理测试目录
    try {
      await fs.rm(testBaseDir, { recursive: true, force: true });
    } catch (err) {
      // Ignore cleanup errors
    }
  });

  it('应该完成完整的进化流程', async () => {
    // Step 1: 模拟交易数据，计算收益
    const target = 10;  // 目标收益率 10%
    const actual = 6.67; // 实际收益率 6.67%
    const market = 5;    // 大盘收益率 5%

    // Step 2: 运行减法器分析差距
    const gap = calculateGap(target, actual, market);
    expect(gap.gap).toBeCloseTo(3.33, 1);
    expect(gap.alpha).toBeCloseTo(1.67, 1);

    // Step 3: 归因分析
    const historicalReturns = [8, 7.5, 9, 6.5, 7];
    const marketVolatility = 15;
    const decisionQuality: DecisionQualityMetrics = {
      recentReturns: [6, 7, 5, 8, 6.67],
      errorRate: 0.4,
      stopLossExecutionRate: 0.55
    };

    const attribution = attributeGap(gap, historicalReturns, marketVolatility, decisionQuality);
    expect(attribution.rootCause).toBe('capability_insufficient');
    expect(attribution.recommendation).toBe('trigger_optimizer');

    // Step 4: 运行补偿器生成建议
    const strategy = determineOptimizerStrategy(gap.gap);
    expect(strategy.level).toBe('moderate');

    const suggestions = generateOptimizationSuggestions({
      level: strategy.level,
      toolStats: [
        {
          tool_name: 'bad_tool',
          call_count: 10,
          decisions_after_call: 8,
          win_rate: 0.3,
          avg_return: -2.5,
          avg_tokens: 500,
          cost_per_call: 0.01,
          roi: -5.0,
          rating: 1
        }
      ],
      weaknesses: ['风控能力', '选股能力']
    });

    expect(suggestions.length).toBeGreaterThan(0);
    expect(suggestions.some(s => s.type === 'remove_tool')).toBe(true);
    expect(suggestions.some(s => s.type === 'add_tool')).toBe(true);

    // Step 5: 生成并保存进化报告
    const report = generateEvolutionReport({
      period: '2026-05-01 ~ 2026-05-14',
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
      toolStats: [
        {
          tool_name: 'bad_tool',
          call_count: 10,
          decisions_after_call: 8,
          win_rate: 0.3,
          avg_return: -2.5,
          avg_tokens: 500,
          cost_per_call: 0.01,
          roi: -5.0,
          rating: 1
        }
      ],
      suggestions
    });

    expect(report.period).toBe('2026-05-01 ~ 2026-05-14');
    expect(report.performance.gap).toBeCloseTo(3.33, 1);
    expect(report.suggestions.length).toBeGreaterThan(0);

    // Step 6: 保存报告
    const markdown = formatReportAsMarkdown(report);
    expect(markdown).toContain('# 进化报告');
    expect(markdown).toContain('## 📊 本月表现');
    expect(markdown).toContain('## 🔍 减法器归因分析');
    expect(markdown).toContain('## 💡 补偿器调整方案');

    const reportPath = path.join(evolutionDir, 'evolution-2026-05-14.md');
    await fs.writeFile(reportPath, markdown, 'utf-8');

    // 验证报告文件存在
    const reportExists = await fs.access(reportPath).then(() => true).catch(() => false);
    expect(reportExists).toBe(true);

    // Step 7: 验证经验库可以被查询
    const experience: Experience = {
      id: 'exp_001',
      scenario: '高位追涨后回调',
      pattern: {
        conditions: ['股价创新高', '成交量放大', 'RSI > 70'],
        action: 'sell'
      },
      outcomes: {
        total_cases: 10,
        win_rate: 0.7,
        avg_return: 3.5,
        max_gain: 8.0,
        max_loss: -2.0
      },
      recommendation: 'moderate',
      reason: '高位追涨风险较大，及时止盈',
      examples: [
        {
          date: '2026-05-10',
          symbol: '600519',
          session_id: 'session_001',
          result: 3.5
        }
      ],
      confidence: 0.85,
      last_updated: '2026-05-14'
    };

    addExperience(experience, testBaseDir);

    // 查询经验
    const results = queryExperience(
      { scenario: '高位追涨' },
      testBaseDir
    );

    expect(results.length).toBeGreaterThan(0);
    expect(results[0].id).toBe('exp_001');
    expect(results[0].outcomes.win_rate).toBe(0.7);
  });

  it('应该正确处理多个经验的查询', async () => {
    // 添加多个经验
    const experiences: Experience[] = [
      {
        id: 'exp_001',
        scenario: '突破平台后回踩',
        pattern: {
          conditions: ['突破平台', '回踩支撑'],
          action: 'buy'
        },
        outcomes: {
          total_cases: 15,
          win_rate: 0.8,
          avg_return: 5.2
        },
        recommendation: 'aggressive',
        reason: '突破后回踩是较好的买入时机',
        examples: [],
        confidence: 0.9,
        last_updated: '2026-05-14'
      },
      {
        id: 'exp_002',
        scenario: '跌破支撑位',
        pattern: {
          conditions: ['跌破支撑', '成交量放大'],
          action: 'sell'
        },
        outcomes: {
          total_cases: 20,
          win_rate: 0.75,
          avg_return: -3.5
        },
        recommendation: 'cautious',
        reason: '跌破支撑后容易继续下跌',
        examples: [],
        confidence: 0.85,
        last_updated: '2026-05-14'
      },
      {
        id: 'exp_003',
        scenario: '横盘整理',
        pattern: {
          conditions: ['横盘整理', '成交量萎缩'],
          action: 'hold'
        },
        outcomes: {
          total_cases: 30,
          win_rate: 0.6,
          avg_return: 1.0
        },
        recommendation: 'moderate',
        reason: '横盘整理期间观望为主',
        examples: [],
        confidence: 0.7,
        last_updated: '2026-05-14'
      }
    ];

    for (const exp of experiences) {
      addExperience(exp, testBaseDir);
    }

    // 按场景查询
    const breakoutResults = queryExperience(
      { scenario: '突破' },
      testBaseDir
    );
    expect(breakoutResults.length).toBeGreaterThan(0);
    expect(breakoutResults[0].id).toBe('exp_001');

    // 按条件查询
    const supportResults = queryExperience(
      { conditions: ['支撑'] },
      testBaseDir
    );
    expect(supportResults.length).toBeGreaterThanOrEqual(2);

    // 验证按置信度排序
    const allResults = queryExperience({}, testBaseDir);
    expect(allResults.length).toBe(3);
    expect(allResults[0].confidence).toBeGreaterThanOrEqual(allResults[1].confidence);
    expect(allResults[1].confidence).toBeGreaterThanOrEqual(allResults[2].confidence);
  });

  it('应该正确处理经验库的更新', async () => {
    // 添加初始经验
    const experience: Experience = {
      id: 'exp_001',
      scenario: '测试场景',
      pattern: {
        conditions: ['条件1'],
        action: 'buy'
      },
      outcomes: {
        total_cases: 10,
        win_rate: 0.6,
        avg_return: 2.0
      },
      recommendation: 'moderate',
      reason: '初始原因',
      examples: [],
      confidence: 0.7,
      last_updated: '2026-05-14'
    };

    addExperience(experience, testBaseDir);

    // 更新经验
    const updatedExperience: Experience = {
      ...experience,
      outcomes: {
        total_cases: 20,
        win_rate: 0.7,
        avg_return: 3.0
      },
      confidence: 0.8,
      last_updated: '2026-05-15'
    };

    addExperience(updatedExperience, testBaseDir);

    // 验证更新
    const base = loadExperienceBase(testBaseDir);
    expect(base.experiences.length).toBe(1);
    expect(base.experiences[0].outcomes.total_cases).toBe(20);
    expect(base.experiences[0].outcomes.win_rate).toBe(0.7);
    expect(base.experiences[0].confidence).toBe(0.8);
  });

  it('应该生成包含完整信息的报告', async () => {
    // 完整的进化流程
    const gap = calculateGap(10, 6.67, 5);
    const attribution = attributeGap(
      gap,
      [8, 7.5, 9, 6.5, 7],
      15,
      {
        recentReturns: [6, 7, 5, 8, 6.67],
        errorRate: 0.4,
        stopLossExecutionRate: 0.55
      }
    );

    const strategy = determineOptimizerStrategy(gap.gap);
    const suggestions = generateOptimizationSuggestions({
      level: strategy.level,
      toolStats: [],
      weaknesses: ['风控能力'],
      newPatterns: [
        {
          pattern: '高位追涨失败',
          winRate: 0.3,
          avgReturn: -2.5
        }
      ]
    });

    const report = generateEvolutionReport({
      period: '2026-05-01 ~ 2026-05-14',
      performance: {
        target: 10,
        actual: 6.67,
        gap: gap.gap,
        market: 5,
        winRate: 0.6,
        maxDrawdown: -8,
        sharpeRatio: 1.2
      },
      attribution,
      toolStats: [],
      suggestions,
      successPatterns: [
        {
          pattern: '突破后回踩买入',
          count: 5,
          winRate: 0.8,
          avgReturn: 4.5
        }
      ],
      failurePatterns: [
        {
          pattern: '高位追涨',
          count: 3,
          winRate: 0.3,
          avgLoss: -2.5
        }
      ]
    });

    const markdown = formatReportAsMarkdown(report);

    // 验证报告包含所有关键部分
    expect(markdown).toContain('# 进化报告');
    expect(markdown).toContain('## 📊 本月表现');
    expect(markdown).toContain('月收益率');
    expect(markdown).toContain('胜率');
    expect(markdown).toContain('最大回撤');
    expect(markdown).toContain('夏普比率');
    expect(markdown).toContain('## 🔍 减法器归因分析');
    expect(markdown).toContain('根本原因');
    expect(markdown).toContain('## 💡 补偿器调整方案');
    expect(markdown).toContain('生成时间');

    // 验证建议包含新增能力和经验库更新
    expect(suggestions.some(s => s.type === 'add_tool')).toBe(true);
    expect(suggestions.some(s => s.type === 'update_experience')).toBe(true);
  });
});
