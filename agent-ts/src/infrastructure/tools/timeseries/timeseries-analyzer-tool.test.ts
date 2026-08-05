/**
 * Timeseries Analyzer Tool - 测试文件
 */

import { describe, it, expect, beforeEach, jest } from '@jest/globals';

// ESM 下 jest.mock 不提升，必须 unstable_mockModule + 动态 import
const mockRunQuantV2 = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule('../../adapters/quant/quant-v2-client.js', () => ({
  runQuantV2: mockRunQuantV2,
}));

const { timeseriesAnalyzerTool } = await import('./timeseries-analyzer-tool.js');

describe('timeseries_analyzer tool', () => {
  beforeEach(() => {
    mockRunQuantV2.mockReset();
  });

  it('should have correct metadata', () => {
    expect(timeseriesAnalyzerTool.name).toBe('timeseries_analyzer');
    expect(timeseriesAnalyzerTool.label).toBe('时间序列分析');
    expect(timeseriesAnalyzerTool.description).toContain('时间序列分析工具');
  });

  it('should execute arima command', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      command: 'timeseries.arima',
      data: {
        predictions: [100, 101, 102, 103, 104],
        confidence_intervals: [[98, 102], [99, 103]]
      },
      error: null,
    } as any);

    const result = await timeseriesAnalyzerTool.execute('test', {
      command: 'arima',
      params: { symbol: '600519', periods: 5 }
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('命令执行成功');
    }
  });

  it('should pass action_type=forecast to backend path substitution for arima', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true, command: 'timeseries.arima', data: { predictions: [100] }, error: null,
    } as any);

    await timeseriesAnalyzerTool.execute('test', {
      command: 'arima',
      params: { symbol: '600519', periods: 5 }
    }, undefined, undefined, {} as any);

    // 后端路由为 /api/timeseries/arima/{action_type}，缺少 action_type 会 404
    expect(mockRunQuantV2).toHaveBeenCalledWith(
      'timeseries.arima',
      expect.objectContaining({ action_type: 'forecast' })
    );
  });

  it('should pass action_type=filter for kalman command', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true, command: 'timeseries.kalman', data: { filtered: [1, 2] }, error: null,
    } as any);

    await timeseriesAnalyzerTool.execute('test', {
      command: 'kalman',
      params: { symbol: '600519' }
    }, undefined, undefined, {} as any);

    expect(mockRunQuantV2).toHaveBeenCalledWith(
      'timeseries.kalman',
      expect.objectContaining({ action_type: 'filter' })
    );
  });

  it('should allow action_type override via params', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true, command: 'timeseries.arima', data: {}, error: null,
    } as any);

    await timeseriesAnalyzerTool.execute('test', {
      command: 'arima',
      params: { symbol: '600519', periods: 5, action_type: 'fit' }
    }, undefined, undefined, {} as any);

    expect(mockRunQuantV2).toHaveBeenCalledWith(
      'timeseries.arima',
      expect.objectContaining({ action_type: 'fit' })
    );
  });

  it('should execute garch command', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      command: 'timeseries.garch',
      data: {
        volatility_forecast: [0.02, 0.021, 0.019]
      },
      error: null,
    } as any);

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
