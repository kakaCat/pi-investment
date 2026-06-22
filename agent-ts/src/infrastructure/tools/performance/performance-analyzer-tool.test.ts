/**
 * Performance Analyzer Tool - 测试文件
 */

import { describe, it, expect, vi } from 'vitest';
import { performanceAnalyzerTool } from './performance-analyzer-tool.js';
import * as quantV2Client from '../../adapters/quant/quant-v2-client.js';

vi.mock('../../adapters/quant/quant-v2-client.js');

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

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

    const result = await performanceAnalyzerTool.execute('test', {
      command: 'by_strategy',
      params: { strategy_id: 'rsi-strategy' }
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('命令执行成功');
      expect(content.text).toContain('total_return');
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

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

    const result = await performanceAnalyzerTool.execute('test', {
      command: 'comparison',
      params: {}
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('命令执行成功');
    }
  });

  it('should reject invalid command', async () => {
    const result = await performanceAnalyzerTool.execute('test', {
      command: 'invalid_command',
      params: {}
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('未知命令');
    }
  });
});
