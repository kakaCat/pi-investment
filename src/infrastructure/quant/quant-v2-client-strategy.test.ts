/**
 * QuantV2Client 策略执行方法测试
 *
 * 测试 executeStrategy, batchExecuteStrategy, pipelineExecuteStrategy 三个方法
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import type {
  StrategyExecuteParams,
  StrategyBatchExecuteParams,
  StrategyPipelineExecuteParams,
  StrategyExecutionSignal,
  BatchExecutionResult,
  PipelineExecutionResult,
} from './types.js';

// Mock global fetch
const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockFetch;

// Import after mocking
import { executeStrategy, batchExecuteStrategy, pipelineExecuteStrategy } from './quant-v2-client.js';

describe('QuantV2Client Strategy Methods', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // ─── Task 7: executeStrategy ───────────────────────────────

  describe('executeStrategy', () => {
    it('should call correct endpoint with valid params', async () => {
      const params: StrategyExecuteParams = {
        symbol: '600519.SH',
        strategy_name: 'VolatilityBreakout',
        date: '2026-05-30',
      };

      const mockSignal: StrategyExecutionSignal = {
        signal_id: 'sig_123',
        symbol: '600519.SH',
        signal_type: 'BUY',
        confidence: 0.85,
        entry_price: 1800.0,
        stop_loss: 1750.0,
        target_price: 1900.0,
        position_size: 100,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          data: mockSignal,
        }),
      } as Response);

      const result = await executeStrategy(params);

      expect(mockFetch).toHaveBeenCalledWith(
        'http://127.0.0.1:5001/api/strategies/execute',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params),
        })
      );

      expect(result).toEqual(mockSignal);
    });

    it('should throw QuantV2Error on API error', async () => {
      const params: StrategyExecuteParams = {
        symbol: '600519.SH',
        strategy_name: 'InvalidStrategy',
      };

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => 'Strategy not found',
      } as Response);

      await expect(executeStrategy(params)).rejects.toThrow('HTTP 404: Strategy not found');
    });

    it('should throw QuantV2Error when success is false', async () => {
      const params: StrategyExecuteParams = {
        symbol: '600519.SH',
        strategy_name: 'VolatilityBreakout',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: false,
          error: 'Insufficient data',
        }),
      } as Response);

      await expect(executeStrategy(params)).rejects.toThrow('Insufficient data');
    });
  });

  // ─── Task 8: batchExecuteStrategy ──────────────────────────

  describe('batchExecuteStrategy', () => {
    it('should parse NDJSON stream correctly', async () => {
      const params: StrategyBatchExecuteParams = {
        symbols: ['600519.SH', '000001.SZ'],
        strategy_name: 'VolatilityBreakout',
        min_confidence: 0.7,
      };

      const ndjsonResponse = [
        '{"type":"signal","data":{"symbol":"600519.SH","signal_type":"BUY","confidence":0.85,"entry_price":1800.0}}',
        '{"type":"signal","data":{"symbol":"000001.SZ","signal_type":"HOLD","confidence":0.6,"entry_price":15.0}}',
        '{"type":"error","symbol":"600000.SH","error":"Insufficient data"}',
        '{"type":"summary","total":3,"success":2,"failed":1,"buy":1,"sell":0,"hold":1,"duration_ms":1500}',
      ].join('\n');

      mockFetch.mockResolvedValueOnce({
        ok: true,
        text: async () => ndjsonResponse,
      } as Response);

      const result = await batchExecuteStrategy(params);

      expect(mockFetch).toHaveBeenCalledWith(
        'http://127.0.0.1:5001/api/strategies/batch-execute',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params),
        })
      );

      expect(result.signals).toHaveLength(2);
      expect(result.signals[0].symbol).toBe('600519.SH');
      expect(result.signals[0].signal_type).toBe('BUY');
      expect(result.errors).toHaveLength(1);
      expect(result.errors[0].symbol).toBe('600000.SH');
      expect(result.summary.total).toBe(3);
      expect(result.summary.success).toBe(2);
      expect(result.summary.buy).toBe(1);
    });

    it('should handle errors in NDJSON stream', async () => {
      const params: StrategyBatchExecuteParams = {
        symbols: ['600519.SH'],
        strategy_name: 'VolatilityBreakout',
      };

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: async () => 'Server error',
      } as Response);

      await expect(batchExecuteStrategy(params)).rejects.toThrow('HTTP 500: Server error');
    });

    it('should handle malformed NDJSON gracefully', async () => {
      const params: StrategyBatchExecuteParams = {
        symbols: ['600519.SH'],
        strategy_name: 'VolatilityBreakout',
      };

      const ndjsonResponse = [
        '{"type":"signal","data":{"symbol":"600519.SH","signal_type":"BUY","confidence":0.85}}',
        'invalid json line',
        '{"type":"summary","total":1,"success":1,"failed":0,"buy":1,"sell":0,"hold":0,"duration_ms":500}',
      ].join('\n');

      mockFetch.mockResolvedValueOnce({
        ok: true,
        text: async () => ndjsonResponse,
      } as Response);

      const result = await batchExecuteStrategy(params);

      // Should skip invalid line and continue
      expect(result.signals).toHaveLength(1);
      expect(result.summary.total).toBe(1);
    });
  });

  // ─── Task 9: pipelineExecuteStrategy ───────────────────────

  describe('pipelineExecuteStrategy', () => {
    it('should return execution result', async () => {
      const params: StrategyPipelineExecuteParams = {
        symbols: ['600519.SH', '000001.SZ'],
        strategy_name: 'VolatilityBreakout',
        create_orders: true,
        risk_check: true,
      };

      const mockResult: PipelineExecutionResult = {
        execution_date: '2026-05-30',
        duration_ms: 2500,
        signals_generated: 10,
        signals_approved: 7,
        signals_rejected: 3,
        orders_created: 5,
        rejection_reasons: {
          'risk_too_high': 2,
          'insufficient_liquidity': 1,
        },
        orders: [
          {
            order_id: 'ord_123',
            symbol: '600519.SH',
            side: 'BUY',
            quantity: 100,
            price: 1800.0,
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          data: mockResult,
        }),
      } as Response);

      const result = await pipelineExecuteStrategy(params);

      expect(mockFetch).toHaveBeenCalledWith(
        'http://127.0.0.1:5001/api/strategies/pipeline-execute',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params),
        })
      );

      expect(result).toEqual(mockResult);
      expect(result.signals_generated).toBe(10);
      expect(result.orders_created).toBe(5);
      expect(result.orders).toHaveLength(1);
    });

    it('should throw QuantV2Error on API error', async () => {
      const params: StrategyPipelineExecuteParams = {
        symbols: ['600519.SH'],
        strategy_name: 'VolatilityBreakout',
      };

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        text: async () => 'Invalid parameters',
      } as Response);

      await expect(pipelineExecuteStrategy(params)).rejects.toThrow('HTTP 400: Invalid parameters');
    });
  });
});
