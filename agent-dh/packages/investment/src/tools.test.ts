import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createQuoteTool } from '../src/tools/quote-tool.js';
import { createKlineTool } from '../src/tools/kline-tool.js';
import { createFinancialTool } from '../src/tools/financial-tool.js';
import { createPoolListTool } from '../src/tools/pool-list-tool.js';
import { createStrategyListTool } from '../src/tools/strategy-list-tool.js';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

describe('Investment Tools', () => {
  let mockClient: AgentDHClient;

  beforeEach(() => {
    mockClient = {
      quantsysV2: {
        getQuote: vi.fn(),
        getKlines: vi.fn(),
        getFinancialData: vi.fn(),
        listPools: vi.fn(),
        listStrategies: vi.fn(),
      },
    } as any;
  });

  describe('quote-tool', () => {
    it('should have correct metadata', () => {
      const tool = createQuoteTool(mockClient);
      expect(tool.name).toBe('data_fetch_quote');
      expect(tool.description).toContain('实时行情');
    });

    it('should call getQuote with correct symbol', async () => {
      const mockQuote = { symbol: '600519', price: 1800, change: 10, change_pct: 0.56, volume: 1000000, timestamp: '2024-01-01' };
      vi.mocked(mockClient.quantsysV2.getQuote).mockResolvedValue(mockQuote);

      const tool = createQuoteTool(mockClient);
      const result = await tool.execute({ symbol: '600519' }, { signal: new AbortController().signal } as any);

      expect(mockClient.quantsysV2.getQuote).toHaveBeenCalledWith('600519');
      expect(result).toEqual(mockQuote);
    });

    it('should throw error when API fails', async () => {
      vi.mocked(mockClient.quantsysV2.getQuote).mockRejectedValue(new Error('Network error'));

      const tool = createQuoteTool(mockClient);
      await expect(
        tool.execute({ symbol: '600519' }, { signal: new AbortController().signal } as any)
      ).rejects.toThrow('获取股票 600519 行情失败');
    });
  });

  describe('kline-tool', () => {
    it('should have correct metadata', () => {
      const tool = createKlineTool(mockClient);
      expect(tool.name).toBe('data_fetch_kline');
      expect(tool.description).toContain('K线数据');
    });

    it('should call getKlines with correct parameters', async () => {
      const mockKlines = [{ date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000 }];
      vi.mocked(mockClient.quantsysV2.getKlines).mockResolvedValue(mockKlines);

      const tool = createKlineTool(mockClient);
      const result = await tool.execute(
        { symbol: '600519', start_date: '2024-01-01', end_date: '2024-01-31', period: 'daily' },
        { signal: new AbortController().signal } as any
      );

      expect(mockClient.quantsysV2.getKlines).toHaveBeenCalledWith('600519', '2024-01-01', '2024-01-31', 'daily');
      expect(result).toEqual(mockKlines);
    });

    it('should use default period when not provided', async () => {
      const mockKlines = [];
      vi.mocked(mockClient.quantsysV2.getKlines).mockResolvedValue(mockKlines);

      const tool = createKlineTool(mockClient);
      await tool.execute(
        { symbol: '600519', start_date: '2024-01-01', end_date: '2024-01-31' },
        { signal: new AbortController().signal } as any
      );

      expect(mockClient.quantsysV2.getKlines).toHaveBeenCalledWith('600519', '2024-01-01', '2024-01-31', 'daily');
    });
  });

  describe('financial-tool', () => {
    it('should have correct metadata', () => {
      const tool = createFinancialTool(mockClient);
      expect(tool.name).toBe('data_fetch_financial');
      expect(tool.description).toContain('财务数据');
    });

    it('should call getFinancialData with correct symbol', async () => {
      const mockFinancial = { symbol: '600519', report_date: '2024-Q1', revenue: 1000000, net_profit: 200000, roe: 25 };
      vi.mocked(mockClient.quantsysV2.getFinancialData).mockResolvedValue(mockFinancial);

      const tool = createFinancialTool(mockClient);
      const result = await tool.execute({ symbol: '600519' }, { signal: new AbortController().signal } as any);

      expect(mockClient.quantsysV2.getFinancialData).toHaveBeenCalledWith('600519');
      expect(result).toEqual(mockFinancial);
    });
  });

  describe('pool-list-tool', () => {
    it('should have correct metadata', () => {
      const tool = createPoolListTool(mockClient);
      expect(tool.name).toBe('pool_list');
      expect(tool.description).toContain('股票池列表');
    });

    it('should call listPools', async () => {
      const mockPools = [{ id: 1, name: 'Test Pool', description: 'Test', created_at: '2024-01-01', updated_at: '2024-01-01' }];
      vi.mocked(mockClient.quantsysV2.listPools).mockResolvedValue(mockPools);

      const tool = createPoolListTool(mockClient);
      const result = await tool.execute({}, { signal: new AbortController().signal } as any);

      expect(mockClient.quantsysV2.listPools).toHaveBeenCalled();
      expect(result).toEqual(mockPools);
    });
  });

  describe('strategy-list-tool', () => {
    it('should have correct metadata', () => {
      const tool = createStrategyListTool(mockClient);
      expect(tool.name).toBe('strategy_list');
      expect(tool.description).toContain('策略列表');
    });

    it('should call listStrategies with no params', async () => {
      const mockStrategies = [{ id: 1, name: 'MA Cross', code: 'ma_cross', code_type: 'indicator' as const }];
      vi.mocked(mockClient.quantsysV2.listStrategies).mockResolvedValue(mockStrategies);

      const tool = createStrategyListTool(mockClient);
      const result = await tool.execute({}, { signal: new AbortController().signal } as any);

      expect(mockClient.quantsysV2.listStrategies).toHaveBeenCalledWith({});
      expect(result).toEqual(mockStrategies);
    });

    it('should call listStrategies with source filter', async () => {
      const mockStrategies = [];
      vi.mocked(mockClient.quantsysV2.listStrategies).mockResolvedValue(mockStrategies);

      const tool = createStrategyListTool(mockClient);
      await tool.execute({ source: 'builtin' }, { signal: new AbortController().signal } as any);

      expect(mockClient.quantsysV2.listStrategies).toHaveBeenCalledWith({ source: 'builtin' });
    });
  });
});
