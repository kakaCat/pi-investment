import { describe, it, expect } from '@jest/globals';
import { check_stop_loss_triggerTool } from './check_stop_loss_trigger-tool.js';

describe('check_stop_loss_triggerTool', () => {
  it('should execute successfully with valid params', async () => {
    const result = await (check_stop_loss_triggerTool.execute as any)('test-id', {
      symbol: '600519',
      name: '贵州茅台',
      currentPrice: 94,
      costPrice: 100,
      quantity: 200,
      stopLossPct: 8,
    });

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.status).toBe('warning');
  });

  it('should handle invalid params gracefully', async () => {
    const result = await (check_stop_loss_triggerTool.execute as any)('test-id', {});
    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.status).toBe('invalid');
  });
});