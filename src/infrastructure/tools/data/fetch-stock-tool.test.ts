/**
 * Data Fetch Stock Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';

const mockGetStockData = jest.fn<(symbol: string, fields?: Array<'info' | 'price' | 'news' | 'announcements'>, newsNum?: number) => Promise<any>>();

jest.unstable_mockModule('../../quant/quant-v2-client.js', () => ({
  getStockData: mockGetStockData
}));

const { dataFetchStockTool } = await import('./fetch-stock-tool.js');

// Helper to extract text from tool result
function getResponseText(result: any): string {
  return result.content[0].text;
}

describe('data_fetch_stock tool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tool Definition', () => {
    it('should have correct name and label', () => {
      expect(dataFetchStockTool.name).toBe('data_fetch_stock');
      expect(dataFetchStockTool.label).toBe('获取股票数据');
    });

    it('should have description', () => {
      expect(dataFetchStockTool.description).toBeDefined();
      expect(dataFetchStockTool.description.length).toBeGreaterThan(0);
    });

    it('should have execute function', () => {
      expect(dataFetchStockTool.execute).toBeDefined();
      expect(typeof dataFetchStockTool.execute).toBe('function');
    });
  });

  describe('Default behavior (info + price)', () => {
    it('should fetch info and price by default', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        info: {
          symbol: '600519',
          name: '贵州茅台',
          sector: '食品饮料',
          market_cap: 2250000000000
        },
        price: {
          symbol: '600519',
          price: 1800.50,
          change_pct: 2.5,
          volume: 1500000
        }
      });

      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '600519' });

      expect(mockGetStockData).toHaveBeenCalledTimes(1);
      expect(mockGetStockData).toHaveBeenCalledWith('600519', ['info', 'price'], 10);

      const response = JSON.parse(getResponseText(result));
      expect(response.info).toBeDefined();
      expect(response.price).toBeDefined();
      expect(response.info.symbol).toBe('600519');
      expect(response.price.price).toBe(1800.50);
    });
  });

  describe('Field-specific queries', () => {
    it('should fetch only info when fields=["info"]', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        info: {
          symbol: '600519',
          name: '贵州茅台'
        }
      });

      const result = await (dataFetchStockTool.execute as any)('test-call-id', {
        symbol: '600519',
        fields: ['info']
      });

      expect(mockGetStockData).toHaveBeenCalledTimes(1);
      expect(mockGetStockData).toHaveBeenCalledWith('600519', ['info'], 10);

      const response = JSON.parse(getResponseText(result));
      expect(response.info).toBeDefined();
      expect(response.price).toBeUndefined();
      expect(response.news).toBeUndefined();
      expect(response.announcements).toBeUndefined();
    });

    it('should fetch news when fields=["news"]', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        news: {
          news: [
            { title: '茅台发布年报', date: '2026-05-20' }
          ]
        }
      });

      const result = await (dataFetchStockTool.execute as any)('test-call-id', {
        symbol: '600519',
        fields: ['news']
      });

      expect(mockGetStockData).toHaveBeenCalledTimes(1);
      expect(mockGetStockData).toHaveBeenCalledWith('600519', ['news'], 10);

      const response = JSON.parse(getResponseText(result));
      expect(response.news).toBeDefined();
    });

    it('should fetch announcements when fields=["announcements"]', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        announcements: {
          announcements: [
            { title: '2025年年度报告', date: '2026-04-30' }
          ]
        }
      });

      const result = await (dataFetchStockTool.execute as any)('test-call-id', {
        symbol: '600519',
        fields: ['announcements']
      });

      expect(mockGetStockData).toHaveBeenCalledTimes(1);
      expect(mockGetStockData).toHaveBeenCalledWith('600519', ['announcements'], 10);

      const response = JSON.parse(getResponseText(result));
      expect(response.announcements).toBeDefined();
    });

    it('should fetch multiple fields', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        info: { symbol: '600519', name: '贵州茅台' },
        news: { news: [] }
      });

      const result = await (dataFetchStockTool.execute as any)('test-call-id', {
        symbol: '600519',
        fields: ['info', 'news']
      });

      expect(mockGetStockData).toHaveBeenCalledTimes(1);

      const response = JSON.parse(getResponseText(result));
      expect(response.info).toBeDefined();
      expect(response.news).toBeDefined();
      expect(response.price).toBeUndefined();
    });
  });

  describe('HK stock support', () => {
    it('should support HK stock with .HK suffix', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        info: {
          symbol: '9988.HK',
          name: '阿里巴巴-SW'
        },
        price: {
          symbol: '9988.HK',
          price: 85.50
        }
      });

      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '9988.HK' });

      expect(mockGetStockData).toHaveBeenCalledWith('9988.HK', ['info', 'price'], 10);

      const response = JSON.parse(getResponseText(result));
      expect(response.info.symbol).toBe('9988.HK');
    });

    it('should support HK stock without suffix', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        info: {
          symbol: '9988',
          name: '阿里巴巴-SW'
        },
        price: {
          symbol: '9988',
          price: 85.50
        }
      });

      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '9988' });

      const response = JSON.parse(getResponseText(result));
      expect(response.info).toBeDefined();
    });
  });

  describe('Error handling', () => {
    it('should reject invalid stock code', async () => {
      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: 'AAPL' });

      expect(mockGetStockData).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.error).toBeDefined();
      expect(response.error).toContain('不支持的股票代码');
      expect(response.invalid_format).toBe(true);
    });

    it('should handle v2 client errors gracefully', async () => {
      mockGetStockData.mockRejectedValueOnce(new Error('Network timeout'));

      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('获取股票数据失败');
      expect(response.error).toContain('Network timeout');
    });

    it('should handle partial failures from v2 API', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        info: { symbol: '600519', name: '贵州茅台' },
        price: null,
        price_error: 'Price service unavailable'
      });

      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.info).toBeDefined();
      expect(response.info.symbol).toBe('600519');
      expect(response.price).toBeNull();
      expect(response.price_error).toBeDefined();
      expect(response.price_error).toContain('Price service unavailable');
    });
  });

  describe('Custom parameters', () => {
    it('should pass num parameter to news query', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        news: { news: [] }
      });

      await (dataFetchStockTool.execute as any)('test-call-id', {
        symbol: '600519',
        fields: ['news'],
        news_num: 20
      });

      expect(mockGetStockData).toHaveBeenCalledWith('600519', ['news'], 20);
    });
  });
});
