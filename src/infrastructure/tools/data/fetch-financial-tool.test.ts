/**
 * Data Fetch Financial Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { tmpdir } from 'os';
import { readFile, unlink } from 'fs/promises';
import { join } from 'path';
import { getResponseText } from '../test-utils.js';

const mockCallQuantSysDaemon = jest.fn<(func: string, args?: Record<string, unknown>) => Promise<string>>();

jest.unstable_mockModule('../../quant/quantsys-daemon-adapter.js', () => ({
  callQuantSysDaemon: mockCallQuantSysDaemon
}));

const { dataFetchFinancialTool } = await import('./fetch-financial-tool.js');

describe('data_fetch_financial tool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tool Definition', () => {
    it('should have correct name and label', () => {
      expect(dataFetchFinancialTool.name).toBe('data_fetch_financial');
      expect(dataFetchFinancialTool.label).toBe('获取财务指标');
    });

    it('should have description', () => {
      expect(dataFetchFinancialTool.description).toBeDefined();
      expect(dataFetchFinancialTool.description.length).toBeGreaterThan(0);
    });

    it('should have execute function', () => {
      expect(dataFetchFinancialTool.execute).toBeDefined();
      expect(typeof dataFetchFinancialTool.execute).toBe('function');
    });
  });

  describe('Default behavior (all statements, 8 periods)', () => {
    it('should fetch all financial statements with default parameters', async () => {
      const mockFinancialResponse = JSON.stringify({
        symbol: '600519',
        income_statement: { data: [{ 报告日: '2026-03-31', 营业总收入: 50000000000, 净利润: 20000000000 }] },
        balance_sheet: { data: [{ 报告日: '2026-03-31', 总资产: 300000000000, 总负债: 100000000000 }] },
        cashflow_statement: { data: [{ 报告日: '2026-03-31', 经营活动现金流: 25000000000 }] }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockFinancialResponse);

      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', { symbol: '600519' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(1);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_financial_statements', {
        symbol: '600519',
        statement: 'all',
        recent_n: 8
      });

      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');

      const response = JSON.parse(getResponseText(result));
      expect(response.symbol).toBe('600519');
      expect(response.income_statement).toBeDefined();
      expect(response.balance_sheet).toBeDefined();
      expect(response.cashflow_statement).toBeDefined();
    });
  });

  describe('Custom parameters', () => {
    it('should fetch only income statement', async () => {
      const mockFinancialResponse = JSON.stringify({
        symbol: '600519',
        income_statement: { data: [{ 报告日: '2026-03-31', 营业总收入: 50000000000 }] }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockFinancialResponse);

      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', {
        symbol: '600519',
        statement: 'income'
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_financial_statements', {
        symbol: '600519',
        statement: 'income',
        recent_n: 8
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.income_statement).toBeDefined();
    });

    it('should fetch only balance sheet', async () => {
      const mockFinancialResponse = JSON.stringify({
        symbol: '600519',
        balance_sheet: { data: [{ 报告日: '2026-03-31', 总资产: 300000000000 }] }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockFinancialResponse);

      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', {
        symbol: '600519',
        statement: 'balance'
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_financial_statements', {
        symbol: '600519',
        statement: 'balance',
        recent_n: 8
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.balance_sheet).toBeDefined();
    });

    it('should fetch only cashflow statement', async () => {
      const mockFinancialResponse = JSON.stringify({
        symbol: '600519',
        cashflow_statement: { data: [{ 报告日: '2026-03-31', 经营活动现金流: 25000000000 }] }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockFinancialResponse);

      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', {
        symbol: '600519',
        statement: 'cashflow'
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_financial_statements', {
        symbol: '600519',
        statement: 'cashflow',
        recent_n: 8
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.cashflow_statement).toBeDefined();
    });

    it('should fetch custom number of recent periods', async () => {
      const mockFinancialResponse = JSON.stringify({
        symbol: '600519',
        income_statement: { data: [] }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockFinancialResponse);

      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', {
        symbol: '600519',
        recent_n: 4
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_financial_statements', {
        symbol: '600519',
        statement: 'all',
        recent_n: 4
      });
    });

    it('should fetch with all custom parameters', async () => {
      const mockFinancialResponse = JSON.stringify({
        symbol: '600519',
        income_statement: { data: [] }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockFinancialResponse);

      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', {
        symbol: '600519',
        statement: 'income',
        recent_n: 12
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('get_financial_statements', {
        symbol: '600519',
        statement: 'income',
        recent_n: 12
      });
    });
  });

  describe('Large data handling', () => {
    it('should write large data to temp file and return preview', async () => {
      // Create a large JSON response (> 2000 characters)
      const largeData = {
        symbol: '600519',
        income_statement: {
          data: Array(100).fill({
            报告日: '2026-03-31',
            营业总收入: 50000000000,
            营业成本: 10000000000,
            销售费用: 5000000000,
            管理费用: 3000000000,
            财务费用: 1000000000,
            净利润: 20000000000,
            基本每股收益: 15.5,
            稀释每股收益: 15.5,
            营业外收入: 500000000,
            营业外支出: 300000000,
            所得税费用: 8000000000,
            其他综合收益: 1000000000
          })
        }
      };
      const mockFinancialResponse = JSON.stringify(largeData);

      // Verify the mock data is actually > 2000 characters
      expect(mockFinancialResponse.length).toBeGreaterThan(2000);

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockFinancialResponse);

      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', { symbol: '600519' });

      const responseText = getResponseText(result);
      const response = JSON.parse(responseText);

      // Should have file metadata
      expect(response.note).toBe('数据过大，已写入临时文件');
      expect(response.file).toBeDefined();
      expect(response.file).toContain('financial_600519_');
      expect(response.preview_text).toBeDefined();
      expect(response.full_length).toBeGreaterThan(2000);

      // Verify file was created
      const fileContent = await readFile(response.file, 'utf-8');
      expect(fileContent).toBe(mockFinancialResponse);

      // Cleanup
      await unlink(response.file);
    });

    it('should return inline data when small enough', async () => {
      const smallData = {
        symbol: '600519',
        income_statement: { data: [{ 报告日: '2026-03-31', 营业总收入: 50000000000 }] }
      };
      const mockFinancialResponse = JSON.stringify(smallData);

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockFinancialResponse);

      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));

      // Should NOT have file metadata
      expect(response.note).toBeUndefined();
      expect(response.file).toBeUndefined();
      expect(response.symbol).toBe('600519');
      expect(response.income_statement).toBeDefined();
    });
  });

  describe('Error handling', () => {
    it('should reject HK stock code', async () => {
      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', { symbol: '9988.HK' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('暂不支持港股代码');
      expect(response.unsupported_for_hk).toBe(true);
    });

    it('should reject HK stock code without suffix', async () => {
      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', { symbol: '9988' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('暂不支持港股代码');
    });

    it('should reject invalid stock code', async () => {
      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', { symbol: 'AAPL' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('不支持的股票代码');
      expect(response.invalid_format).toBe(true);
    });

    it('should handle daemon errors gracefully', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('Database connection failed'));

      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('获取财务数据失败');
      expect(response.error).toContain('Database connection failed');
    });

    it('should handle empty symbol', async () => {
      const result = await (dataFetchFinancialTool.execute as any)('test-call-id', { symbol: '' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
    });
  });
});
