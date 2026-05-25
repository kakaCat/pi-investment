/**
 * Data Fetch Stock Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';

const mockCallQuantSysDaemon = jest.fn<(func: string, args?: Record<string, unknown>) => Promise<string>>();

jest.unstable_mockModule('../../quant/quantsys-daemon-adapter.js', () => ({
  callQuantSysDaemon: mockCallQuantSysDaemon
}));

const { dataFetchStockTool } = await import('./fetch-stock-tool.js');

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
      const mockInfoResponse = JSON.stringify({
        symbol: '600519',
        name: '贵州茅台',
        sector: '食品饮料',
        market_cap: 2250000000000
      });

      const mockPriceResponse = JSON.stringify({
        symbol: '600519',
        price: 1800.50,
        change_pct: 2.5,
        volume: 1500000
      });

      mockCallQuantSysDaemon
        .mockResolvedValueOnce(mockInfoResponse)
        .mockResolvedValueOnce(mockPriceResponse);

      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '600519' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(2);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_stock_info', { symbol: '600519' });
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_stock_realtime_price', { symbol: '600519' });

      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.info).toBeDefined();
      expect(response.price).toBeDefined();
      expect(response.info.symbol).toBe('600519');
      expect(response.price.price).toBe(1800.50);
    });
  });

  describe('Field-specific queries', () => {
    it('should fetch only info when fields=["info"]', async () => {
      const mockInfoResponse = JSON.stringify({
        symbol: '600519',
        name: '贵州茅台'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockInfoResponse);

      const result = await (dataFetchStockTool.execute as any)('test-call-id', {
        symbol: '600519',
        fields: ['info']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(1);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_stock_info', { symbol: '600519' });

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.info).toBeDefined();
      expect(response.price).toBeUndefined();
      expect(response.news).toBeUndefined();
      expect(response.announcements).toBeUndefined();
    });

    it('should fetch news when fields=["news"]', async () => {
      const mockNewsResponse = JSON.stringify({
        news: [
          { title: '茅台发布年报', date: '2026-05-20' }
        ]
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockNewsResponse);

      const result = await (dataFetchStockTool.execute as any)('test-call-id', {
        symbol: '600519',
        fields: ['news']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(1);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_stock_news', { symbol: '600519', num: 10 });

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.news).toBeDefined();
    });

    it('should fetch announcements when fields=["announcements"]', async () => {
      const mockAnnouncementsResponse = JSON.stringify({
        announcements: [
          { title: '2025年年度报告', date: '2026-04-30' }
        ]
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockAnnouncementsResponse);

      const result = await (dataFetchStockTool.execute as any)('test-call-id', {
        symbol: '600519',
        fields: ['announcements']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(1);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_announcements', { symbol: '600519' });

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.announcements).toBeDefined();
    });

    it('should fetch multiple fields', async () => {
      const mockInfoResponse = JSON.stringify({ symbol: '600519', name: '贵州茅台' });
      const mockNewsResponse = JSON.stringify({ news: [] });

      mockCallQuantSysDaemon
        .mockResolvedValueOnce(mockInfoResponse)
        .mockResolvedValueOnce(mockNewsResponse);

      const result = await (dataFetchStockTool.execute as any)('test-call-id', {
        symbol: '600519',
        fields: ['info', 'news']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(2);

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.info).toBeDefined();
      expect(response.news).toBeDefined();
      expect(response.price).toBeUndefined();
    });
  });

  describe('HK stock support', () => {
    it('should support HK stock with .HK suffix', async () => {
      const mockInfoResponse = JSON.stringify({
        symbol: '9988.HK',
        name: '阿里巴巴-SW'
      });

      const mockPriceResponse = JSON.stringify({
        symbol: '9988.HK',
        price: 85.50
      });

      mockCallQuantSysDaemon
        .mockResolvedValueOnce(mockInfoResponse)
        .mockResolvedValueOnce(mockPriceResponse);

      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '9988.HK' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_stock_info', { symbol: '9988.HK' });
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_stock_realtime_price', { symbol: '9988.HK' });

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.info.symbol).toBe('9988.HK');
    });

    it('should support HK stock without suffix', async () => {
      const mockInfoResponse = JSON.stringify({
        symbol: '9988',
        name: '阿里巴巴-SW'
      });

      const mockPriceResponse = JSON.stringify({
        symbol: '9988',
        price: 85.50
      });

      mockCallQuantSysDaemon
        .mockResolvedValueOnce(mockInfoResponse)
        .mockResolvedValueOnce(mockPriceResponse);

      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '9988' });

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.info).toBeDefined();
    });
  });

  describe('Error handling', () => {
    it('should reject invalid stock code', async () => {
      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: 'AAPL' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('不支持的股票代码');
      expect(response.invalid_format).toBe(true);
    });

    it('should handle daemon errors gracefully', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('Network timeout'));

      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('Network timeout');
    });

    it('should handle partial failures', async () => {
      const mockInfoResponse = JSON.stringify({ symbol: '600519', name: '贵州茅台' });

      mockCallQuantSysDaemon
        .mockResolvedValueOnce(mockInfoResponse)
        .mockRejectedValueOnce(new Error('Price service unavailable'));

      const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.info).toBeDefined();
      expect(response.price_error).toBeDefined();
      expect(response.price_error).toContain('Price service unavailable');
    });
  });

  describe('Custom parameters', () => {
    it('should pass num parameter to news query', async () => {
      const mockNewsResponse = JSON.stringify({ news: [] });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockNewsResponse);

      await (dataFetchStockTool.execute as any)('test-call-id', {
        symbol: '600519',
        fields: ['news'],
        news_num: 20
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_stock_news', {
        symbol: '600519',
        num: 20
      });
    });
  });
});
