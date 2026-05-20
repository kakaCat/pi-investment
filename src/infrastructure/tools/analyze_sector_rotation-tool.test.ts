import { describe, it, expect } from '@jest/globals';
import { analyze_sector_rotationTool } from './analyze_sector_rotation-tool.js';

describe('analyze_sector_rotationTool', () => {
  it('should execute successfully with valid params', async () => {
    const result = await (analyze_sector_rotationTool.execute as any)('test-id', {
      days: 7,
      sectorFlows: [
        { name: '半导体', netInflow: 2800000000, inflowPct: 3.5, changePct: 1.8, price: 1520 },
        { name: '人工智能', netInflow: 3200000000, inflowPct: 4.1, changePct: 2.2, price: 1288 },
        { name: '地产', netInflow: -1800000000, inflowPct: -2.6, changePct: -1.7, price: 645 },
        { name: '煤炭', netInflow: -2400000000, inflowPct: -3.2, changePct: -2.1, price: 715 },
      ],
    });

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.rotationStage).toBeDefined();
    expect(Array.isArray(result.details.topGainers)).toBe(true);
    expect(Array.isArray(result.details.topDecliners)).toBe(true);
  });

  it('should handle invalid params gracefully', async () => {
    const result = await (analyze_sector_rotationTool.execute as any)('test-id', {});
    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.usedDefaultData).toBe(true);
  });
});