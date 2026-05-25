/**
 * Factor Calculate Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { getResponseText } from '../test-utils.js';

const mockCallQuantSysDaemon = jest.fn<(func: string, args?: Record<string, unknown>) => Promise<string>>();

jest.unstable_mockModule('../../quant/quantsys-daemon-adapter.js', () => ({
  callQuantSysDaemon: mockCallQuantSysDaemon
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

  describe('Default behavior (technical + valuation + quality)', () => {
    it('should calculate default factors successfully', async () => {
      const mockTechnical = JSON.stringify({
        symbol: '600519',
        ma5: 1800,
        ma10: 1790,
        macd: { dif: 5.2, dea: 3.1, macd: 2.1 },
        rsi: 65.5,
        bollinger: { upper: 1850, middle: 1800, lower: 1750 }
      });

      const mockValuation = JSON.stringify({
        symbol: '600519',
        pe: 35.2,
        pb: 8.5,
        graham_value: 1650
      });

      const mockQuality = JSON.stringify({
        symbol: '600519',
        score: 85,
        framework: 'auto'
      });

      mockCallQuantSysDaemon
        .mockResolvedValueOnce(mockTechnical)
        .mockResolvedValueOnce(mockValuation)
        .mockResolvedValueOnce(mockQuality);

      const result = await (factorCalculateTool.execute as any)('test-call-id', { symbol: '600519' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(3);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('calculate_technical_indicators', { symbol: '600519' });
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_stock_valuation', { symbol: '600519' });
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_quality_score', { symbol: '600519', framework: 'auto' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(true);
      expect(response.symbol).toBe('600519');
      expect(response.factors.technical).toBeDefined();
      expect(response.factors.valuation).toBeDefined();
      expect(response.factors.quality).toBeDefined();
      expect(response.factors.technical.ma5).toBe(1800);
      expect(response.factors.valuation.pe).toBe(35.2);
      expect(response.factors.quality.score).toBe(85);
    });
  });

  describe('Single factor queries', () => {
    it('should calculate only technical factor', async () => {
      const mockTechnical = JSON.stringify({
        symbol: '600519',
        ma5: 1800,
        rsi: 65.5
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockTechnical);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519',
        factors: ['technical']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(1);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('calculate_technical_indicators', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(true);
      expect(response.factors.technical).toBeDefined();
      expect(response.factors.valuation).toBeUndefined();
      expect(response.factors.quality).toBeUndefined();
    });

    it('should calculate only pe_percentile factor', async () => {
      const mockPePercentile = JSON.stringify({
        symbol: '600519',
        current_pe: 35.2,
        percentile: 68.5,
        years: 3
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPePercentile);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519',
        factors: ['pe_percentile']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(1);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_pe_percentile', { symbol: '600519', years: 3 });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(true);
      expect(response.factors.pe_percentile).toBeDefined();
      expect(response.factors.pe_percentile.percentile).toBe(68.5);
    });

    it('should calculate only price_action factor', async () => {
      const mockPriceAction = JSON.stringify({
        symbol: '600519',
        trend: 'uptrend',
        strength: 0.75,
        period: 60
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPriceAction);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519',
        factors: ['price_action']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(1);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('analyze_price_action', { symbol: '600519', period: 60 });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(true);
      expect(response.factors.price_action).toBeDefined();
      expect(response.factors.price_action.trend).toBe('uptrend');
    });
  });

  describe('Multiple factor combinations', () => {
    it('should calculate technical + pe_percentile', async () => {
      const mockTechnical = JSON.stringify({ symbol: '600519', rsi: 65.5 });
      const mockPePercentile = JSON.stringify({ symbol: '600519', percentile: 68.5 });

      mockCallQuantSysDaemon
        .mockResolvedValueOnce(mockTechnical)
        .mockResolvedValueOnce(mockPePercentile);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519',
        factors: ['technical', 'pe_percentile']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(2);

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(true);
      expect(response.factors.technical).toBeDefined();
      expect(response.factors.pe_percentile).toBeDefined();
    });

    it('should calculate all five factors', async () => {
      const mockTechnical = JSON.stringify({ symbol: '600519', rsi: 65.5 });
      const mockValuation = JSON.stringify({ symbol: '600519', pe: 35.2 });
      const mockQuality = JSON.stringify({ symbol: '600519', score: 85 });
      const mockPePercentile = JSON.stringify({ symbol: '600519', percentile: 68.5 });
      const mockPriceAction = JSON.stringify({ symbol: '600519', trend: 'uptrend' });

      mockCallQuantSysDaemon
        .mockResolvedValueOnce(mockTechnical)
        .mockResolvedValueOnce(mockValuation)
        .mockResolvedValueOnce(mockQuality)
        .mockResolvedValueOnce(mockPePercentile)
        .mockResolvedValueOnce(mockPriceAction);

      const result = await (factorCalculateTool.execute as any)('test-call-id', {
        symbol: '600519',
        factors: ['technical', 'valuation', 'quality', 'pe_percentile', 'price_action']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(5);

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(true);
      expect(response.factors.technical).toBeDefined();
      expect(response.factors.valuation).toBeDefined();
      expect(response.factors.quality).toBeDefined();
      expect(response.factors.pe_percentile).toBeDefined();
      expect(response.factors.price_action).toBeDefined();
    });
  });

  describe('Error handling', () => {
    it('should reject invalid stock code', async () => {
      const result = await (factorCalculateTool.execute as any)('test-call-id', { symbol: 'AAPL' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('不支持的股票代码');
      expect(response.invalid_format).toBe(true);
    });

    it('should reject HK stock code', async () => {
      const result = await (factorCalculateTool.execute as any)('test-call-id', { symbol: '9988.HK' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('暂不支持港股');
      expect(response.unsupported_for_hk).toBe(true);
    });

    it('should handle partial failure (one factor fails)', async () => {
      const mockTechnical = JSON.stringify({ symbol: '600519', rsi: 65.5 });
      const mockValuation = JSON.stringify({ symbol: '600519', pe: 35.2 });

      mockCallQuantSysDaemon
        .mockResolvedValueOnce(mockTechnical)
        .mockResolvedValueOnce(mockValuation)
        .mockRejectedValueOnce(new Error('Quality score calculation failed'));

      const result = await (factorCalculateTool.execute as any)('test-call-id', { symbol: '600519' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(3);

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(true); // Still success because 2 out of 3 succeeded
      expect(response.factors.technical).toBeDefined();
      expect(response.factors.valuation).toBeDefined();
      expect(response.factors.quality).toBeNull();
      expect(response.factors.quality_error).toBeDefined();
      expect(response.factors.quality_error).toContain('Quality score calculation failed');
    });

    it('should handle all factors failing', async () => {
      mockCallQuantSysDaemon
        .mockRejectedValueOnce(new Error('Technical failed'))
        .mockRejectedValueOnce(new Error('Valuation failed'))
        .mockRejectedValueOnce(new Error('Quality failed'));

      const result = await (factorCalculateTool.execute as any)('test-call-id', { symbol: '600519' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(3);

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBe('所有因子计算失败');
    });

    it('should handle daemon network timeout', async () => {
      mockCallQuantSysDaemon
        .mockRejectedValueOnce(new Error('Network timeout'))
        .mockRejectedValueOnce(new Error('Network timeout'))
        .mockRejectedValueOnce(new Error('Network timeout'));

      const result = await (factorCalculateTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBe('所有因子计算失败');
    });
  });
});
