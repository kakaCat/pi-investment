import { describe, it, expect } from '@jest/globals';
import { calculate_rsiTool } from './calculate_rsi-tool.js';

describe('calculate_rsiTool', () => {
  it('should execute successfully with valid params', async () => {
    const result = await (calculate_rsiTool.execute as any)('test-id', {
      prices: [
        44.34, 44.09, 44.15, 43.61, 44.33,
        44.83, 45.1, 45.42, 45.84, 46.08,
        45.89, 46.03, 45.61, 46.28, 46.28,
        46.0, 46.03, 46.41,
      ],
      period: 14,
    });

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.success).toBe(true);
    expect(result.details.latestRsi).toEqual(expect.any(Number));
  });

  it('should handle invalid params gracefully', async () => {
    const result = await (calculate_rsiTool.execute as any)('test-id', {});

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.success).toBe(false);
  });
});