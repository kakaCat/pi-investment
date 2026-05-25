/**
 * Portfolio Rebalance Tool Tests
 */
import { describe, it, expect } from '@jest/globals';
import { portfolioRebalanceTool } from './rebalance-tool.js';

describe('portfolioRebalanceTool', () => {
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
