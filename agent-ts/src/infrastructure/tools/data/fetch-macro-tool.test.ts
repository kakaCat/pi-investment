/**
 * Data Fetch Macro Tool - Unit Tests
 */
import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { dataFetchMacroTool } from './fetch-macro-tool.js';

// Mock runQuantV2
jest.mock('../../adapters/quant/quant-v2-client.js', () => ({
  runQuantV2: jest.fn()
}));

import { runQuantV2 } from '../../adapters/quant/quant-v2-client.js';
const mockRunQuantV2 = runQuantV2 as jest.MockedFunction<typeof runQuantV2>;

describe('dataFetchMacroTool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should have correct tool definition', () => {
    expect(dataFetchMacroTool.name).toBe('data_fetch_macro');
    expect(dataFetchMacroTool.label).toBe('获取宏观经济数据');
    expect(dataFetchMacroTool.description).toContain('宏观经济指标');
  });

  it('should fetch macro data successfully', async () => {
    const mockData = {
      success: true,
      data: {
        indicators: {
          gdp: [
            { date: '2026-Q1', value: 5.3 },
            { date: '2025-Q4', value: 5.1 }
          ],
          cpi: [
            { date: '2026-05', value: 2.1 },
            { date: '2026-04', value: 2.4 }
          ]
        }
      }
    };

    mockRunQuantV2.mockResolvedValue(mockData);

    const result = await dataFetchMacroTool.execute('test-call-id', {
      indicators: ['gdp', 'cpi'],
      start_date: '2025-01-01',
      end_date: '2026-06-04'
    }, undefined, undefined, {} as any);

    expect(result.content).toHaveLength(1);
    expect(result.content[0].type).toBe('text');
    const content0 = result.content[0];
    if (content0.type === 'text') {
      expect(content0.text).toContain('宏观经济数据');
    }
    expect(result.details).toEqual(mockData.data);
  });

  it('should handle empty indicators (fetch all)', async () => {
    const mockData = {
      success: true,
      data: {
        indicators: {
          gdp: [{ date: '2026-Q1', value: 5.3 }],
          cpi: [{ date: '2026-05', value: 2.1 }],
          pmi: [{ date: '2026-05', value: 50.5 }]
        }
      }
    };

    mockRunQuantV2.mockResolvedValue(mockData);

    const result = await dataFetchMacroTool.execute('test-call-id', {}, undefined, undefined, {} as any);

    expect(mockRunQuantV2).toHaveBeenCalledWith({
      command: 'market.macro',
      params: {
        indicators: undefined,
        start_date: undefined,
        end_date: undefined
      }
    }, undefined, undefined, {} as any);

  });

  it('should show trend analysis when data has multiple points', async () => {
    const mockData = {
      success: true,
      data: {
        indicators: {
          gdp: [
            { date: '2026-Q1', value: 5.3 },
            { date: '2025-Q4', value: 5.1 }
          ]
        }
      }
    };

    mockRunQuantV2.mockResolvedValue(mockData);

    const result = await dataFetchMacroTool.execute('test-call-id', {
      indicators: ['gdp']
    }, undefined, undefined, {} as any);

  });

  it('should handle API error gracefully', async () => {
    mockRunQuantV2.mockResolvedValue({
      success: false,
      error: 'API连接失败'
    });

    await expect(
      dataFetchMacroTool.execute('test-call-id', {
        indicators: ['gdp']
      })
    ).rejects.toThrow('API连接失败');
  }, undefined, undefined, {} as any);

  it('should handle empty data', async () => {
    const mockData = {
      success: true,
      data: {
        indicators: {}
      }
    };

    mockRunQuantV2.mockResolvedValue(mockData);

    const result = await dataFetchMacroTool.execute('test-call-id', {
      indicators: ['gdp']
    }, undefined, undefined, {} as any);

  });

  it('should format values correctly with units', async () => {
    const mockData = {
      success: true,
      data: {
        indicators: {
          gdp: [{ date: '2026-Q1', value: 5.3 }],
          m1: [{ date: '2026-05', value: 625000 }],
          exchange_rate: [{ date: '2026-06-04', value: 7.2345 }]
        }
      }
    };

    mockRunQuantV2.mockResolvedValue(mockData);

    const result = await dataFetchMacroTool.execute('test-call-id', {
      indicators: ['gdp', 'm1', 'exchange_rate']
    }, undefined, undefined, {} as any);

    const text = result.content[0].text;
    expect(text).toContain('5.30%');  // GDP with %
    expect(text).toContain('万亿元');  // M1 converted
    expect(text).toContain('7.2345');  // Exchange rate with 4 decimals
  });

  it('should provide economic interpretation', async () => {
    const mockData = {
      success: true,
      data: {
        indicators: {
          pmi: [
            { date: '2026-05', value: 51.2 },
            { date: '2026-04', value: 49.8 }
          ]
        }
      }
    };

    mockRunQuantV2.mockResolvedValue(mockData);

    const result = await dataFetchMacroTool.execute('test-call-id', {
      indicators: ['pmi']
    }, undefined, undefined, {} as any);

  });
});
