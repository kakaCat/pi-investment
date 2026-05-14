/**
 * Data Collector Tests
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'fs';
import { join } from 'path';
import {
  loadPortfolio,
  loadTrades,
  parsePortfolio,
  parseTrades,
  calculateTradeStats,
  groupTradesBySymbol,
  loadReviews,
  extractPatternsFromReviews,
  collectAllData,
  type Portfolio,
  type TradeHistory,
  type Trade,
} from './data-collector.js';

const TEST_DIR = join(process.cwd(), '.test-data');

describe('Data Collector', () => {
  beforeEach(() => {
    // 创建测试目录
    if (existsSync(TEST_DIR)) {
      rmSync(TEST_DIR, { recursive: true });
    }
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    // 清理测试目录
    if (existsSync(TEST_DIR)) {
      rmSync(TEST_DIR, { recursive: true });
    }
  });

  describe('loadPortfolio', () => {
    it('should load valid portfolio data', () => {
      const portfolio: Portfolio = {
        holdings: [
          {
            symbol: '600036',
            name: '招商银行',
            quantity: 300,
            avg_cost: 37.89,
            market: 'A',
            notes: 'Test holding',
            added_date: '2026-05-13',
            original_cost: 37.89,
            total_invested: 11367,
            stop_loss: null,
            target_price: null,
            batch_plan: null,
            sector: '银行',
            buy_reason: 'Test reason',
          },
        ],
        last_updated: '2026-05-14',
      };

      writeFileSync(
        join(TEST_DIR, 'portfolio.json'),
        JSON.stringify(portfolio, null, 2)
      );

      const loaded = loadPortfolio(TEST_DIR);
      expect(loaded.holdings).toHaveLength(1);
      expect(loaded.holdings[0].symbol).toBe('600036');
      expect(loaded.holdings[0].name).toBe('招商银行');
    });

    it('should throw error if portfolio file not found', () => {
      expect(() => loadPortfolio(TEST_DIR)).toThrow('Portfolio file not found');
    });

    it('should throw error if portfolio format is invalid', () => {
      writeFileSync(join(TEST_DIR, 'portfolio.json'), '{"invalid": true}');
      expect(() => loadPortfolio(TEST_DIR)).toThrow('Invalid portfolio format');
    });

    it('should throw error if JSON is malformed', () => {
      writeFileSync(join(TEST_DIR, 'portfolio.json'), '{invalid json}');
      expect(() => loadPortfolio(TEST_DIR)).toThrow('Failed to parse portfolio.json');
    });
  });

  describe('parsePortfolio', () => {
    it('should parse portfolio without current prices', () => {
      const portfolio: Portfolio = {
        holdings: [
          {
            symbol: '600036',
            name: '招商银行',
            quantity: 300,
            avg_cost: 37.89,
            market: 'A',
            notes: '',
            added_date: '2026-05-13',
            original_cost: 37.89,
            total_invested: 11367,
            stop_loss: null,
            target_price: null,
            batch_plan: null,
            sector: '银行',
            buy_reason: null,
          },
        ],
        last_updated: '2026-05-14',
      };

      const parsed = parsePortfolio(portfolio);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].symbol).toBe('600036');
      expect(parsed[0].current_return).toBeUndefined();
    });

    it('should calculate current return with prices', () => {
      const portfolio: Portfolio = {
        holdings: [
          {
            symbol: '600036',
            name: '招商银行',
            quantity: 300,
            avg_cost: 37.89,
            market: 'A',
            notes: '',
            added_date: '2026-05-13',
            original_cost: 37.89,
            total_invested: 11367,
            stop_loss: null,
            target_price: null,
            batch_plan: null,
            sector: '银行',
            buy_reason: null,
          },
        ],
        last_updated: '2026-05-14',
      };

      const prices = new Map([['600036', 40.0]]);
      const parsed = parsePortfolio(portfolio, prices);

      expect(parsed[0].current_return).toBeCloseTo(5.57, 1); // (40 - 37.89) / 37.89 * 100
    });

    it('should extract realized return from notes', () => {
      const portfolio: Portfolio = {
        holdings: [
          {
            symbol: '601088',
            name: '中国神华',
            quantity: 400,
            avg_cost: 35.086,
            market: 'A',
            notes: '原1,000股建仓@35.086，5/12卖300股@45.20，5/13卖300股@45.01，剩余400股',
            added_date: '2026-05-13',
            original_cost: 35.086,
            total_invested: 14034.4,
            stop_loss: null,
            target_price: null,
            batch_plan: null,
            sector: '煤炭',
            buy_reason: null,
          },
        ],
        last_updated: '2026-05-14',
      };

      const parsed = parsePortfolio(portfolio);
      expect(parsed[0].realized_return).toBeCloseTo(28.84, 1); // (45.20 - 35.086) / 35.086 * 100
    });
  });

  describe('loadTrades', () => {
    it('should load valid trades data', () => {
      const trades: TradeHistory = {
        trades: [
          {
            date: '2026-05-13',
            action: 'buy',
            symbol: '600036',
            name: '招商银行',
            quantity: 300,
            price: 37.89,
            amount: 11367,
            market: 'A',
            notes: 'Test trade',
            time: '2026-05-13 10:47:47',
          },
        ],
        last_updated: '2026-05-14',
      };

      writeFileSync(
        join(TEST_DIR, 'trades.json'),
        JSON.stringify(trades, null, 2)
      );

      const loaded = loadTrades(TEST_DIR);
      expect(loaded.trades).toHaveLength(1);
      expect(loaded.trades[0].symbol).toBe('600036');
    });

    it('should throw error if trades file not found', () => {
      expect(() => loadTrades(TEST_DIR)).toThrow('Trades file not found');
    });

    it('should throw error if trades format is invalid', () => {
      writeFileSync(join(TEST_DIR, 'trades.json'), '{"invalid": true}');
      expect(() => loadTrades(TEST_DIR)).toThrow('Invalid trades format');
    });
  });

  describe('parseTrades', () => {
    it('should match buy and sell trades', () => {
      const trades: Trade[] = [
        {
          date: '2026-05-12',
          action: 'buy',
          symbol: '600036',
          name: '招商银行',
          quantity: 300,
          price: 37.89,
          amount: 11367,
          market: 'A',
          notes: '',
          time: '2026-05-12 10:00:00',
        },
        {
          date: '2026-05-13',
          action: 'sell',
          symbol: '600036',
          name: '招商银行',
          quantity: 300,
          price: 40.0,
          amount: 12000,
          market: 'A',
          notes: '',
          time: '2026-05-13 15:00:00',
        },
      ];

      const parsed = parseTrades(trades);
      expect(parsed).toHaveLength(2);

      const sellTrade = parsed[1];
      expect(sellTrade.return_rate).toBeCloseTo(5.57, 1);
      expect(sellTrade.outcome).toBe('profit');
      expect(sellTrade.holding_days).toBe(1);
    });

    it('should handle multiple buys and sells (FIFO)', () => {
      const trades: Trade[] = [
        {
          date: '2026-05-10',
          action: 'buy',
          symbol: '600036',
          name: '招商银行',
          quantity: 100,
          price: 35.0,
          amount: 3500,
          market: 'A',
          notes: '',
          time: '2026-05-10 10:00:00',
        },
        {
          date: '2026-05-11',
          action: 'buy',
          symbol: '600036',
          name: '招商银行',
          quantity: 200,
          price: 38.0,
          amount: 7600,
          market: 'A',
          notes: '',
          time: '2026-05-11 10:00:00',
        },
        {
          date: '2026-05-12',
          action: 'sell',
          symbol: '600036',
          name: '招商银行',
          quantity: 150,
          price: 40.0,
          amount: 6000,
          market: 'A',
          notes: '',
          time: '2026-05-12 15:00:00',
        },
      ];

      const parsed = parseTrades(trades);
      const sellTrade = parsed[2];

      // 应该匹配第一笔买入 (35.0)
      expect(sellTrade.return_rate).toBeCloseTo(14.29, 1); // (40 - 35) / 35 * 100
      expect(sellTrade.outcome).toBe('profit');
    });

    it('should handle loss trades', () => {
      const trades: Trade[] = [
        {
          date: '2026-05-12',
          action: 'buy',
          symbol: '600036',
          name: '招商银行',
          quantity: 300,
          price: 40.0,
          amount: 12000,
          market: 'A',
          notes: '',
          time: '2026-05-12 10:00:00',
        },
        {
          date: '2026-05-13',
          action: 'sell',
          symbol: '600036',
          name: '招商银行',
          quantity: 300,
          price: 37.0,
          amount: 11100,
          market: 'A',
          notes: '',
          time: '2026-05-13 15:00:00',
        },
      ];

      const parsed = parseTrades(trades);
      const sellTrade = parsed[1];

      expect(sellTrade.return_rate).toBeCloseTo(-7.5, 1);
      expect(sellTrade.outcome).toBe('loss');
    });

    it('should handle breakeven trades', () => {
      const trades: Trade[] = [
        {
          date: '2026-05-12',
          action: 'buy',
          symbol: '600036',
          name: '招商银行',
          quantity: 300,
          price: 40.0,
          amount: 12000,
          market: 'A',
          notes: '',
          time: '2026-05-12 10:00:00',
        },
        {
          date: '2026-05-13',
          action: 'sell',
          symbol: '600036',
          name: '招商银行',
          quantity: 300,
          price: 40.1,
          amount: 12030,
          market: 'A',
          notes: '',
          time: '2026-05-13 15:00:00',
        },
      ];

      const parsed = parseTrades(trades);
      const sellTrade = parsed[1];

      expect(sellTrade.return_rate).toBeCloseTo(0.25, 1);
      expect(sellTrade.outcome).toBe('breakeven');
    });
  });

  describe('calculateTradeStats', () => {
    it('should calculate correct statistics', () => {
      const trades: Trade[] = [
        {
          date: '2026-05-10',
          action: 'buy',
          symbol: '600036',
          name: '招商银行',
          quantity: 300,
          price: 35.0,
          amount: 10500,
          market: 'A',
          notes: '',
          time: '2026-05-10 10:00:00',
        },
        {
          date: '2026-05-11',
          action: 'sell',
          symbol: '600036',
          name: '招商银行',
          quantity: 300,
          price: 40.0,
          amount: 12000,
          market: 'A',
          notes: '',
          time: '2026-05-11 15:00:00',
        },
        {
          date: '2026-05-12',
          action: 'buy',
          symbol: '601899',
          name: '紫金矿业',
          quantity: 400,
          price: 34.88,
          amount: 13952,
          market: 'A',
          notes: '',
          time: '2026-05-12 10:00:00',
        },
        {
          date: '2026-05-13',
          action: 'sell',
          symbol: '601899',
          name: '紫金矿业',
          quantity: 400,
          price: 32.0,
          amount: 12800,
          market: 'A',
          notes: '',
          time: '2026-05-13 15:00:00',
        },
      ];

      const parsed = parseTrades(trades);
      const stats = calculateTradeStats(parsed);

      expect(stats.total_trades).toBe(4);
      expect(stats.buy_count).toBe(2);
      expect(stats.sell_count).toBe(2);
      expect(stats.profit_count).toBe(1);
      expect(stats.loss_count).toBe(1);
      expect(stats.win_rate).toBeCloseTo(50, 1);
    });
  });

  describe('groupTradesBySymbol', () => {
    it('should group trades by symbol', () => {
      const trades: Trade[] = [
        {
          date: '2026-05-10',
          action: 'buy',
          symbol: '600036',
          name: '招商银行',
          quantity: 300,
          price: 35.0,
          amount: 10500,
          market: 'A',
          notes: '',
          time: '2026-05-10 10:00:00',
        },
        {
          date: '2026-05-12',
          action: 'buy',
          symbol: '601899',
          name: '紫金矿业',
          quantity: 400,
          price: 34.88,
          amount: 13952,
          market: 'A',
          notes: '',
          time: '2026-05-12 10:00:00',
        },
        {
          date: '2026-05-13',
          action: 'sell',
          symbol: '600036',
          name: '招商银行',
          quantity: 300,
          price: 40.0,
          amount: 12000,
          market: 'A',
          notes: '',
          time: '2026-05-13 15:00:00',
        },
      ];

      const parsed = parseTrades(trades);
      const grouped = groupTradesBySymbol(parsed);

      expect(grouped.size).toBe(2);
      expect(grouped.get('600036')).toHaveLength(2);
      expect(grouped.get('601899')).toHaveLength(1);
    });
  });

  describe('loadReviews', () => {
    it('should load review files', () => {
      const reviewsDir = join(TEST_DIR, 'reviews');
      mkdirSync(reviewsDir);

      writeFileSync(
        join(reviewsDir, '2026-05-13.md'),
        '# 每日复盘 2026-05-13\n\n## 持仓复盘（3只）\n\n### 招商银行（600036）\n💡 **操作建议**：继续持有'
      );

      writeFileSync(
        join(reviewsDir, '2026-05-14.md'),
        '# 每日复盘 2026-05-14\n\n## 持仓复盘（2只）'
      );

      const reviews = loadReviews(TEST_DIR);
      expect(reviews).toHaveLength(2);
      expect(reviews[0].date).toBe('2026-05-13');
      expect(reviews[0].holdings_count).toBe(3);
      expect(reviews[1].date).toBe('2026-05-14');
    });

    it('should return empty array if reviews directory not found', () => {
      const reviews = loadReviews(TEST_DIR);
      expect(reviews).toEqual([]);
    });
  });

  describe('extractPatternsFromReviews', () => {
    it('should extract patterns from reviews', () => {
      const reviews = [
        {
          date: '2026-05-13',
          content: `### 招商银行（600036）
- 趋势：MA20(39.32) vs MA60(39.26) → **多头**
- MACD：死叉区域（柱：-0.3609）
- RSI：38.11（正常）
💡 **操作建议**：继续持有`,
          holdings_count: 1,
          suggestions: ['继续持有'],
        },
      ];

      const patterns = extractPatternsFromReviews(reviews);
      expect(patterns).toHaveLength(1);
      expect(patterns[0].symbol).toBe('600036');
      expect(patterns[0].suggestion).toBe('继续持有');
      expect(patterns[0].condition).toContain('趋势');
      expect(patterns[0].condition).toContain('MACD');
    });
  });

  describe('collectAllData', () => {
    it('should collect all data successfully', () => {
      // 准备测试数据
      const portfolio: Portfolio = {
        holdings: [
          {
            symbol: '600036',
            name: '招商银行',
            quantity: 300,
            avg_cost: 37.89,
            market: 'A',
            notes: '',
            added_date: '2026-05-13',
            original_cost: 37.89,
            total_invested: 11367,
            stop_loss: null,
            target_price: null,
            batch_plan: null,
            sector: '银行',
            buy_reason: null,
          },
        ],
        last_updated: '2026-05-14',
      };

      const trades: TradeHistory = {
        trades: [
          {
            date: '2026-05-13',
            action: 'buy',
            symbol: '600036',
            name: '招商银行',
            quantity: 300,
            price: 37.89,
            amount: 11367,
            market: 'A',
            notes: '',
            time: '2026-05-13 10:47:47',
          },
        ],
        last_updated: '2026-05-14',
      };

      writeFileSync(join(TEST_DIR, 'portfolio.json'), JSON.stringify(portfolio, null, 2));
      writeFileSync(join(TEST_DIR, 'trades.json'), JSON.stringify(trades, null, 2));

      const reviewsDir = join(TEST_DIR, 'reviews');
      mkdirSync(reviewsDir);
      writeFileSync(join(reviewsDir, '2026-05-13.md'), '# 每日复盘\n\n## 持仓复盘（1只）');

      const data = collectAllData(TEST_DIR);

      expect(data.portfolio).toHaveLength(1);
      expect(data.trades).toHaveLength(1);
      expect(data.reviews).toHaveLength(1);
      expect(data.tradeStats.total_trades).toBe(1);
      expect(data.collectedAt).toBeDefined();
    });

    it('should throw error if data collection fails', () => {
      expect(() => collectAllData(TEST_DIR)).toThrow('Data collection failed');
    });
  });
});
