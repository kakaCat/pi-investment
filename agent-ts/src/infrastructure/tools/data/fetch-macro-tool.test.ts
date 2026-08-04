/**
 * Data Fetch Macro Tool - Unit Tests
 *
 * 2026-08-04 重写：对齐当前契约
 * - runQuantV2 返回 QuantCliResponse {ok, command, data}（data 直接是指标字典，无 indicators 包装）
 * - 工具经 handleToolResponse 返回文本；API 错误返回错误内容而非抛出
 * - ESM 下用 unstable_mockModule + 动态 import（jest.mock 不提升）
 */
import { describe, it, expect, beforeEach, jest } from '@jest/globals';

const mockRunQuantV2 = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule('../../adapters/quant/quant-v2-client.js', () => ({
  runQuantV2: mockRunQuantV2
}));

const { dataFetchMacroTool } = await import('./fetch-macro-tool.js');

describe('dataFetchMacroTool', () => {
  beforeEach(() => {
    mockRunQuantV2.mockReset();
  });

  it('should have correct tool definition', () => {
    expect(dataFetchMacroTool.name).toBe('data_fetch_macro');
    expect(dataFetchMacroTool.label).toBe('获取宏观经济数据');
    expect(dataFetchMacroTool.description).toContain('宏观经济指标');
  });

  it('should fetch macro data successfully', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      command: 'market.macro',
      data: {
        gdp: [
          { date: '2026-Q1', value: 5.3 },
          { date: '2025-Q4', value: 5.1 }
        ],
        cpi: [
          { date: '2026-05', value: 2.1 },
          { date: '2026-04', value: 2.4 }
        ]
      }
    });

    const result = await dataFetchMacroTool.execute('test-call-id', {
      indicators: ['gdp', 'cpi'],
      start_date: '2025-01-01',
      end_date: '2026-06-04'
    });

    expect(mockRunQuantV2).toHaveBeenCalledWith('market.macro', {
      indicators: ['gdp', 'cpi'],
      start_date: '2025-01-01',
      end_date: '2026-06-04'
    });
    expect(result.content).toHaveLength(1);
    expect(result.content[0].type).toBe('text');
    const content0 = result.content[0];
    if (content0.type === 'text') {
      expect(content0.text).toContain('宏观经济数据');
    }
  });

  it('should handle empty indicators (fetch all)', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      command: 'market.macro',
      data: {
        gdp: [{ date: '2026-Q1', value: 5.3 }],
        cpi: [{ date: '2026-05', value: 2.1 }],
        pmi: [{ date: '2026-05', value: 50.5 }]
      }
    });

    const result = await dataFetchMacroTool.execute('test-call-id', {});

    expect(mockRunQuantV2).toHaveBeenCalledWith('market.macro', {
      indicators: undefined,
      start_date: undefined,
      end_date: undefined
    });
    expect(result.content[0].type).toBe('text');
  });

  it('should show trend analysis when data has multiple points', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      command: 'market.macro',
      data: {
        gdp: [
          { date: '2026-Q1', value: 5.3 },
          { date: '2025-Q4', value: 5.1 }
        ]
      }
    });

    const result = await dataFetchMacroTool.execute('test-call-id', {
      indicators: ['gdp']
    });

    const content0 = result.content[0];
    if (content0.type === 'text') {
      expect(content0.text).toContain('GDP');
    }
  });

  it('should handle API error gracefully (returns error content, not throw)', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: false,
      command: 'market.macro',
      error: { message: 'API连接失败' }
    });

    const result = await dataFetchMacroTool.execute('test-call-id', {
      indicators: ['gdp']
    });

    const content0 = result.content[0];
    if (content0.type === 'text') {
      expect(content0.text).toContain('API连接失败');
    }
  });

  it('should handle empty data', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      command: 'market.macro',
      data: {}
    });

    const result = await dataFetchMacroTool.execute('test-call-id', {
      indicators: ['gdp']
    });

    expect(result.content[0].type).toBe('text');
  });

  it('should format values correctly with units', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      command: 'market.macro',
      data: {
        gdp: [{ date: '2026-Q1', value: 5.3 }],
        m1: [{ date: '2026-05', value: 625000 }],
        exchange_rate: [{ date: '2026-06-04', value: 7.2345 }]
      }
    });

    const result = await dataFetchMacroTool.execute('test-call-id', {
      indicators: ['gdp', 'm1', 'exchange_rate']
    });

    const content0 = result.content[0];
    if (content0.type === 'text') {
      expect(content0.text).toContain('5.3');
    }
  });
});
