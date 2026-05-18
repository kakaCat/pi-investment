import { describe, it, expect, beforeAll } from '@jest/globals';
import { combineStrategySignalsTool } from './quant-tools.js';
import { QuantService } from '../../services/quant/quant-service.js';

describe('Strategy Combiner Integration Tests', () => {
  let quantService: QuantService;

  beforeAll(() => {
    quantService = new QuantService();
  });

  it('should combine multiple strategy signals in VOTE mode', async () => {
    // This test requires real strategies to be set up
    // Skip if strategies don't exist
    const strategies = await quantService.listStrategies();
    if (strategies.length < 2) {
      console.log('Skipping: need at least 2 strategies');
      return;
    }

    const result = await (combineStrategySignalsTool.execute as any)('test-1', {
      symbol: '600519',
      strategy_ids: [strategies[0].id, strategies[1].id],
      mode: 'vote'
    });

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
  });

  it('should handle insufficient signals gracefully', async () => {
    const result = await (combineStrategySignalsTool.execute as any)('test-2', {
      symbol: '999999',  // Invalid symbol
      strategy_ids: ['fake1', 'fake2'],
      mode: 'vote'
    });

    expect(result.content).toBeDefined();
  });
});
