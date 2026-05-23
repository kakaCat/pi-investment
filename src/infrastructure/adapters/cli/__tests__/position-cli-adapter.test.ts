import { describe, expect, it, beforeEach, jest } from '@jest/globals';
import { PositionCliAdapter } from '../position-cli-adapter.js';
import { CliExecutionError } from '../types.js';

// Mock the entire base-cli-adapter module
jest.mock('../base-cli-adapter.js', () => {
  return {
    BaseCliAdapter: class {
      protected async executeCommand(domain: string, action: string, params: Record<string, any>): Promise<any> {
        // This will be overridden in tests
        return {};
      }
    }
  };
});

describe('PositionCliAdapter', () => {
  let adapter: PositionCliAdapter;

  beforeEach(() => {
    adapter = new PositionCliAdapter();
    jest.clearAllMocks();
  });

  describe('list', () => {
    it('should list positions with default parameters', async () => {
      const mockData = {
        total: 1,
        positions: [{
          symbol: '600036',
          name: '招商银行',
          quantity: 100,
          cost_basis: 38.5,
          current_price: 40.0,
          entry_date: '2026-05-01',
          stop_loss: 35.0,
          take_profit: 45.0,
          status: 'open',
          account_id: 'default',
          notes: 'Test position'
        }]
      };

      jest.spyOn(adapter as any, 'executeCommand').mockResolvedValue(mockData);

      const result = await adapter.list();
      expect(result).toHaveLength(1);
      expect(result[0]).toEqual({
        symbol: '600036',
        name: '招商银行',
        quantity: 100,
        costBasis: 38.5,
        currentPrice: 40.0,
        entryDate: '2026-05-01',
        stopLoss: 35.0,
        takeProfit: 45.0,
        status: 'open',
        accountId: 'default',
        notes: 'Test position'
      });
    });

    it('should list positions with filters', async () => {
      const mockData = { total: 0, positions: [] };

      const executeSpy = jest.spyOn(adapter as any, 'executeCommand').mockResolvedValue(mockData);

      await adapter.list({ accountId: 'test', status: 'closed' });

      expect(executeSpy).toHaveBeenCalledWith('position', 'list', {
        accountId: 'test',
        status: 'closed'
      });
    });
  });

  describe('get', () => {
    it('should get single position', async () => {
      const mockData = {
        symbol: '600036',
        name: '招商银行',
        quantity: 100,
        cost_basis: 38.5,
        current_price: 40.0,
        entry_date: '2026-05-01',
        stop_loss: 35.0,
        take_profit: 45.0,
        status: 'open',
        account_id: 'default',
        notes: 'Test position'
      };

      jest.spyOn(adapter as any, 'executeCommand').mockResolvedValue(mockData);

      const result = await adapter.get('600036');
      expect(result).toEqual({
        symbol: '600036',
        name: '招商银行',
        quantity: 100,
        costBasis: 38.5,
        currentPrice: 40.0,
        entryDate: '2026-05-01',
        stopLoss: 35.0,
        takeProfit: 45.0,
        status: 'open',
        accountId: 'default',
        notes: 'Test position'
      });
    });

    it('should return null when position not found', async () => {
      const error = new CliExecutionError('Position not found', 'quant position +get', 1);

      jest.spyOn(adapter as any, 'executeCommand').mockRejectedValue(error);

      const result = await adapter.get('NONEXISTENT');
      expect(result).toBeNull();
    });
  });

  describe('update', () => {
    it('should update position and return true on success', async () => {
      const mockData = { updated_rows: 1 };

      jest.spyOn(adapter as any, 'executeCommand').mockResolvedValue(mockData);

      const result = await adapter.update('600036', { price: 38.5 });
      expect(result).toBe(true);
    });

    it('should return false when no rows updated', async () => {
      const mockData = { updated_rows: 0 };

      jest.spyOn(adapter as any, 'executeCommand').mockResolvedValue(mockData);

      const result = await adapter.update('600036', { price: 38.5 });
      expect(result).toBe(false);
    });
  });

  describe('close', () => {
    it('should close position', async () => {
      const mockData = { closed: true };

      jest.spyOn(adapter as any, 'executeCommand').mockResolvedValue(mockData);

      const result = await adapter.close('600036', '止盈');
      expect(result).toBe(true);
    });
  });

  describe('getSummary', () => {
    it('should get position summary', async () => {
      const mockData = {
        total_positions: 2,
        total_quantity: 100,
        total_cost: 5000,
        total_market_value: 6000,
        total_pnl: 1000,
        total_pnl_pct: 20
      };

      jest.spyOn(adapter as any, 'executeCommand').mockResolvedValue(mockData);

      const result = await adapter.getSummary();
      expect(result.totalPositions).toBe(2);
      expect(result.totalPnl).toBe(1000);
      expect(result).toEqual({
        totalPositions: 2,
        totalQuantity: 100,
        totalCost: 5000,
        totalMarketValue: 6000,
        totalPnl: 1000,
        totalPnlPct: 20
      });
    });
  });
});
