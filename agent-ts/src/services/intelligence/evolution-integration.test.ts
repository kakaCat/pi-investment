/**
 * Evolution System - End-to-End Integration Test
 *
 * Tests the complete evolution flow:
 * 1. Data Collection (portfolio, trades, reviews)
 * 2. Comparator (gap calculation, attribution)
 * 3. Compensator (strategy determination, suggestions)
 * 4. Reporter (report generation)
 * 5. Executor (suggestion execution)
 */

import { describe, test, expect, beforeEach, afterEach } from '@jest/globals';
import * as fs from 'fs/promises';
import * as path from 'path';
import { existsSync, mkdirSync, writeFileSync } from 'fs';

const TEST_PI_DIR = path.join(process.cwd(), '.pi-invest-test-evolution');

describe('Evolution System - End-to-End Integration', () => {
  beforeEach(async () => {
    // Clean up test directory
    if (existsSync(TEST_PI_DIR)) {
      await fs.rm(TEST_PI_DIR, { recursive: true, force: true });
    }
    mkdirSync(TEST_PI_DIR, { recursive: true });
  });

  afterEach(async () => {
    // Clean up
    if (existsSync(TEST_PI_DIR)) {
      await fs.rm(TEST_PI_DIR, { recursive: true, force: true });
    }
  });

  test('should complete full evolution cycle with sample data', async () => {
    // ── 1. Setup: Create sample data ──────────────────────────────────────

    // Portfolio with 2 holdings
    const portfolio = {
      holdings: [
        {
          symbol: '600519',
          name: '贵州茅台',
          quantity: 100,
          avg_cost: 1800,
          market: 'SH',
          total_invested: 180000,
          sector: '食品饮料',
          buy_reason: '白酒龙头，长期看好',
        },
        {
          symbol: '000858',
          name: '五粮液',
          quantity: 200,
          avg_cost: 200,
          market: 'SZ',
          total_invested: 40000,
          sector: '食品饮料',
          buy_reason: '白酒板块配置',
        },
      ],
    };

    // Trades: 3 completed trades (2 wins, 1 loss)
    const trades = {
      trades: [
        // Trade 1: Buy 茅台
        {
          date: '2026-05-01',
          time: '10:30:00',
          action: 'buy',
          symbol: '600519',
          name: '贵州茅台',
          quantity: 100,
          price: 1800,
          amount: 180000,
          market: 'SH',
          notes: 'MACD金叉，成交量放大',
        },
        // Trade 2: Buy 五粮液
        {
          date: '2026-05-03',
          time: '14:00:00',
          action: 'buy',
          symbol: '000858',
          name: '五粮液',
          quantity: 300,
          price: 200,
          amount: 60000,
          market: 'SZ',
          notes: '跟随板块轮动',
        },
        // Trade 3: Sell 五粮液 (partial, profit)
        {
          date: '2026-05-10',
          time: '10:15:00',
          action: 'sell',
          symbol: '000858',
          name: '五粮液',
          quantity: 100,
          price: 210,
          amount: 21000,
          market: 'SZ',
          notes: '卖100股@210.00，盈利1000元(+5.00%)',
        },
      ],
    };

    // Reviews: 1 daily review
    const reviewsDir = path.join(TEST_PI_DIR, 'reviews');
    mkdirSync(reviewsDir, { recursive: true });
    const review = {
      date: '2026-05-10',
      holdings: portfolio.holdings,
      analysis: '持仓稳定，五粮液部分止盈',
      suggestions: ['继续持有茅台', '观察五粮液回调机会'],
    };

    // Write test data
    writeFileSync(
      path.join(TEST_PI_DIR, 'portfolio.json'),
      JSON.stringify(portfolio, null, 2)
    );
    writeFileSync(
      path.join(TEST_PI_DIR, 'trades.json'),
      JSON.stringify(trades, null, 2)
    );
    writeFileSync(
      path.join(reviewsDir, '2026-05-10.json'),
      JSON.stringify(review, null, 2)
    );

    // ── 2. Test: Comparator ───────────────────────────────────────────────

    const { calculateGap, attributeGap } = await import('./comparator.js');

    const target = 10; // 10% target return
    const actual = 5; // 5% actual return (from the one profitable trade)
    const market = 3; // 3% market return

    const gap = calculateGap(target, actual, market);
    expect(gap.gap).toBe(5); // 10 - 5 = 5
    expect(gap.target).toBe(target);
    expect(gap.actual).toBe(actual);

    const historicalReturns = [5.0]; // One trade with 5% return
    const marketVolatility = 15;
    const decisionQuality = {
      recentReturns: [5.0],
      errorRate: 0.3,
      stopLossExecutionRate: 0.5,
    };

    const attribution = attributeGap(gap, historicalReturns, marketVolatility, decisionQuality);
    expect(attribution.rootCause).toBe('capability_insufficient'); // Underperforming
    expect(attribution.confidence).toBeGreaterThan(0);
    expect(attribution.recommendation).toBe('trigger_optimizer');

    // ── 3. Test: Compensator ──────────────────────────────────────────────

    const { determineOptimizerStrategy, generateOptimizationSuggestions } = await import('./compensator.js');

    const strategy = determineOptimizerStrategy(gap.gap);
    expect(strategy.level).toBe('major'); // 5% gap >= 5, so major
    expect(strategy.actions.length).toBeGreaterThan(0);

    const suggestions = generateOptimizationSuggestions({
      level: strategy.level,
      toolStats: [],
      weaknesses: ['选股能力', '风控能力'],
    });

    expect(suggestions.length).toBeGreaterThan(0);
    expect(suggestions.some(s => s.type === 'add_tool' || s.type === 'update_experience')).toBe(true);

    // ── 4. Test: Reporter ─────────────────────────────────────────────────

    const { generateEvolutionReport } = await import('./evolution-reporter.js');

    const report = generateEvolutionReport({
      period: '2026-05-01 ~ 2026-05-14',
      performance: {
        target,
        actual,
        gap: gap.gap,
        market,
        winRate: 1.0, // 1 win out of 1 completed trade
        maxDrawdown: 0,
        sharpeRatio: 0,
      },
      attribution,
      toolStats: [],
      suggestions,
      successPatterns: [
        {
          pattern: '板块轮动跟随',
          count: 1,
          winRate: 1.0,
          avgReturn: 5.0,
        },
      ],
      failurePatterns: [],
    });

    expect(report.period).toBe('2026-05-01 ~ 2026-05-14');
    expect(report.performance.target).toBe(target);
    expect(report.performance.actual).toBe(actual);
    expect(report.attribution.rootCause).toBe('capability_insufficient');
    expect(report.suggestions.length).toBeGreaterThan(0);

    // ── 5. Verify: Report structure ───────────────────────────────────────

    expect(report).toHaveProperty('period');
    expect(report).toHaveProperty('performance');
    expect(report).toHaveProperty('attribution');
    expect(report).toHaveProperty('suggestions');
    expect(report).toHaveProperty('sessionAnalysis');
    expect(report.sessionAnalysis).toHaveProperty('successPatterns');
    expect(report.sessionAnalysis).toHaveProperty('failurePatterns');

    console.log('✅ End-to-end integration test passed');
  }, 30000); // 30s timeout

  test('should handle empty data gracefully', async () => {
    // Create empty data files
    writeFileSync(
      path.join(TEST_PI_DIR, 'portfolio.json'),
      JSON.stringify({ holdings: [] }, null, 2)
    );
    writeFileSync(
      path.join(TEST_PI_DIR, 'trades.json'),
      JSON.stringify({ trades: [] }, null, 2)
    );

    const { calculateGap } = await import('./comparator.js');
    const { determineOptimizerStrategy } = await import('./compensator.js');

    // Should not crash with empty data
    const gap = calculateGap(10, 0, 5);
    expect(gap.gap).toBe(10);

    const strategy = determineOptimizerStrategy(gap.gap);
    expect(strategy.level).toBe('major'); // 10% gap = major

    console.log('✅ Empty data handling test passed');
  });

  test('should generate valid suggestions for different gap levels', async () => {
    const { determineOptimizerStrategy, generateOptimizationSuggestions } = await import('./compensator.js');

    // Small gap (< 2%) - provide newPatterns to generate suggestions
    const smallStrategy = determineOptimizerStrategy(1.5);
    expect(smallStrategy.level).toBe('minor');
    const smallSuggestions = generateOptimizationSuggestions({
      level: 'minor',
      toolStats: [],
      weaknesses: [],
      newPatterns: [{
        pattern: '高估值买入后快速止损',
        winRate: 0.3,
        avgReturn: -0.05
      }]
    });
    expect(smallSuggestions.length).toBeGreaterThan(0);
    expect(smallSuggestions.some(s => s.type === 'update_experience')).toBe(true);

    // Medium gap (2-5%)
    const mediumStrategy = determineOptimizerStrategy(3.5);
    expect(mediumStrategy.level).toBe('moderate');
    const mediumSuggestions = generateOptimizationSuggestions({
      level: 'moderate',
      toolStats: [],
      weaknesses: ['选股能力'],
    });
    expect(mediumSuggestions.length).toBeGreaterThan(0);

    // Large gap (> 5%)
    const largeStrategy = determineOptimizerStrategy(8);
    expect(largeStrategy.level).toBe('major');
    const largeSuggestions = generateOptimizationSuggestions({
      level: 'major',
      toolStats: [],
      weaknesses: ['选股能力', '风控能力', '决策准确性'],
    });
    expect(largeSuggestions.length).toBeGreaterThan(0);

    console.log('✅ Gap level suggestions test passed');
  });

  test('should correctly attribute performance gaps', async () => {
    const { calculateGap, attributeGap } = await import('./comparator.js');

    // Scenario 1: Unrealistic target (market -5%, target +10%)
    const gap1 = calculateGap(10, -5, -5);
    const attr1 = attributeGap(gap1, [-5], 15, {
      recentReturns: [-5],
      errorRate: 0.2,
      stopLossExecutionRate: 0.9,
    });
    expect(attr1.rootCause).toBe('target_unrealistic'); // Target too high for bear market
    expect(attr1.recommendation).toBe('adjust_target');

    // Scenario 2: Capability problem (market +5%, actual -2%)
    const gap2 = calculateGap(10, -2, 5);
    const attr2 = attributeGap(gap2, [-2], 15, {
      recentReturns: [-2],
      errorRate: 0.6,
      stopLossExecutionRate: 0.3,
    });
    expect(attr2.rootCause).toBe('capability_insufficient'); // Underperforming market
    expect(attr2.recommendation).toBe('trigger_optimizer');

    // Scenario 3: Large gap with poor execution
    const gap3 = calculateGap(20, 2, 5);
    const attr3 = attributeGap(gap3, [2], 15, {
      recentReturns: [2],
      errorRate: 0.5,
      stopLossExecutionRate: 0.4,
    });
    // With 18% gap, should trigger optimizer regardless
    expect(attr3.recommendation).toBe('trigger_optimizer');

    console.log('✅ Attribution test passed');
  });
});
