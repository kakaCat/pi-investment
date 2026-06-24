/**
 * Timeseries Analyzer Tool - 测试文件
 */

import { describe, it, expect, jest } from '@jest/globals';
import { vi } from 'vitest';
import { timeseriesAnalyzerTool } from './timeseries-analyzer-tool.js';
import * as quantV2Client from '../../adapters/quant/quant-v2-client.js';

jest.mock('../../adapters/quant/quant-v2-client.js');

describe('timeseries_analyzer tool', () => {
  it('should have correct metadata', () => {
    expect(timeseriesAnalyzerTool.name).toBe('timeseries_analyzer');
    expect(timeseriesAnalyzerTool.label).toBe('时间序列分析');
    expect(timeseriesAnalyzerTool.description).toContain('时间序列分析工具');
  });

  it('should execute arima command', async () => {
    const mockResult = {
      ok: true,
      command: 'timeseries.arima',
      data: {
        predictions: [100, 101, 102, 103, 104],
        confidence_intervals: [[98, 102], [99, 103]]
      },
      error: null,
    };

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

    const result = await timeseriesAnalyzerTool.execute('test', {
      command: 'arima',
      params: { symbol: '600519', periods: 5 }
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('命令执行成功');
    }
  });

  it('should execute garch command', async () => {
    const mockResult = {
      ok: true,
      command: 'timeseries.garch',
      data: {
        volatility_forecast: [0.02, 0.021, 0.019]
      },
      error: null,
    };

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

    const result = await timeseriesAnalyzerTool.execute('test', {
      command: 'garch',
      params: { symbol: '600519', periods: 3 }
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('命令执行成功');
    }
  });

  it('should reject invalid command', async () => {
    const result = await timeseriesAnalyzerTool.execute('test', {
      command: 'invalid_command',
      params: {}
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('未知命令');
    }
  });

  it('should validate required params', async () => {
    const result = await timeseriesAnalyzerTool.execute('test', {
      command: 'arima',
      params: {} // missing required 'symbol'
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('参数');
    }
  });
});
