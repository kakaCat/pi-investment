import { describe, it, expect } from '@jest/globals';
import { calculate_rsiTool } from './calculate_rsi-tool.js';

describe('calculate_rsiTool', () => {
  it('should execute successfully with valid params', async () => {
    const result = await (calculate_rsiTool.execute as any)('test-id', {
      prices: [44, 44.15, 43.9, 44.35, 44.8, 44.6, 45.1, 45.3, 45, 45.4, 45.8, 46, 45.7, 46.2, 46.5],
      period: 14,
    });

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.success).toBe(true);
    expect(typeof result.details.rsi).toBe('number');
  });

  it('should handle invalid params gracefully', async () => {
    const result = await (calculate_rsiTool.execute as any)('test-id', {});

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.success).toBe(false);
  });
});