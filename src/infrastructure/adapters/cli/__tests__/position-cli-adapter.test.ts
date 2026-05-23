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
        positions: [{ symbol: '600036', quantity: 100 }]
      };

      jest.spyOn(adapter as any, 'executeCommand').mockResolvedValue(mockData);

      const result = await adapter.list();
      expect(result).toEqual([{ symbol: '600036', quantity: 100 }]);
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
      const mockData = { symbol: '600036', quantity: 100 };

      jest.spyOn(adapter as any, 'executeCommand').mockResolvedValue(mockData);

      const result = await adapter.get('600036');
      expect(result).toEqual({ symbol: '600036', quantity: 100 });
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
        totalPositions: 2,
        totalQuantity: 100,
        totalCost: 5000,
        totalMarketValue: 6000,
        totalPnl: 1000,
        totalPnlPct: 20
      };

      jest.spyOn(adapter as any, 'executeCommand').mockResolvedValue(mockData);

      const result = await adapter.getSummary();
      expect(result.totalPositions).toBe(2);
      expect(result.totalPnl).toBe(1000);
    });
  });
});
