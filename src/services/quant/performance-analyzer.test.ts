/**
 * PerformanceAnalyzer Tests
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { PerformanceAnalyzer } from './performance-analyzer.js';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'fs';
import { join } from 'path';
import type { Signal } from './types.js';

describe('PerformanceAnalyzer', () => {
  const testDir = '.pi-invest-test/quant/signals';
  let analyzer: PerformanceAnalyzer;

  beforeEach(() => {
    // 创建测试目录
    mkdirSync(testDir, { recursive: true });
    analyzer = new PerformanceAnalyzer(testDir);
  });

  afterEach(() => {
    // 清理测试数据
    if (existsSync('.pi-invest-test')) {
      rmSync('.pi-invest-test', { recursive: true, force: true });
    }
  });

  it('should return empty metrics when no signals exist', async () => {
    const metrics = await analyzer.analyzeStrategy('test-strategy', 'Test Strategy', 30);

    expect(metrics.strategy_id).toBe('test-strategy');
    expect(metrics.strategy_name).toBe('Test Strategy');
    expect(metrics.total_signals).toBe(0);
    expect(metrics.win_rate).toBe(0);
    expect(metrics.avg_profit_pct).toBe(0);
  });

  it('should analyze strategy with buy signals', async () => {
    // 创建测试信号数据
    const signals: Signal[] = [
      {
        symbol: '600036.SH',
        name: '招商银行',
        action: 'buy',
        confidence: 0.85,
        reason: 'RSI超卖',
        price: 40.0,
        date: new Date().toISOString(),
        strategy_id: 'rsi-strategy',
        indicators: {
          rsi: 28,
          ma5: 39.5,
          ma10: 39.8,
          ma20: 40.2,
          ma60: 41.0,
          macd: { dif: -0.5, dea: -0.3, macd: -0.2 },
          bollinger: { upper: 42.0, middle: 40.0, lower: 38.0 },
          volume_ratio: 1.2,
          atr: 1.5
        }
      },
      {
        symbol: '000425.SZ',
        name: '徐工机械',
        action: 'buy',
        confidence: 0.75,
        reason: 'MACD金叉',
        price: 7.0,
        date: new Date().toISOString(),
        strategy_id: 'rsi-strategy',
        indicators: {
          rsi: 55,
          ma5: 6.9,
          ma10: 6.8,
          ma20: 6.7,
          ma60: 6.5,
          macd: { dif: 0.1, dea: 0.05, macd: 0.05 },
          bollinger: { upper: 7.5, middle: 7.0, lower: 6.5 },
          volume_ratio: 1.5,
          atr: 0.3
        }
      }
    ];

    // 写入信号文件
    const signalFile = join(testDir, '2026-05-16.json');
    writeFileSync(signalFile, JSON.stringify({ signals }, null, 2));

    const metrics = await analyzer.analyzeStrategy('rsi-strategy', 'RSI Strategy', 30);

    expect(metrics.strategy_id).toBe('rsi-strategy');
    expect(metrics.strategy_name).toBe('RSI Strategy');
    expect(metrics.total_signals).toBe(2);
    expect(metrics.buy_signals).toBe(2);
    expect(metrics.sell_signals).toBe(0);
    expect(metrics.win_rate).toBeGreaterThanOrEqual(0);
    expect(metrics.win_rate).toBeLessThanOrEqual(100);
  });

  it('should calculate win rate correctly', async () => {
    // 创建多个信号以测试胜率计算
    const signals: Signal[] = [];
    const now = new Date();

    for (let i = 0; i < 10; i++) {
      const date = new Date(now);
      date.setDate(date.getDate() - i);

      signals.push({
        symbol: '600036.SH',
        name: '招商银行',
        action: 'buy',
        confidence: 0.6 + (i % 3) * 0.1, // 变化的置信度
        reason: '测试信号',
        price: 40.0 + i * 0.5,
        date: date.toISOString(),
        strategy_id: 'test-strategy',
        indicators: {
          rsi: 50,
          ma5: 40,
          ma10: 40,
          ma20: 40,
          ma60: 40,
          macd: { dif: 0, dea: 0, macd: 0 },
          bollinger: { upper: 42, middle: 40, lower: 38 },
          volume_ratio: 1.0,
          atr: 1.0
        }
      });
    }

    const signalFile = join(testDir, 'test-signals.json');
    writeFileSync(signalFile, JSON.stringify({ signals }, null, 2));

    const metrics = await analyzer.analyzeStrategy('test-strategy', 'Test Strategy', 30);

    expect(metrics.total_signals).toBe(10);
    expect(metrics.profitable_trades).toBeGreaterThanOrEqual(0);
    expect(metrics.losing_trades).toBeGreaterThanOrEqual(0);
    expect(metrics.profitable_trades + metrics.losing_trades).toBe(10);
  });

  it('should filter signals by date range', async () => {
    const now = new Date();
    const signals: Signal[] = [];

    // 创建45天前的信号（应该被过滤掉）
    const oldDate = new Date(now);
    oldDate.setDate(oldDate.getDate() - 45);
    signals.push({
      symbol: '600036.SH',
      name: '招商银行',
      action: 'buy',
      confidence: 0.8,
      reason: '旧信号',
      price: 40.0,
      date: oldDate.toISOString(),
      strategy_id: 'test-strategy',
      indicators: {
        rsi: 50,
        ma5: 40,
        ma10: 40,
        ma20: 40,
        ma60: 40,
        macd: { dif: 0, dea: 0, macd: 0 },
        bollinger: { upper: 42, middle: 40, lower: 38 },
        volume_ratio: 1.0,
        atr: 1.0
      }
    });

    // 创建15天前的信号（应该被包含）
    const recentDate = new Date(now);
    recentDate.setDate(recentDate.getDate() - 15);
    signals.push({
      symbol: '000425.SZ',
      name: '徐工机械',
      action: 'buy',
      confidence: 0.75,
      reason: '新信号',
      price: 7.0,
      date: recentDate.toISOString(),
      strategy_id: 'test-strategy',
      indicators: {
        rsi: 55,
        ma5: 7,
        ma10: 7,
        ma20: 7,
        ma60: 7,
        macd: { dif: 0, dea: 0, macd: 0 },
        bollinger: { upper: 7.5, middle: 7, lower: 6.5 },
        volume_ratio: 1.0,
        atr: 0.3
      }
    });

    const signalFile = join(testDir, 'mixed-dates.json');
    writeFileSync(signalFile, JSON.stringify({ signals }, null, 2));

    const metrics = await analyzer.analyzeStrategy('test-strategy', 'Test Strategy', 30);

    // 只有15天前的信号应该被包含
    expect(metrics.total_signals).toBe(1);
    expect(metrics.first_signal_date).toBe(recentDate.toISOString());
  });

  it('should calculate performance metrics correctly', async () => {
    const signals: Signal[] = [
      {
        symbol: '600036.SH',
        name: '招商银行',
        action: 'buy',
        confidence: 0.9, // 高置信度
        reason: '强买入信号',
        price: 40.0,
        date: new Date().toISOString(),
        strategy_id: 'test-strategy',
        indicators: {
          rsi: 25,
          ma5: 40,
          ma10: 40,
          ma20: 40,
          ma60: 40,
          macd: { dif: 0.5, dea: 0.3, macd: 0.2 },
          bollinger: { upper: 42, middle: 40, lower: 38 },
          volume_ratio: 1.5,
          atr: 1.0
        }
      }
    ];

    const signalFile = join(testDir, 'performance-test.json');
    writeFileSync(signalFile, JSON.stringify({ signals }, null, 2));

    const metrics = await analyzer.analyzeStrategy('test-strategy', 'Test Strategy', 30);

    expect(metrics.total_signals).toBe(1);
    expect(metrics.max_drawdown_pct).toBeGreaterThanOrEqual(0);
    expect(metrics.first_signal_date).toBeDefined();
    expect(metrics.last_signal_date).toBeDefined();
  });

  it('should handle multiple signal files', async () => {
    // 创建多个日期的信号文件
    const dates = ['2026-05-14', '2026-05-15', '2026-05-16'];

    for (const date of dates) {
      const signals: Signal[] = [
        {
          symbol: '600036.SH',
          name: '招商银行',
          action: 'buy',
          confidence: 0.8,
          reason: '测试',
          price: 40.0,
          date: new Date(date).toISOString(),
          strategy_id: 'multi-file-strategy',
          indicators: {
            rsi: 50,
            ma5: 40,
            ma10: 40,
            ma20: 40,
            ma60: 40,
            macd: { dif: 0, dea: 0, macd: 0 },
            bollinger: { upper: 42, middle: 40, lower: 38 },
            volume_ratio: 1.0,
            atr: 1.0
          }
        }
      ];

      const signalFile = join(testDir, `${date}.json`);
      writeFileSync(signalFile, JSON.stringify({ signals }, null, 2));
    }

    const metrics = await analyzer.analyzeStrategy('multi-file-strategy', 'Multi File Strategy', 30);

    expect(metrics.total_signals).toBe(3);
  });
});
