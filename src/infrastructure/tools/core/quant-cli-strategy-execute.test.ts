/**
 * Tests for strategy.execute command in quant_cli tool
 */

import { describe, it, expect, jest, beforeEach } from '@jest/globals';

// Mock must be before imports
const mockRunQuantV2: any = jest.fn();

await jest.unstable_mockModule('../../quant/quant-v2-client.js', () => ({
  runQuantV2: mockRunQuantV2,
  V2_COMMAND_LIST: [],
}));

const { quantCliTool } = await import('./quant-cli-tool.js');

// Helper to call execute with proper signature
async function executeCommand(params: any) {
  return quantCliTool.execute('test-call-id', params, undefined, undefined, {} as any);
}

describe('quant_cli tool - strategy.execute command', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('single mode execution', () => {
    it('should execute single strategy and format result', async () => {
      const mockSignal = {
        symbol: '600000',
        signal_type: 'BUY',
        confidence: 0.85,
        entry_price: 10.50,
        stop_loss: 9.50,
        target_price: 12.00,
        position_size: 1000,
      };

      mockRunQuantV2.mockResolvedValue(mockSignal as any);

      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'single',
          symbol: '600000',
          strategy: 'rsi-strategy',
        },
      });

      expect(mockRunQuantV2).toHaveBeenCalledWith('strategy.execute', {
        action: 'single',
        symbol: '600000',
        strategy: 'rsi-strategy',
      });

      expect(result.content[0].type).toBe('text');
      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('600000');
        expect((result.content[0] as any).text).toContain('买入');
        expect((result.content[0] as any).text).toContain('85.00%');
      }
      expect(result.details).toEqual(mockSignal);
    });

    it('should validate required symbol parameter', async () => {
      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'single',
          strategy: 'rsi-strategy',
        },
      });

      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('缺少必填参数: symbol');
      }
      expect(mockRunQuantV2).not.toHaveBeenCalled();
    });

    it('should validate required strategy parameter', async () => {
      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'single',
          symbol: '600000',
        },
      });

      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('缺少必填参数: strategy');
      }
      expect(mockRunQuantV2).not.toHaveBeenCalled();
    });
  });

  describe('batch mode execution', () => {
    it('should execute batch strategy and format result', async () => {
      const mockBatchResult = {
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
        ],
        summary: {
          total: 2,
          success: 2,
          failed: 0,
          buy: 1,
          sell: 1,
          hold: 0,
          duration_ms: 1500,
        },
        errors: [],
      };

      mockRunQuantV2.mockResolvedValue(mockBatchResult as any);

      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'batch',
          symbols: ['600000', '000001'],
          strategy: 'rsi-strategy',
        },
      });

      expect(mockRunQuantV2).toHaveBeenCalledWith('strategy.execute', {
        action: 'batch',
        symbols: ['600000', '000001'],
        strategy: 'rsi-strategy',
      });

      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('批量执行完成');
        expect((result.content[0] as any).text).toContain('总数: 2');
        expect((result.content[0] as any).text).toContain('买入: 1');
        expect((result.content[0] as any).text).toContain('卖出: 1');
      }
      expect(result.details).toEqual(mockBatchResult);
    });

    it('should validate required symbols parameter', async () => {
      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'batch',
          strategy: 'rsi-strategy',
        },
      });

      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('缺少必填参数: symbols');
      }
      expect(mockRunQuantV2).not.toHaveBeenCalled();
    });
  });

  describe('pipeline mode execution', () => {
    it('should execute pipeline strategy and format result', async () => {
      const mockPipelineResult = {
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
        ],
      };

      mockRunQuantV2.mockResolvedValue(mockPipelineResult as any);

      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'pipeline',
          strategy: 'rsi-strategy',
        },
      });

      expect(mockRunQuantV2).toHaveBeenCalledWith('strategy.execute', {
        action: 'pipeline',
        strategy: 'rsi-strategy',
      });

      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('策略流水线执行完成');
        expect((result.content[0] as any).text).toContain('生成信号: 100');
        expect((result.content[0] as any).text).toContain('通过: 15');
        expect((result.content[0] as any).text).toContain('拒绝: 85');
        expect((result.content[0] as any).text).toContain('low_confidence');
      }
      expect(result.details).toEqual(mockPipelineResult);
    });
  });

  describe('action parameter validation', () => {
    it('should reject invalid action parameter', async () => {
      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'invalid',
          strategy: 'rsi-strategy',
        },
      });

      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('action 只能是 single 或 batch 或 pipeline');
      }
      expect(mockRunQuantV2).not.toHaveBeenCalled();
    });

    it('should require action parameter', async () => {
      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          strategy: 'rsi-strategy',
        },
      });

      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('缺少必填参数: action');
      }
      expect(mockRunQuantV2).not.toHaveBeenCalled();
    });
  });

  describe('symbol/symbols parameter validation', () => {
    it('should require symbol for single mode', async () => {
      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'single',
          strategy: 'rsi-strategy',
        },
      });

      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('缺少必填参数: symbol');
      }
      expect(mockRunQuantV2).not.toHaveBeenCalled();
    });

    it('should require symbols for batch mode', async () => {
      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'batch',
          strategy: 'rsi-strategy',
        },
      });

      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('缺少必填参数: symbols');
      }
      expect(mockRunQuantV2).not.toHaveBeenCalled();
    });

    it('should not require symbol/symbols for pipeline mode', async () => {
      const mockPipelineResult = {
        execution_date: '2026-05-30',
        duration_ms: 1000,
        signals_generated: 10,
        signals_approved: 5,
        signals_rejected: 5,
        orders_created: 5,
        rejection_reasons: {},
        orders: [],
      };

      mockRunQuantV2.mockResolvedValue(mockPipelineResult as any);

      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'pipeline',
          strategy: 'rsi-strategy',
        },
      });

      expect(mockRunQuantV2).toHaveBeenCalled();
      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('策略流水线执行完成');
      }
    });
  });

  describe('error handling', () => {
    it('should handle client errors gracefully', async () => {
      mockRunQuantV2.mockRejectedValue(
        new Error('API connection failed')
      );

      const result = await executeCommand({
        command: 'strategy.execute',
        params: {
          action: 'single',
          symbol: '600000',
          strategy: 'rsi-strategy',
        },
      });

      if (result.content[0].type === 'text') {
        expect((result.content[0] as any).text).toContain('量化 CLI 调用失败');
        expect((result.content[0] as any).text).toContain('API connection failed');
      }
    });
  });
});
