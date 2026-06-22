/**
 * Data Fetch Quote Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';

const mockGetStockData = jest.fn<(symbol: string, fields?: Array<'price'>, newsNum?: number, source?: 'realtime' | 'db' | 'auto') => Promise<any>>();
const mockFormatStockPrice = jest.fn<(priceData: any) => string>();

jest.unstable_mockModule('../../quant/quant-v2-client.js', () => ({
  getStockData: mockGetStockData
}));

jest.unstable_mockModule('../../quant/formatters.js', () => ({
  formatStockPrice: mockFormatStockPrice
}));

const { dataFetchQuoteTool } = await import('./fetch-stock-tool.js');

// Helper to extract text from tool result
function getResponseText(result: any): string {
  return result.content[0].text;
}

describe('data_fetch_quote tool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tool Definition', () => {
    it('should have correct name and label', () => {
      expect(dataFetchQuoteTool.name).toBe('data_fetch_quote');
      expect(dataFetchQuoteTool.label).toBe('获取股票实时行情');
    });

    it('should have description', () => {
      expect(dataFetchQuoteTool.description).toBeDefined();
      expect(dataFetchQuoteTool.description.length).toBeGreaterThan(0);
    });

    it('should have execute function', () => {
      expect(dataFetchQuoteTool.execute).toBeDefined();
      expect(typeof dataFetchQuoteTool.execute).toBe('function');
    });
  });

  describe('Default behavior (auto mode)', () => {
    it('should fetch price with auto source by default', async () => {
      const mockPriceData = {
        data: {
          symbol: '600519',
          name: '贵州茅台',
          price: 1800.50,
          changePct: 2.5,
          volume: 1500000,
          source: 'sina',
          timestamp: '2026-06-02T10:30:00'
        },
        success: true
      };

      mockGetStockData.mockResolvedValueOnce({
        success: true,
        price: mockPriceData
      });

      mockFormatStockPrice.mockReturnValueOnce('贵州茅台 (600519)\n价格: 1800.50');

      const result = await (dataFetchQuoteTool.execute as any)('test-call-id', { symbol: '600519' });

      expect(mockGetStockData).toHaveBeenCalledTimes(1);
      expect(mockGetStockData).toHaveBeenCalledWith('600519', ['price'], 10, 'auto');
      expect(mockFormatStockPrice).toHaveBeenCalledWith(mockPriceData);

      const responseText = getResponseText(result);
      expect(responseText).toContain('贵州茅台');
      expect(responseText).toContain('1800.50');
    });
  });

  describe('Source parameter', () => {
    it('should support realtime source', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        price: {
          data: { symbol: '600519', price: 1800.50, source: 'sina' },
          success: true
        }
      });

      mockFormatStockPrice.mockReturnValueOnce('Mock formatted output');

      await (dataFetchQuoteTool.execute as any)('test-call-id', {
        symbol: '600519',
        source: 'realtime'
      });

      expect(mockGetStockData).toHaveBeenCalledWith('600519', ['price'], 10, 'realtime');
    });

    it('should support db source', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: true,
        price: {
          data: { symbol: '600519', price: 1800.50, source: 'db_fallback', tradeDate: '2026-06-01' },
          success: true
        }
      });

      mockFormatStockPrice.mockReturnValueOnce('Mock formatted output');

      await (dataFetchQuoteTool.execute as any)('test-call-id', {
        symbol: '600519',
        source: 'db'
      });

      expect(mockGetStockData).toHaveBeenCalledWith('600519', ['price'], 10, 'db');
    });
  });

  describe('Error handling', () => {
    it('should reject invalid stock code', async () => {
      const result = await (dataFetchQuoteTool.execute as any)('test-call-id', { symbol: 'AAPL' });

      expect(mockGetStockData).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.error).toBeDefined();
      expect(response.error).toContain('不支持的股票代码');
      expect(response.invalid_format).toBe(true);
    });

    it('should handle v2 client errors gracefully', async () => {
      mockGetStockData.mockRejectedValueOnce(new Error('Network timeout'));

      const result = await (dataFetchQuoteTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('获取股票行情失败');
      expect(response.error).toContain('Network timeout');
    });

    it('should handle price_error from v2 API', async () => {
      mockGetStockData.mockResolvedValueOnce({
        success: false,
        price: null,
        price_error: 'HTTP 502: 无法获取实时行情'
      });

      const result = await (dataFetchQuoteTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('无法获取实时行情');
    });

    it('should add friendly message for non-trading hours', async () => {
      // Mock non-trading time (e.g., Sunday 10:00)
      const mockDate = new Date('2026-06-07T10:00:00'); // Sunday
      jest.useFakeTimers();
      jest.setSystemTime(mockDate);

      mockGetStockData.mockResolvedValueOnce({
        success: false,
        price: null,
        price_error: 'HTTP 502: 无法获取 600519 的实时行情'
      });

      const result = await (dataFetchQuoteTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.error).toContain('💡 提示：当前非交易时段');
      expect(response.error).toContain('A股交易时间：周一至周五 9:30-11:30, 13:00-15:00');

      jest.useRealTimers();
    });
  });
});
