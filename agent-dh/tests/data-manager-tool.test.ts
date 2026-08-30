/**
 * DataManagerTool 单元测试
 *
 * 验证 C/D-class 修复：status 操作使用 getPlatformStatus() 而非 POST /api/data/update
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DataManagerTool } from '../packages/data-manager/src/tools/DataManagerTool/DataManagerTool.js';

describe('DataManagerTool', () => {
  let tool: DataManagerTool;
  let mockClient: any;
  const mockContext = {} as any;

  beforeEach(() => {
    mockClient = {
      getPlatformStatus: vi.fn(),
      dataManager: vi.fn(),
    };
    tool = new DataManagerTool(mockClient);
  });

  describe('validate', () => {
    it('accepts valid status operation', () => {
      const result = (tool as any).validate({ operation: 'status' });
      expect(result.success).toBe(true);
    });

    it('accepts valid refresh operation', () => {
      const result = (tool as any).validate({ operation: 'refresh', data_type: 'kline' });
      expect(result.success).toBe(true);
    });

    it('rejects invalid operation', () => {
      const result = (tool as any).validate({ operation: 'invalid' });
      expect(result.success).toBe(false);
    });

    it('rejects invalid data_type', () => {
      const result = (tool as any).validate({ operation: 'status', data_type: 'invalid' });
      expect(result.success).toBe(false);
    });

    it('rejects invalid symbol format', () => {
      const result = (tool as any).validate({ operation: 'refresh', symbol: '123' });
      expect(result.success).toBe(false);
    });

    it('accepts valid 6-digit symbol', () => {
      const result = (tool as any).validate({ operation: 'refresh', symbol: '600519' });
      expect(result.success).toBe(true);
    });

    it('rejects start_date after end_date', () => {
      const result = (tool as any).validate({
        operation: 'refresh',
        start_date: '2026-01-10',
        end_date: '2026-01-01',
      });
      expect(result.success).toBe(false);
    });
  });

  describe('execute - status operation', () => {
    it('calls getPlatformStatus for status operation', async () => {
      mockClient.getPlatformStatus.mockResolvedValue({
        status: 'healthy',
        db_connected: true,
        holdings_count: 5,
        balance: {},
        recent_signals: 10,
        model_loaded: true,
        recent_report: true,
        timestamp: '2026-08-30T10:00:00Z',
      });

      const result = await (tool as any).execute({ operation: 'status' }, mockContext);

      expect(mockClient.getPlatformStatus).toHaveBeenCalledOnce();
      expect(mockClient.dataManager).not.toHaveBeenCalled();
      expect(result.status).toBe('success');
      expect(result.operation).toBe('status');
      expect(result.message).toContain('healthy');
      expect(result.message).toContain('已连接');
    });

    it('returns error when getPlatformStatus fails', async () => {
      mockClient.getPlatformStatus.mockRejectedValue(new Error('Connection refused'));

      const result = await (tool as any).execute({ operation: 'status' }, mockContext);

      expect(result.status).toBe('error');
      expect(result.message).toContain('Connection refused');
    });
  });

  describe('execute - non-status operations', () => {
    it('calls dataManager for refresh operation', async () => {
      mockClient.dataManager.mockResolvedValue({ success: true });

      const result = await (tool as any).execute({ operation: 'refresh', data_type: 'kline' }, mockContext);

      expect(mockClient.dataManager).toHaveBeenCalledOnce();
      expect(mockClient.getPlatformStatus).not.toHaveBeenCalled();
      expect(result.status).toBe('success');
      expect(result.operation).toBe('refresh');
    });

    it('sends correct params to dataManager', async () => {
      mockClient.dataManager.mockResolvedValue({ success: true });

      await (tool as any).execute({
        operation: 'refresh',
        data_type: 'quote',
        symbol: '600519',
        start_date: '2026-01-01',
        end_date: '2026-08-30',
      }, mockContext);

      expect(mockClient.dataManager).toHaveBeenCalledWith({
        source: 'quote',
        days: 30,
        force: false,
        async: true,
        symbols: '600519',
        start_date: '2026-01-01',
        end_date: '2026-08-30',
      });
    });
  });

  describe('wrap', () => {
    it('wraps success response correctly', () => {
      const data = { operation: 'status', status: 'success', message: 'ok' };
      const result = (tool as any).wrap(data, mockContext);
      expect(result.success).toBe(true);
      expect(result.metadata.operation).toBe('status');
    });

    it('wraps error response correctly', () => {
      const data = { operation: 'status', status: 'error', message: 'failed' };
      const result = (tool as any).wrap(data, mockContext);
      expect(result.success).toBe(false);
    });
  });
});
