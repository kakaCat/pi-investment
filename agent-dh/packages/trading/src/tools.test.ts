import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createAccountInfoTool } from '../src/tools/account-info-tool.js';
import { createPositionListTool } from '../src/tools/position-list-tool.js';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

describe('Trading Tools', () => {
  let mockClient: AgentDHClient;

  beforeEach(() => {
    mockClient = {
      quantsysV2: {
        getPortfolioSummary: vi.fn(),
        getPositions: vi.fn(),
      },
    } as any;
  });

  describe('account-info-tool', () => {
    it('should have correct metadata', () => {
      const tool = createAccountInfoTool(mockClient);
      expect(tool.name).toBe('account_info');
      expect(tool.description).toContain('账户信息');
    });

    it('should call getPortfolioSummary', async () => {
      const mockSummary = {
        total_value: 1000000,
        total_cost: 900000,
        total_profit: 100000,
        total_profit_pct: 11.11,
        cash: 200000,
        positions_count: 5,
        updated_at: '2024-01-01',
      };
      vi.mocked(mockClient.quantsysV2.getPortfolioSummary).mockResolvedValue(mockSummary);

      const tool = createAccountInfoTool(mockClient);
      const result = await tool.execute({}, { signal: new AbortController().signal } as any);

      expect(mockClient.quantsysV2.getPortfolioSummary).toHaveBeenCalled();
      expect(result).toEqual(mockSummary);
    });

    it('should throw error when API fails', async () => {
      vi.mocked(mockClient.quantsysV2.getPortfolioSummary).mockRejectedValue(new Error('Network error'));

      const tool = createAccountInfoTool(mockClient);
      await expect(
        tool.execute({}, { signal: new AbortController().signal } as any)
      ).rejects.toThrow('获取账户信息失败');
    });
  });

  describe('position-list-tool', () => {
    it('should have correct metadata', () => {
      const tool = createPositionListTool(mockClient);
      expect(tool.name).toBe('position_list');
      expect(tool.description).toContain('持仓列表');
    });

    it('should call getPositions', async () => {
      const mockPositions = [
        {
          symbol: '600519',
          name: '贵州茅台',
          shares: 100,
          avg_cost: 1800,
          current_price: 2000,
          market_value: 200000,
          profit: 20000,
          profit_pct: 11.11,
          updated_at: '2024-01-01',
        },
      ];
      vi.mocked(mockClient.quantsysV2.getPositions).mockResolvedValue(mockPositions);

      const tool = createPositionListTool(mockClient);
      const result = await tool.execute({}, { signal: new AbortController().signal } as any);

      expect(mockClient.quantsysV2.getPositions).toHaveBeenCalled();
      expect(result).toEqual(mockPositions);
    });

    it('should throw error when API fails', async () => {
      vi.mocked(mockClient.quantsysV2.getPositions).mockRejectedValue(new Error('Network error'));

      const tool = createPositionListTool(mockClient);
      await expect(
        tool.execute({}, { signal: new AbortController().signal } as any)
      ).rejects.toThrow('获取持仓列表失败');
    });
  });
});
