/**
 * Portfolio Rebalance Tool Tests - Business Logic Coverage
 */
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import { portfolioRebalanceTool } from './rebalance-tool.js';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'fs';
import { join } from 'path';

const TEST_PI_DIR = join(process.cwd(), '.pi-invest-test-portfolio');

// Helper to extract text from result
const getText = (result: any): string => {
  const content = result.content[0];
  return content.type === 'text' ? content.text : '';
};

describe('portfolioRebalanceTool - Tool Definition', () => {
  it('should have correct tool name', () => {
    expect(portfolioRebalanceTool.name).toBe('portfolio_rebalance');
  });

  it('should have correct label', () => {
    expect(portfolioRebalanceTool.label).toBe('组合再平衡');
  });

  it('should have description mentioning rebalancing', () => {
    expect(portfolioRebalanceTool.description).toContain('Rebalance');
    expect(portfolioRebalanceTool.description).toContain('portfolio');
  });

  it('should have parameters object', () => {
    expect(portfolioRebalanceTool.parameters).toBeDefined();
    expect(typeof portfolioRebalanceTool.parameters).toBe('object');
  });

  it('should have execute function', () => {
    expect(portfolioRebalanceTool.execute).toBeDefined();
    expect(typeof portfolioRebalanceTool.execute).toBe('function');
  });

  it('should support all actions from original tool', () => {
    const params = portfolioRebalanceTool.parameters as any;
    expect(params.properties).toBeDefined();
    expect(params.properties.action).toBeDefined();
  });
});

describe('portfolioRebalanceTool - Business Logic', () => {
  beforeEach(() => {
    // Create test directory
    if (!existsSync(TEST_PI_DIR)) {
      mkdirSync(TEST_PI_DIR, { recursive: true });
    }
    // Initialize empty portfolio.json
    writeFileSync(join(TEST_PI_DIR, 'portfolio.json'), JSON.stringify({ positions: [] }));
    // Initialize empty trades.json
    writeFileSync(join(TEST_PI_DIR, 'trades.json'), JSON.stringify({ trades: [] }));
  });

  afterEach(() => {
    // Clean up test directory
    if (existsSync(TEST_PI_DIR)) {
      rmSync(TEST_PI_DIR, { recursive: true, force: true });
    }
  });

  describe('action: get', () => {
    it('should return empty positions list', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'get'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(Array.isArray(response)).toBe(true);
    });
  });

  describe('action: get_with_pnl', () => {
    it('should return positions with P&L data structure', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'get_with_pnl'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response).toHaveProperty('summary');
      expect(response).toHaveProperty('positions');
    });
  });

  describe('action: add - A股', () => {
    it('should reject add without symbol', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'add',
        quantity: 100,
        avg_cost: 50
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('symbol');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject add without quantity', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'add',
        symbol: '600519',
        avg_cost: 50
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('quantity');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject add A-share without avg_cost', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'add',
        symbol: '600519',
        quantity: 100,
        market: 'A'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('avg_cost');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject negative quantity', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'add',
        symbol: '600519',
        quantity: -100,
        avg_cost: 50
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('数量');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject zero quantity', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'add',
        symbol: '600519',
        quantity: 0,
        avg_cost: 50
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('数量');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject negative avg_cost', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'add',
        symbol: '600519',
        quantity: 100,
        avg_cost: -50
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('成本价');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject zero avg_cost', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'add',
        symbol: '600519',
        quantity: 100,
        avg_cost: 0
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('成本价');
      expect(response._no_operation_performed).toBe(true);
    });
  });

  describe('action: add - 港股', () => {
    it('should reject HK stock without price_hkd', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'add',
        symbol: '09988',
        quantity: 100,
        market: 'HK'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('price_hkd');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject HK stock with negative price_hkd', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'add',
        symbol: '09988',
        quantity: 100,
        market: 'HK',
        price_hkd: -100
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('港币价格');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject HK stock with zero price_hkd', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'add',
        symbol: '09988',
        quantity: 100,
        market: 'HK',
        price_hkd: 0
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('港币价格');
      expect(response._no_operation_performed).toBe(true);
    });
  });

  describe('action: sell', () => {
    it('should reject sell without symbol', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'sell',
        quantity: 100,
        price: 60
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('symbol');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject sell without quantity', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'sell',
        symbol: '600519',
        price: 60
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('quantity');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject sell without price', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'sell',
        symbol: '600519',
        quantity: 100
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('price');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject sell with negative quantity', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'sell',
        symbol: '600519',
        quantity: -100,
        price: 60
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('卖出数量');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject sell with negative price', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'sell',
        symbol: '600519',
        quantity: 100,
        price: -60
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('卖出价格');
      expect(response._no_operation_performed).toBe(true);
    });
  });

  describe('action: update', () => {
    it('should reject update without symbol', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'update',
        quantity: 200
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('symbol');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject update with negative quantity', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'update',
        symbol: '600519',
        quantity: -200
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('数量');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should reject update with negative avg_cost', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'update',
        symbol: '600519',
        avg_cost: -55
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('成本价');
      expect(response._no_operation_performed).toBe(true);
    });
  });

  describe('action: remove', () => {
    it('should reject remove without symbol', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'remove'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('symbol');
      expect(response._no_operation_performed).toBe(true);
    });
  });

  describe('error handling', () => {
    it('should handle unknown action', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'invalid_action'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('未知操作');
      expect(response.valid_actions).toContain('get');
      expect(response._no_operation_performed).toBe(true);
    });

    it('should handle service errors gracefully', async () => {
      const result = await portfolioRebalanceTool.execute('test-id', {
        action: 'sell',
        symbol: 'NON_EXISTENT',
        quantity: 100,
        price: 60
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toBeDefined();
      expect(response._no_operation_performed).toBe(true);
    });
  });
});
