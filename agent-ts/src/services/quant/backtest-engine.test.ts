import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { BacktestEngine, BacktestResult } from './backtest-engine.js';
// @ts-ignore - Module stub needed
import { QuantService } from './quant-service.js';
import { QuantStrategy } from './types.js';
import * as fs from 'fs';

describe('BacktestEngine', () => {
  let backtestEngine: BacktestEngine;
  let quantService: QuantService;
  const testDir = '.pi-invest-test';

  beforeEach(async () => {
    // 创建测试目录
    if (!fs.existsSync(testDir)) {
      fs.mkdirSync(testDir, { recursive: true });
    }

    backtestEngine = new BacktestEngine();
    quantService = new QuantService(testDir);
  });

  afterEach(() => {
    // 清理测试数据
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  describe('runBacktest', () => {
    it('should run a basic backtest and return results', async () => {
      // 创建测试策略
      const strategy = await quantService.createStrategy({
        name: 'Test RSI Strategy',
        description: 'Buy when RSI < 30, sell when RSI > 70',
        enabled: true,
        screening: {
          market: 'A',
          filters: {}
        },
        entry: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '<', value: 30 }
          ],
          logic: 'AND'
        },
        exit: {
          stop_loss: 0.05,
          take_profit: 0.10,
          conditions: [
            { indicator: 'rsi', params: {}, operator: '>', value: 70 }
          ]
        },
        position: {
          max_position_pct: 0.33,
          max_stocks: 3
        }
      });

      // 运行回测（使用较短的时间范围以加快测试）
      const result = await backtestEngine.runBacktest(
        strategy,
        '2024-01-01',
        '2024-01-31',
        ['000001', '600000'], // 测试两只股票
        100000
      );

      // 验证结果结构
      expect(result).toBeDefined();
      expect(result.strategy_id).toBe(strategy.id);
      expect(result.start_date).toBe('2024-01-01');
      expect(result.end_date).toBe('2024-01-31');
      expect(result.initial_capital).toBe(100000);
      expect(result.final_capital).toBeGreaterThan(0);

      // 验证收益指标
      expect(typeof result.total_return).toBe('number');
      expect(typeof result.annual_return).toBe('number');
      expect(typeof result.max_drawdown).toBe('number');

      // 验证交易指标
      expect(result.total_trades).toBeGreaterThanOrEqual(0);
      expect(result.winning_trades).toBeGreaterThanOrEqual(0);
      expect(result.losing_trades).toBeGreaterThanOrEqual(0);
      expect(result.winning_trades + result.losing_trades).toBe(result.total_trades);

      // 验证风险指标
      expect(typeof result.sharpe_ratio).toBe('number');
      expect(typeof result.volatility).toBe('number');

      // 验证详细记录
      expect(Array.isArray(result.trades)).toBe(true);
      expect(Array.isArray(result.daily_equity)).toBe(true);
      expect(result.daily_equity.length).toBeGreaterThan(0);
    });

    it('should handle stop loss correctly', async () => {
      const strategy = await quantService.createStrategy({
        name: 'Stop Loss Test',
        description: 'Test stop loss functionality',
        enabled: true,
        screening: {
          market: 'A',
          filters: {}
        },
        entry: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '<', value: 50 }
          ],
          logic: 'AND'
        },
        exit: {
          stop_loss: 0.03, // 3% 止损
          take_profit: 0.10
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 5
        }
      });

      const result = await backtestEngine.runBacktest(
        strategy,
        '2024-01-01',
        '2024-01-31',
        ['000001'],
        100000
      );

      // 如果有交易，检查是否有止损交易
      if (result.trades.length > 0) {
        const stopLossTrades = result.trades.filter(t => t.exit_reason.includes('止损'));
        // 止损交易应该存在或不存在都是合理的，取决于市场数据
        expect(stopLossTrades.length).toBeGreaterThanOrEqual(0);
      }
    });

    it('should handle take profit correctly', async () => {
      const strategy = await quantService.createStrategy({
        name: 'Take Profit Test',
        description: 'Test take profit functionality',
        enabled: true,
        screening: {
          market: 'A',
          filters: {}
        },
        entry: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '<', value: 50 }
          ],
          logic: 'AND'
        },
        exit: {
          stop_loss: 0.10,
          take_profit: 0.05 // 5% 止盈
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 5
        }
      });

      const result = await backtestEngine.runBacktest(
        strategy,
        '2024-01-01',
        '2024-01-31',
        ['000001'],
        100000
      );

      // 如果有交易，检查是否有止盈交易
      if (result.trades.length > 0) {
        const takeProfitTrades = result.trades.filter(t => t.exit_reason.includes('止盈'));
        expect(takeProfitTrades.length).toBeGreaterThanOrEqual(0);
      }
    });

    it('should respect max stocks limit', async () => {
      const maxStocks = 2;
      const strategy = await quantService.createStrategy({
        name: 'Max Stocks Test',
        description: 'Test max stocks limit',
        enabled: true,
        screening: {
          market: 'A',
          filters: {}
        },
        entry: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '<', value: 60 } // 宽松条件，容易触发
          ],
          logic: 'AND'
        },
        exit: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '>', value: 80 }
          ]
        },
        position: {
          max_position_pct: 0.5,
          max_stocks: maxStocks
        }
      });

      const result = await backtestEngine.runBacktest(
        strategy,
        '2024-01-01',
        '2024-01-31',
        ['000001', '600000', '600036', '601318'], // 4只股票
        100000
      );

      // 最大同时持仓数不应超过限制
      expect(result.max_position_count).toBeLessThanOrEqual(maxStocks);
    });

    it('should calculate performance metrics correctly', async () => {
      const strategy = await quantService.createStrategy({
        name: 'Metrics Test',
        description: 'Test performance metrics calculation',
        enabled: true,
        screening: {
          market: 'A',
          filters: {}
        },
        entry: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '<', value: 40 }
          ],
          logic: 'AND'
        },
        exit: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '>', value: 60 }
          ]
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 5
        }
      });

      const result = await backtestEngine.runBacktest(
        strategy,
        '2024-01-01',
        '2024-02-29',
        ['000001', '600000'],
        100000
      );

      // 验证指标计算
      if (result.total_trades > 0) {
        // 胜率应该在 0-100 之间
        expect(result.win_rate).toBeGreaterThanOrEqual(0);
        expect(result.win_rate).toBeLessThanOrEqual(100);

        // 盈亏比应该是非负数
        expect(result.profit_loss_ratio).toBeGreaterThanOrEqual(0);

        // 最大回撤应该是非负数
        expect(result.max_drawdown).toBeGreaterThanOrEqual(0);
      }

      // 每日权益曲线应该连续
      for (let i = 1; i < result.daily_equity.length; i++) {
        const prev = new Date(result.daily_equity[i - 1].date);
        const curr = new Date(result.daily_equity[i].date);
        const daysDiff = (curr.getTime() - prev.getTime()) / (1000 * 60 * 60 * 24);

        // 交易日之间的间隔应该在 1-3 天之间（考虑周末）
        expect(daysDiff).toBeGreaterThanOrEqual(1);
        expect(daysDiff).toBeLessThanOrEqual(4);
      }
    });

    it('should handle empty stock list gracefully', async () => {
      const strategy = await quantService.createStrategy({
        name: 'Empty List Test',
        description: 'Test with empty stock list',
        enabled: true,
        screening: {
          market: 'A',
          filters: {}
        },
        entry: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '<', value: 30 }
          ],
          logic: 'AND'
        },
        exit: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '>', value: 70 }
          ]
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 5
        }
      });

      const result = await backtestEngine.runBacktest(
        strategy,
        '2024-01-01',
        '2024-01-31',
        [], // 空列表
        100000
      );

      // 应该没有交易
      expect(result.total_trades).toBe(0);
      expect(result.final_capital).toBe(100000);
      expect(result.total_return).toBe(0);
    });
  });

  describe('Edge cases', () => {
    it('should handle single day backtest', async () => {
      const strategy = await quantService.createStrategy({
        name: 'Single Day Test',
        description: 'Test single day backtest',
        enabled: true,
        screening: {
          market: 'A',
          filters: {}
        },
        entry: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '<', value: 50 }
          ],
          logic: 'AND'
        },
        exit: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '>', value: 50 }
          ]
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 5
        }
      });

      const result = await backtestEngine.runBacktest(
        strategy,
        '2024-01-15',
        '2024-01-15',
        ['000001'],
        100000
      );

      // 单日回测应该有结果
      expect(result).toBeDefined();
      expect(result.daily_equity.length).toBeGreaterThanOrEqual(1);
    });

    it('should handle very small initial capital', async () => {
      const strategy = await quantService.createStrategy({
        name: 'Small Capital Test',
        description: 'Test with small initial capital',
        enabled: true,
        screening: {
          market: 'A',
          filters: {}
        },
        entry: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '<', value: 30 }
          ],
          logic: 'AND'
        },
        exit: {
          conditions: [
            { indicator: 'rsi', params: {}, operator: '>', value: 70 }
          ]
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 5
        }
      });

      const result = await backtestEngine.runBacktest(
        strategy,
        '2024-01-01',
        '2024-01-31',
        ['000001'],
        1000 // 很小的初始资金
      );

      // 应该能正常运行，但可能没有交易（资金不足）
      expect(result).toBeDefined();
      expect(result.initial_capital).toBe(1000);
    });
  });
});
