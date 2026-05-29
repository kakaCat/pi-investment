/**
 * Data Fetch Kline Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { getResponseText } from '../test-utils.js';
import type { KlineData } from '../../quant/types.js';

const mockGetKlineHistory = jest.fn<(symbol: string, period?: string, startDate?: string, endDate?: string, limit?: number) => Promise<KlineData>>();

jest.unstable_mockModule('../../quant/quant-v2-client.js', () => ({
  getKlineHistory: mockGetKlineHistory
}));

const { dataFetchKlineTool } = await import('./fetch-kline-tool.js');

describe('data_fetch_kline tool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tool Definition', () => {
    it('should have correct name and label', () => {
      expect(dataFetchKlineTool.name).toBe('data_fetch_kline');
      expect(dataFetchKlineTool.label).toBe('获取历史K线');
    });

    it('should have description', () => {
      expect(dataFetchKlineTool.description).toBeDefined();
      expect(dataFetchKlineTool.description.length).toBeGreaterThan(0);
    });

    it('should have execute function', () => {
      expect(dataFetchKlineTool.execute).toBeDefined();
      expect(typeof dataFetchKlineTool.execute).toBe('function');
    });
  });

  describe('Default behavior (daily period)', () => {
    it('should fetch daily kline data with default parameters', async () => {
      const mockKlineResponse: KlineData = {
        success: true,
        symbol: '600519',
        period: 'daily',
        count: 2,
        data: [
          { date: '2026-05-20', open: 1800, high: 1820, low: 1790, close: 1810, volume: 1500000, change_pct: 1.2 },
          { date: '2026-05-21', open: 1810, high: 1830, low: 1800, close: 1825, volume: 1600000, change_pct: 0.8 }
        ]
      };

      mockGetKlineHistory.mockResolvedValueOnce(mockKlineResponse);

      const result = await (dataFetchKlineTool.execute as any)('test-call-id', { symbol: '600519' });

      expect(mockGetKlineHistory).toHaveBeenCalledTimes(1);
      expect(mockGetKlineHistory).toHaveBeenCalledWith('600519', 'daily', undefined, undefined, undefined);

      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');

      const response = JSON.parse(getResponseText(result));
      expect(response.symbol).toBe('600519');
      expect(response.data).toHaveLength(2);
    });
  });

  describe('Custom parameters', () => {
    it('should fetch weekly kline data', async () => {
      const mockKlineResponse: KlineData = {
        success: true,
        symbol: '600519',
        period: 'weekly',
        count: 0,
        data: []
      };

      mockGetKlineHistory.mockResolvedValueOnce(mockKlineResponse);

      const result = await (dataFetchKlineTool.execute as any)('test-call-id', {
        symbol: '600519',
        period: 'weekly'
      });

      expect(mockGetKlineHistory).toHaveBeenCalledWith('600519', 'weekly', undefined, undefined, undefined);

      const response = JSON.parse(getResponseText(result));
      expect(response.period).toBe('weekly');
    });

    it('should fetch monthly kline data', async () => {
      const mockKlineResponse: KlineData = {
        success: true,
        symbol: '600519',
        period: 'monthly',
        count: 0,
        data: []
      };

      mockGetKlineHistory.mockResolvedValueOnce(mockKlineResponse);

      const result = await (dataFetchKlineTool.execute as any)('test-call-id', {
        symbol: '600519',
        period: 'monthly'
      });

      expect(mockGetKlineHistory).toHaveBeenCalledWith('600519', 'monthly', undefined, undefined, undefined);

      const response = JSON.parse(getResponseText(result));
      expect(response.period).toBe('monthly');
    });

    it('should fetch kline data with custom date range', async () => {
      const mockKlineResponse: KlineData = {
        success: true,
        symbol: '600519',
        period: 'daily',
        count: 0,
        data: []
      };

      mockGetKlineHistory.mockResolvedValueOnce(mockKlineResponse);

      const result = await (dataFetchKlineTool.execute as any)('test-call-id', {
        symbol: '600519',
        start_date: '20260101',
        end_date: '20260520'
      });

      expect(mockGetKlineHistory).toHaveBeenCalledWith('600519', 'daily', '20260101', '20260520', undefined);
    });

    it('should fetch kline data with all custom parameters', async () => {
      const mockKlineResponse: KlineData = {
        success: true,
        symbol: '600519',
        period: 'weekly',
        count: 0,
        data: []
      };

      mockGetKlineHistory.mockResolvedValueOnce(mockKlineResponse);

      const result = await (dataFetchKlineTool.execute as any)('test-call-id', {
        symbol: '600519',
        period: 'weekly',
        start_date: '20260101',
        end_date: '20260520'
      });

      expect(mockGetKlineHistory).toHaveBeenCalledWith('600519', 'weekly', '20260101', '20260520', undefined);
    });
  });

  describe('HK stock support', () => {
    it('should support HK stock with .HK suffix', async () => {
      const mockKlineResponse: KlineData = {
        success: true,
        symbol: '9988.HK',
        period: 'daily',
        count: 0,
        data: []
      };

      mockGetKlineHistory.mockResolvedValueOnce(mockKlineResponse);

      const result = await (dataFetchKlineTool.execute as any)('test-call-id', { symbol: '9988.HK' });

      expect(mockGetKlineHistory).toHaveBeenCalledWith('9988.HK', 'daily', undefined, undefined, undefined);

      const response = JSON.parse(getResponseText(result));
      expect(response.symbol).toBe('9988.HK');
    });

    it('should support HK stock without suffix', async () => {
      const mockKlineResponse: KlineData = {
        success: true,
        symbol: '9988',
        period: 'daily',
        count: 0,
        data: []
      };

      mockGetKlineHistory.mockResolvedValueOnce(mockKlineResponse);

      const result = await (dataFetchKlineTool.execute as any)('test-call-id', { symbol: '9988' });

      expect(mockGetKlineHistory).toHaveBeenCalledWith('9988', 'daily', undefined, undefined, undefined);
    });
  });

  describe('Error handling', () => {
    it('should reject invalid stock code', async () => {
      const result = await (dataFetchKlineTool.execute as any)('test-call-id', { symbol: 'AAPL' });

      expect(mockGetKlineHistory).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('不支持的股票代码');
      expect(response.invalid_format).toBe(true);
    });

    it('should handle daemon errors gracefully', async () => {
      mockGetKlineHistory.mockRejectedValueOnce(new Error('Network timeout'));

      const result = await (dataFetchKlineTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('获取K线数据失败');
      expect(response.error).toContain('Network timeout');
    });

    it('should handle US stock code rejection', async () => {
      const result = await (dataFetchKlineTool.execute as any)('test-call-id', { symbol: 'TSLA.US' });

      expect(mockGetKlineHistory).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('不支持的股票代码');
      expect(response.invalid_format).toBe(true);
    });

    it('should handle empty symbol', async () => {
      const result = await (dataFetchKlineTool.execute as any)('test-call-id', { symbol: '' });

      expect(mockGetKlineHistory).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
    });
  });
});
