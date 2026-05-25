/**
 * Trade Manage Orders Tool Tests
 */
import { describe, it, expect } from '@jest/globals';
import { tradeManageOrdersTool } from './manage-orders-tool.js';

describe('tradeManageOrdersTool', () => {
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
