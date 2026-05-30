/**
 * Type validation tests for strategy execution types
 */

import { describe, test, expect } from '@jest/globals';
import type {
  StrategyExecuteParams,
  StrategyBatchExecuteParams,
  StrategyExecutionSignal,
} from './types.js';

describe('Strategy Execution Types', () => {
  test('StrategyExecuteParams should have required fields', () => {
    const params: StrategyExecuteParams = {
      symbol: '600519.SH',
      strategy_name: 'VolatilityBreakout',
    };

    expect(params.symbol).toBe('600519.SH');
    expect(params.strategy_name).toBe('VolatilityBreakout');

    // Test optional fields
    const paramsWithOptional: StrategyExecuteParams = {
      symbol: '600519.SH',
      strategy_name: 'VolatilityBreakout',
      date: '2026-05-30',
      persist: true,
      return_details: true,
    };

    expect(paramsWithOptional.date).toBe('2026-05-30');
    expect(paramsWithOptional.persist).toBe(true);
    expect(paramsWithOptional.return_details).toBe(true);
  });

  test('StrategyBatchExecuteParams should accept symbols array', () => {
    const params: StrategyBatchExecuteParams = {
      symbols: ['600519.SH', '000858.SZ'],
      strategy_name: 'VolatilityBreakout',
    };

    expect(params.symbols).toHaveLength(2);
    expect(params.strategy_name).toBe('VolatilityBreakout');

    // Test optional fields
    const paramsWithOptional: StrategyBatchExecuteParams = {
      symbols: ['600519.SH'],
      strategy_name: 'VolatilityBreakout',
      date: '2026-05-30',
      persist: false,
      min_confidence: 0.7,
    };

    expect(paramsWithOptional.min_confidence).toBe(0.7);
  });

  test('StrategySignal should have signal_type union', () => {
    const buySignal: StrategyExecutionSignal = {
      symbol: '600519.SH',
      signal_type: 'BUY',
      confidence: 0.85,
      entry_price: 100.5,
    };

    expect(buySignal.signal_type).toBe('BUY');

    const sellSignal: StrategyExecutionSignal = {
      symbol: '600519.SH',
      signal_type: 'SELL',
      confidence: 0.75,
      entry_price: 105.0,
    };

    expect(sellSignal.signal_type).toBe('SELL');

    const holdSignal: StrategyExecutionSignal = {
      symbol: '600519.SH',
      signal_type: 'HOLD',
      confidence: 0.5,
      entry_price: 102.0,
    };

    expect(holdSignal.signal_type).toBe('HOLD');

    // Test optional fields
    const signalWithOptional: StrategyExecutionSignal = {
      signal_id: 'sig_123',
      symbol: '600519.SH',
      signal_type: 'BUY',
      confidence: 0.85,
      entry_price: 100.5,
      stop_loss: 95.0,
      target_price: 110.0,
      position_size: 1000,
      indicators: { rsi: 30, macd: 0.5 },
    };

    expect(signalWithOptional.signal_id).toBe('sig_123');
    expect(signalWithOptional.stop_loss).toBe(95.0);
    expect(signalWithOptional.indicators?.rsi).toBe(30);
  });
});
