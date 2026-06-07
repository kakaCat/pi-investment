/**
 * Trade Monitor Tool - 测试文件
 */

import { describe, it, expect, vi } from 'vitest';
import { tradeMonitorTool } from './trade-monitor-tool.js';
import * as quantV2Client from '../../adapters/quant/quant-v2-client.js';

vi.mock('../../adapters/quant/quant-v2-client.js');

describe('trade_monitor tool', () => {
  it('should have correct metadata', () => {
    expect(tradeMonitorTool.name).toBe('trade_monitor');
    expect(tradeMonitorTool.label).toBe('交易监控');
    expect(tradeMonitorTool.description).toContain('交易监控工具');
  });

  it('should execute orders command', async () => {
    const mockResult = {
      ok: true,
      command: 'orders.list',
      data: { orders: [{ order_id: '123', symbol: '600519' }] },
      error: null,
    };

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

    const result = await tradeMonitorTool.execute('test', {
      command: 'orders',
      params: {}
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('命令执行成功');
    }
  });

  it('should execute stats command', async () => {
    const mockResult = {
      ok: true,
      command: 'executions.stats',
      data: { success_rate: 0.95, avg_latency: 100 },
      error: null,
    };

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

    const result = await tradeMonitorTool.execute('test', {
      command: 'stats',
      params: {}
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('命令执行成功');
    }
  });

  it('should reject invalid command', async () => {
    const result = await tradeMonitorTool.execute('test', {
      command: 'invalid_command',
      params: {}
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('未知命令');
    }
  });
});
