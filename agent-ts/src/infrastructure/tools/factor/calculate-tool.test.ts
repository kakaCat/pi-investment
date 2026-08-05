/**
 * Factor Calculate Tool Tests (V2)
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { getResponseText } from '../testing-utils.js';

// Mock the v2 client
const mockComputeFactors = jest.fn<typeof import('../../adapters/quant/quant-v2-client.js').computeFactors>();

jest.unstable_mockModule('../../adapters/quant/quant-v2-client.js', () => ({
  computeFactors: mockComputeFactors
}));

const { factorCalculateTool } = await import('./calculate-tool.js');

describe('factor_calculate tool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tool Definition', () => {
    it('should have correct name and label', () => {
      expect(factorCalculateTool.name).toBe('factor_calculate');
      expect(factorCalculateTool.label).toBe('计算因子');
    });

    it('should have description', () => {
      expect(factorCalculateTool.description).toBeDefined();
      expect(factorCalculateTool.description.length).toBeGreaterThan(0);
    });

    it('should have execute function', () => {
      expect(factorCalculateTool.execute).toBeDefined();
      expect(typeof factorCalculateTool.execute).toBe('function');
    });
  });

  describe('Successful factor calculation', () => {
    it('should calculate factors successfully', async () => {
      const mockResult = {
        success: true,
        results: [{
          symbol: '600519',
          date: '2024-06-03',
          factor_count: 15,
          factors: {
            rsi14: 65.5,
            macd: 5.2,
            macd_signal: 3.1,
            macd_histogram: 2.1,
            ma5: 1800,
            ma10: 1790,
            ma20: 1780,
            bollinger_upper: 1850,
            bollinger_middle: 1800,
            bollinger_lower: 1750,
            atr14: 25.5,
            volume_ratio: 1.2,
            turnover_rate: 2.5
          }
        }],
        count: 1
      };

      mockComputeFactors.mockResolvedValueOnce(mockResult);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519'
      });

      expect(mockComputeFactors).toHaveBeenCalledTimes(1);
      expect(mockComputeFactors).toHaveBeenCalledWith({
        symbols: ['600519'],
        factors: undefined
      });

      const text = getResponseText(result);
      expect(text).toContain('600519');
      expect(text).toContain('因子数量: 15');
      expect(text).toContain('RSI(14)');
      expect(text).toContain('65.50');
    });

    it('should calculate specific factors', async () => {
      const mockResult = {
        success: true,
        results: [{
          symbol: '600519',
          date: '2024-06-03',
          factor_count: 3,
          factors: {
            rsi14: 65.5,
            macd: 5.2,
            macd_signal: 3.1
          }
        }],
        count: 1
      };

      mockComputeFactors.mockResolvedValueOnce(mockResult);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519',
        factors: ['rsi14', 'macd', 'macd_signal']
      });

      expect(mockComputeFactors).toHaveBeenCalledWith({
        symbols: ['600519'],
        factors: ['rsi14', 'macd', 'macd_signal']
      });

      const text = getResponseText(result);
      expect(text).toContain('因子数量: 3');
    });
  });

  describe('Error handling', () => {
    it('should reject invalid stock code', async () => {
      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: 'AAPL'
      });

      expect(mockComputeFactors).not.toHaveBeenCalled();

      const text = getResponseText(result);
      expect(text).toContain('不支持的股票代码');
    });

    it('should reject HK stock code', async () => {
      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '9988.HK'
      });

      expect(mockComputeFactors).not.toHaveBeenCalled();

      const text = getResponseText(result);
      expect(text).toContain('暂不支持港股');
    });

    it('should handle API error with error in result item', async () => {
      const mockResult = {
        success: true,  // success can still be true even with item errors
        results: [{
          symbol: '600519',
          date: '',
          factor_count: 0,
          factors: {},
          error: 'No kline data'
        }],
        count: 1
      };

      mockComputeFactors.mockResolvedValueOnce(mockResult);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519'
      });

      const text = getResponseText(result);
      expect(text).toContain('600519');
      expect(text).toContain('错误: No kline data');
    });

    it('should handle complete API failure', async () => {
      const mockResult = {
        success: false,
        results: [],
        count: 0
      };

      mockComputeFactors.mockResolvedValueOnce(mockResult);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519'
      });

      const text = getResponseText(result);
      expect(text).toContain('因子计算失败或无结果');
    });

    it('should handle network timeout', async () => {
      mockComputeFactors.mockRejectedValueOnce(new Error('Network timeout'));

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519'
      });

      const text = getResponseText(result);
      // 统一错误契约：createErrorResponse 输出 "执行失败: <原因>"
      expect(text).toContain('执行失败');
      expect(text).toContain('Network timeout');
    });

    it('should handle empty results array', async () => {
      const mockResult = {
        success: true,
        results: [],
        count: 0
      };

      mockComputeFactors.mockResolvedValueOnce(mockResult);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519'
      });

      const text = getResponseText(result);
      expect(text).toContain('因子计算失败或无结果');
    });
  });

  describe('Factor result formatting', () => {
    it('should format technical factors correctly', async () => {
      const mockResult = {
        success: true,
        results: [{
          symbol: '600519',
          date: '2024-06-03',
          factor_count: 5,
          factors: {
            rsi14: 65.5,
            macd: 5.2345,
            macd_signal: 3.1234,
            macd_histogram: 2.1111,
            ma5: 1800.25
          }
        }],
        count: 1
      };

      mockComputeFactors.mockResolvedValueOnce(mockResult);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519'
      });

      const text = getResponseText(result);

      // Check number formatting
      expect(text).toContain('RSI(14)');
      expect(text).toContain('MACD');
      expect(text).toContain('MA5');
    });
  });
});
