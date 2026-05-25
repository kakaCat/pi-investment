/**
 * Trade Manage Orders Tool Tests - Business Logic Coverage
 */
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import { tradeManageOrdersTool } from './manage-orders-tool.js';
import { OrderService } from '../../../services/order-service.js';
import { PortfolioService } from '../../../services/portfolio/portfolio-service.js';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'fs';
import { join } from 'path';

const TEST_PI_DIR = join(process.cwd(), '.pi-invest-test-orders');

// Helper to extract text from result
const getText = (result: any): string => {
  const content = result.content[0];
  return content.type === 'text' ? content.text : '';
};

describe('tradeManageOrdersTool - Tool Definition', () => {
  it('should have correct tool name', () => {
    expect(tradeManageOrdersTool.name).toBe('trade_manage_orders');
  });

  it('should have correct label', () => {
    expect(tradeManageOrdersTool.label).toBe('管理交易订单');
  });

  it('should have description mentioning trade orders', () => {
    expect(tradeManageOrdersTool.description).toContain('交易订单管理');
    expect(tradeManageOrdersTool.description).toContain('place');
    expect(tradeManageOrdersTool.description).toContain('cancel');
  });

  it('should have parameters object', () => {
    expect(tradeManageOrdersTool.parameters).toBeDefined();
    expect(typeof tradeManageOrdersTool.parameters).toBe('object');
  });

  it('should have execute function', () => {
    expect(tradeManageOrdersTool.execute).toBeDefined();
    expect(typeof tradeManageOrdersTool.execute).toBe('function');
  });

  it('should support all actions from original tool', () => {
    const params = tradeManageOrdersTool.parameters as any;
    expect(params.properties).toBeDefined();
    expect(params.properties.action).toBeDefined();
  });
});

describe('tradeManageOrdersTool - Business Logic', () => {
  beforeEach(() => {
    // Create test directory
    if (!existsSync(TEST_PI_DIR)) {
      mkdirSync(TEST_PI_DIR, { recursive: true });
    }
    // Initialize empty orders.json
    writeFileSync(join(TEST_PI_DIR, 'orders.json'), JSON.stringify({ orders: [] }));
  });

  afterEach(() => {
    // Clean up test directory
    if (existsSync(TEST_PI_DIR)) {
      rmSync(TEST_PI_DIR, { recursive: true, force: true });
    }
  });

  describe('action: place', () => {
    it('should create order with valid parameters', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'place',
        symbol: '600519',
        name: '贵州茅台',
        side: 'buy',
        type: 'limit',
        price: 1800,
        quantity: 100,
        market: 'A'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('挂单已创建');
      expect(text).toContain('贵州茅台');
      expect(text).toContain('600519');
      expect((result.details as any)?.action).toBe('place');
    });

    it('should reject place without symbol', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'place',
        name: '测试股票',
        side: 'buy',
        price: 50,
        quantity: 100
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('symbol 不能为空');
      expect((result.details as any)?.error).toContain('missing symbol');
    });

    it('should reject place without name', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'place',
        symbol: '600519',
        side: 'buy',
        price: 50,
        quantity: 100
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('name 不能为空');
      expect((result.details as any)?.error).toContain('missing name');
    });

    it('should reject place without side', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'place',
        symbol: '600519',
        name: '贵州茅台',
        price: 50,
        quantity: 100
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('side');
      expect((result.details as any)?.error).toContain('missing side');
    });

    it('should reject place with invalid side', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'place',
        symbol: '600519',
        name: '贵州茅台',
        side: 'invalid',
        price: 50,
        quantity: 100
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('side 无效');
      expect((result.details as any)?.error).toContain('invalid side');
    });

    it('should reject place with invalid price', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'place',
        symbol: '600519',
        name: '贵州茅台',
        side: 'buy',
        price: -10,
        quantity: 100
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('price 必须大于0');
      expect((result.details as any)?.error).toContain('invalid price');
    });

    it('should reject place with invalid quantity', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'place',
        symbol: '600519',
        name: '贵州茅台',
        side: 'buy',
        price: 50,
        quantity: 0
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('quantity 必须大于0');
      expect((result.details as any)?.error).toContain('invalid quantity');
    });

    it('should reject place with invalid expires_in_minutes', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'place',
        symbol: '600519',
        name: '贵州茅台',
        side: 'buy',
        price: 50,
        quantity: 100,
        expires_in_minutes: -5
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('expires_in_minutes 必须大于0');
      expect((result.details as any)?.error).toContain('invalid expires_in_minutes');
    });

    it('should create stop loss order', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'place',
        symbol: '600519',
        name: '贵州茅台',
        side: 'sell',
        type: 'stop_loss',
        price: 1620,
        quantity: 100,
        market: 'A'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('挂单已创建');
      expect(text).toContain('止损');
    });
  });

  describe('action: cancel', () => {
    it('should reject cancel without order_id', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'cancel'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('order_id 不能为空');
      expect((result.details as any)?.error).toContain('missing order_id');
    });

    it('should reject cancel for non-existent order', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'cancel',
        order_id: 'non-existent-id'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('未找到挂单');
    });
  });

  describe('action: list', () => {
    it('should list empty orders', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'list'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('当前无');
      expect(text).toContain('挂单');
    });

    it('should list orders with filter', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'list',
        status: 'pending'
      }, undefined, undefined, {} as any);

      expect((result.details as any)?.action).toBe('list');
    });
  });

  describe('action: fill', () => {
    it('should reject fill without order_id', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'fill',
        fill_price: 50
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('order_id 不能为空');
      expect((result.details as any)?.error).toContain('missing order_id');
    });

    it('should reject fill without fill_price', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'fill',
        order_id: 'test-order-id'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('fill_price 必须大于0');
      expect((result.details as any)?.error).toContain('invalid fill_price');
    });

    it('should reject fill with invalid fill_price', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'fill',
        order_id: 'test-order-id',
        fill_price: -10
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('fill_price 必须大于0');
      expect((result.details as any)?.error).toContain('invalid fill_price');
    });

    it('should reject fill with invalid fill_quantity', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'fill',
        order_id: 'test-order-id',
        fill_price: 50,
        fill_quantity: 0
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('fill_quantity 必须大于0');
      expect((result.details as any)?.error).toContain('invalid fill_quantity');
    });
  });

  describe('action: check', () => {
    it('should check orders without symbol filter', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'check'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('挂单检查报告');
      expect((result.details as any)?.action).toBe('check');
    });

    it('should check orders with dry_run mode', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'check',
        dry_run: true
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('试运行模式');
      expect((result.details as any)?.dry_run).toBe(true);
    });

    it('should check orders for specific symbol', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'check',
        symbol: '600519'
      }, undefined, undefined, {} as any);

      expect((result.details as any)?.symbol).toBe('600519');
    });
  });

  describe('error handling', () => {
    it('should handle unknown action', async () => {
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'invalid_action'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('未知操作');
      expect(text).toContain('invalid_action');
      expect((result.details as any)?.error).toContain('unknown action');
    });

    it('should handle service errors gracefully', async () => {
      // Force an error by providing malformed data
      const result = await tradeManageOrdersTool.execute('test-id', {
        action: 'place',
        symbol: '600519',
        name: '贵州茅台',
        side: 'buy',
        price: null, // This will trigger validation error
        quantity: 100
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('price');
    });
  });
});
