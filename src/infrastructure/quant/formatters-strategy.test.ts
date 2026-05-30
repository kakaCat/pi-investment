/**
 * Tests for strategy execution formatters
 */

import { describe, it, expect } from '@jest/globals';
import {
  formatSingleSignal,
  formatBatchSignals,
  formatPipelineResult,
} from './formatters.js';
import type {
  StrategyExecutionSignal,
  BatchExecutionResult,
  PipelineExecutionResult,
} from './types.js';

describe('Strategy Execution Formatters', () => {
  describe('formatSingleSignal', () => {
    it('should format BUY signal with all fields', () => {
      const signal: StrategyExecutionSignal = {
        signal_id: 'sig_123',
        symbol: '600000',
        signal_type: 'BUY',
        confidence: 0.85,
        entry_price: 10.50,
        stop_loss: 9.50,
        target_price: 12.00,
        position_size: 1000,
        indicators: {
          rsi: 35.5,
          macd: 0.15,
        },
      };

      const result = formatSingleSignal(signal);

      expect(result).toContain('600000');
      expect(result).toContain('买入');
      expect(result).toContain('85.00%');
      expect(result).toContain('10.50');
      expect(result).toContain('9.50');
      expect(result).toContain('12.00');
      expect(result).toContain('1,000');
      expect(result).toContain('RSI');
      expect(result).toContain('35.50');
    });

    it('should format SELL signal', () => {
      const signal: StrategyExecutionSignal = {
        symbol: '000001',
        signal_type: 'SELL',
        confidence: 0.75,
        entry_price: 15.20,
      };

      const result = formatSingleSignal(signal);

      expect(result).toContain('000001');
      expect(result).toContain('卖出');
      expect(result).toContain('75.00%');
      expect(result).toContain('15.20');
    });

    it('should format HOLD signal', () => {
      const signal: StrategyExecutionSignal = {
        symbol: '600519',
        signal_type: 'HOLD',
        confidence: 0.60,
        entry_price: 1800.00,
      };

      const result = formatSingleSignal(signal);

      expect(result).toContain('600519');
      expect(result).toContain('持有');
      expect(result).toContain('60.00%');
    });

    it('should handle missing optional fields', () => {
      const signal: StrategyExecutionSignal = {
        symbol: '600000',
        signal_type: 'BUY',
        confidence: 0.80,
        entry_price: 10.00,
      };

      const result = formatSingleSignal(signal);

      expect(result).toContain('600000');
      expect(result).toContain('买入');
      expect(result).not.toContain('止损');
      expect(result).not.toContain('目标价');
      expect(result).not.toContain('建议仓位');
    });
  });

  describe('formatBatchSignals', () => {
    it('should format batch result with signal distribution', () => {
      const result: BatchExecutionResult = {
        signals: [
          {
            symbol: '600000',
            signal_type: 'BUY',
            confidence: 0.85,
            entry_price: 10.50,
          },
          {
            symbol: '000001',
            signal_type: 'SELL',
            confidence: 0.75,
            entry_price: 15.20,
          },
          {
            symbol: '600519',
            signal_type: 'HOLD',
            confidence: 0.60,
            entry_price: 1800.00,
          },
        ],
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          buy: 1,
          sell: 1,
          hold: 1,
          duration_ms: 1500,
        },
        errors: [],
      };

      const formatted = formatBatchSignals(result);

      expect(formatted).toContain('批量执行完成');
      expect(formatted).toContain('总数: 3');
      expect(formatted).toContain('成功: 3');
      expect(formatted).toContain('失败: 0');
      expect(formatted).toContain('买入: 1');
      expect(formatted).toContain('卖出: 1');
      expect(formatted).toContain('持有: 1');
      expect(formatted).toContain('1.50');
      expect(formatted).toContain('600000');
      expect(formatted).toContain('000001');
      expect(formatted).toContain('600519');
    });

    it('should format batch result with errors', () => {
      const result: BatchExecutionResult = {
        signals: [
          {
            symbol: '600000',
            signal_type: 'BUY',
            confidence: 0.85,
            entry_price: 10.50,
          },
        ],
        summary: {
          total: 2,
          success: 1,
          failed: 1,
          buy: 1,
          sell: 0,
          hold: 0,
          duration_ms: 2000,
        },
        errors: [
          {
            symbol: '000001',
            error: 'Insufficient data',
          },
        ],
      };

      const formatted = formatBatchSignals(result);

      expect(formatted).toContain('失败: 1');
      expect(formatted).toContain('000001');
      expect(formatted).toContain('Insufficient data');
    });

    it('should handle empty batch result', () => {
      const result: BatchExecutionResult = {
        signals: [],
        summary: {
          total: 0,
          success: 0,
          failed: 0,
          buy: 0,
          sell: 0,
          hold: 0,
          duration_ms: 100,
        },
        errors: [],
      };

      const formatted = formatBatchSignals(result);

      expect(formatted).toContain('批量执行完成');
      expect(formatted).toContain('总数: 0');
    });
  });

  describe('formatPipelineResult', () => {
    it('should format pipeline result with rejection reasons', () => {
      const result: PipelineExecutionResult = {
        execution_date: '2026-05-30',
        duration_ms: 5000,
        signals_generated: 100,
        signals_approved: 15,
        signals_rejected: 85,
        orders_created: 12,
        rejection_reasons: {
          'low_confidence': 40,
          'risk_limit': 25,
          'duplicate': 20,
        },
        orders: [
          {
            order_id: 'ord_001',
            symbol: '600000',
            side: 'BUY',
            quantity: 1000,
            price: 10.50,
          },
          {
            order_id: 'ord_002',
            symbol: '000001',
            side: 'SELL',
            quantity: 500,
            price: 15.20,
          },
        ],
      };

      const formatted = formatPipelineResult(result);

      expect(formatted).toContain('策略流水线执行完成');
      expect(formatted).toContain('2026-05-30');
      expect(formatted).toContain('5.00');
      expect(formatted).toContain('生成信号: 100');
      expect(formatted).toContain('通过: 15');
      expect(formatted).toContain('拒绝: 85');
      expect(formatted).toContain('创建订单: 12');
      expect(formatted).toContain('low_confidence');
      expect(formatted).toContain('40');
      expect(formatted).toContain('risk_limit');
      expect(formatted).toContain('25');
      expect(formatted).toContain('600000');
      expect(formatted).toContain('000001');
    });

    it('should handle pipeline result without orders', () => {
      const result: PipelineExecutionResult = {
        execution_date: '2026-05-30',
        duration_ms: 3000,
        signals_generated: 50,
        signals_approved: 0,
        signals_rejected: 50,
        orders_created: 0,
        rejection_reasons: {
          'low_confidence': 50,
        },
        orders: [],
      };

      const formatted = formatPipelineResult(result);

      expect(formatted).toContain('策略流水线执行完成');
      expect(formatted).toContain('创建订单: 0');
      expect(formatted).not.toContain('订单列表');
    });

    it('should handle empty rejection reasons', () => {
      const result: PipelineExecutionResult = {
        execution_date: '2026-05-30',
        duration_ms: 1000,
        signals_generated: 10,
        signals_approved: 10,
        signals_rejected: 0,
        orders_created: 10,
        rejection_reasons: {},
        orders: [],
      };

      const formatted = formatPipelineResult(result);

      expect(formatted).toContain('拒绝: 0');
      expect(formatted).not.toContain('拒绝原因分布');
    });
  });
});
