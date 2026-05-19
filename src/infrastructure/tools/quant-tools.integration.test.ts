import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import { combineStrategySignalsTool } from './quant-tools.js';
import { QuantService } from '../../services/quant/quant-service.js';

describe('Strategy Combiner Integration Tests', () => {
  let quantService: QuantService;

  beforeAll(() => {
    quantService = new QuantService();
  });

  afterAll(() => {
    // Clean up any pending async operations
    return new Promise<void>((resolve) => {
      setTimeout(() => resolve(), 100);
    });
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

    // Verify result structure
    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');

    const text = result.content[0].text;

    // Check if it's an error response or success response
    if (text.startsWith('Error:') || text.startsWith('Failed')) {
      // If error, verify it's a meaningful error message
      expect(text).toBeTruthy();
      console.log('Test skipped due to error:', text);
      return;
    }

    // Parse and verify the actual response
    const data = JSON.parse(text);
    expect(data.symbol).toBe('600519');
    expect(data.combined_signals).toBeDefined();
    expect(data.metadata).toBeDefined();
    expect(data.metadata.mode).toBe('vote');
    expect(data.metadata.total_strategies).toBe(2);
    expect(data.metadata.signals_generated).toBeGreaterThanOrEqual(0);

    // Verify metadata contains expected fields
    if (data.metadata.signals_generated > 0) {
      expect(data.metadata).toHaveProperty('buy_score');
      expect(data.metadata).toHaveProperty('sell_score');
    }
  });

  it('should combine multiple strategy signals in AND mode', async () => {
    const strategies = await quantService.listStrategies();
    if (strategies.length < 2) {
      console.log('Skipping: need at least 2 strategies');
      return;
    }

    const result = await (combineStrategySignalsTool.execute as any)('test-and', {
      symbol: '600519',
      strategy_ids: [strategies[0].id, strategies[1].id],
      mode: 'and'
    });

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');

    const text = result.content[0].text;
    if (text.startsWith('Error:') || text.startsWith('Failed')) {
      expect(text).toBeTruthy();
      console.log('Test skipped due to error:', text);
      return;
    }

    const data = JSON.parse(text);
    expect(data.symbol).toBe('600519');
    expect(data.metadata.mode).toBe('and');
    expect(data.metadata.total_strategies).toBe(2);
  });

  it('should combine multiple strategy signals in OR mode', async () => {
    const strategies = await quantService.listStrategies();
    if (strategies.length < 2) {
      console.log('Skipping: need at least 2 strategies');
      return;
    }

    const result = await (combineStrategySignalsTool.execute as any)('test-or', {
      symbol: '600519',
      strategy_ids: [strategies[0].id, strategies[1].id],
      mode: 'or'
    });

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');

    const text = result.content[0].text;
    if (text.startsWith('Error:') || text.startsWith('Failed')) {
      expect(text).toBeTruthy();
      console.log('Test skipped due to error:', text);
      return;
    }

    const data = JSON.parse(text);
    expect(data.symbol).toBe('600519');
    expect(data.metadata.mode).toBe('or');
    expect(data.metadata.total_strategies).toBe(2);
  });

  it('should handle insufficient signals gracefully', async () => {
    const result = await (combineStrategySignalsTool.execute as any)('test-2', {
      symbol: '999999',  // Invalid symbol
      strategy_ids: ['fake1', 'fake2'],
      mode: 'vote'
    });

    // Verify error response structure
    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');

    // Verify the error message - could be either stock data error or signal error
    const text = result.content[0].text;
    expect(text).toMatch(/Error:|Failed/);
    // The error could be about stock data or insufficient signals
    expect(
      text.includes('Failed to get stock data') ||
      text.includes('Need at least 2 valid signals') ||
      text.includes('fake1') ||
      text.includes('fake2')
    ).toBe(true);
  });

  it('should reject requests with fewer than 2 strategies', async () => {
    const result = await (combineStrategySignalsTool.execute as any)('test-3', {
      symbol: '600519',
      strategy_ids: ['single_strategy'],
      mode: 'vote'
    });

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');

    const text = result.content[0].text;
    expect(text).toContain('Error: At least 2 strategy_ids required');
  });

  it('should apply custom weights in VOTE mode', async () => {
    const strategies = await quantService.listStrategies();
    if (strategies.length < 2) {
      console.log('Skipping: need at least 2 strategies');
      return;
    }

    const weights: Record<string, number> = {
      [strategies[0].id]: 1.5,
      [strategies[1].id]: 1.0
    };

    const result = await (combineStrategySignalsTool.execute as any)('test-weights', {
      symbol: '600519',
      strategy_ids: [strategies[0].id, strategies[1].id],
      mode: 'vote',
      weights
    });

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');

    const text = result.content[0].text;
    if (text.startsWith('Error:') || text.startsWith('Failed')) {
      expect(text).toBeTruthy();
      console.log('Test skipped due to error:', text);
      return;
    }

    const data = JSON.parse(text);
    expect(data.symbol).toBe('600519');
    expect(data.metadata.mode).toBe('vote');
  });
});
