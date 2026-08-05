/**
 * Portfolio Optimizer Tool - 测试文件
 */

import { describe, it, expect, jest } from '@jest/globals';

const mockRunQuantV2 = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule('../../adapters/quant/quant-v2-client.js', () => ({
  runQuantV2: mockRunQuantV2,
}));

const { portfolioOptimizerTool } = await import('./portfolio-optimizer-tool.js');

describe('portfolio_optimizer tool', () => {
  it('should have correct metadata', () => {
    expect(portfolioOptimizerTool.name).toBe('portfolio_optimizer');
    expect(portfolioOptimizerTool.label).toBe('组合优化');
    expect(portfolioOptimizerTool.description).toContain('组合优化工具');
  });

  it('should execute optimize command', async () => {
    const mockResult = {
      ok: true,
      command: 'portfolio.optimize',
      data: {
        weights: { '600000': 0.3, '000001': 0.3, '600519': 0.4 },
        expected_return: 0.15,
        risk: 0.10
      },
      error: null,
    };

    mockRunQuantV2.mockResolvedValue(mockResult);

    const result = await portfolioOptimizerTool.execute('test', {
      command: 'optimize',
      params: {
        symbols: ['600000', '000001', '600519'],
        method: 'max_sharpe'
      }
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('命令执行成功');
      expect((content as any).text).toContain('weights');
    }
  });

  it('should execute correlation command', async () => {
    const mockResult = {
      ok: true,
      command: 'portfolio.correlation',
      data: {
        correlation_matrix: [[1.0, 0.5], [0.5, 1.0]]
      },
      error: null,
    };

    mockRunQuantV2.mockResolvedValue(mockResult);

    const result = await portfolioOptimizerTool.execute('test', {
      command: 'correlation',
      params: {
        symbols: ['600000', '000001']
      }
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('命令执行成功');
    }
  });

  it('should reject invalid command', async () => {
    const result = await portfolioOptimizerTool.execute('test', {
      command: 'invalid_command',
      params: {}
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('未知命令');
    }
  });

  it('should validate required params', async () => {
    const result = await portfolioOptimizerTool.execute('test', {
      command: 'optimize',
      params: {} // missing required 'symbols'
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('参数');
    }
  });
});
