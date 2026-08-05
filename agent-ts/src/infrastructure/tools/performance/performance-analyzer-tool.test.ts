/**
 * Performance Analyzer Tool - 测试文件
 */

import { describe, it, expect, jest } from '@jest/globals';

const mockRunQuantV2 = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule('../../adapters/quant/quant-v2-client.js', () => ({
  runQuantV2: mockRunQuantV2,
}));

const { performanceAnalyzerTool } = await import('./performance-analyzer-tool.js');

describe('performance_analyzer tool', () => {
  it('should have correct metadata', () => {
    expect(performanceAnalyzerTool.name).toBe('performance_analyzer');
    expect(performanceAnalyzerTool.label).toBe('性能分析');
    expect(performanceAnalyzerTool.description).toContain('性能分析工具');
  });

  it('should execute by_strategy command', async () => {
    const mockResult = {
      ok: true,
      command: 'performance.by-strategy',
      data: {
        total_return: 0.25,
        sharpe_ratio: 1.5,
        max_drawdown: -0.15
      },
      error: null,
    };

    mockRunQuantV2.mockResolvedValue(mockResult);

    const result = await performanceAnalyzerTool.execute('test', {
      command: 'by_strategy',
      params: { strategy_id: 'rsi-strategy' }
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('命令执行成功');
      expect((content as any).text).toContain('total_return');
    }
  });

  it('should execute comparison command', async () => {
    const mockResult = {
      ok: true,
      command: 'performance.comparison',
      data: {
        strategies: [
          { id: 'rsi-strategy', return: 0.25 },
          { id: 'macd-strategy', return: 0.18 }
        ]
      },
      error: null,
    };

    mockRunQuantV2.mockResolvedValue(mockResult);

    const result = await performanceAnalyzerTool.execute('test', {
      command: 'comparison',
      params: {}
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('命令执行成功');
    }
  });

  it('should reject invalid command', async () => {
    const result = await performanceAnalyzerTool.execute('test', {
      command: 'invalid_command',
      params: {}
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('未知命令');
    }
  });
});
