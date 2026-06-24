/**
 * 测试 strategy_optimize 工具
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';

// Mock fetch
const mockFetch = jest.fn<typeof fetch>();
global.fetch = mockFetch as any;

const { strategyOptimizeTool } = await import('./optimize-tool.js');

describe('strategy_optimize tool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should have correct tool definition', () => {
    expect(strategyOptimizeTool.name).toBe('strategy_optimize');
    expect(strategyOptimizeTool.description).toContain('参数优化');
    expect(strategyOptimizeTool.parameters).toBeDefined();
  });

  it('should call v2 API with correct parameters', async () => {
    const mockResponse = {
      success: true,
      results: [
        {
          params: { rsi_low: 30, rsi_high: 70 },
          sharpeRatio: 2.15,
          totalReturn: 0.23,
          maxDrawdown: -0.08,
          winRate: 0.62,
          totalTrades: 50,
        },
      ],
      totalCombinations: 4,
      successfulCombinations: 4,
    };

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const result = await (strategyOptimizeTool.execute as any)(
      'test-id',
      {
        strategy_id: 1,
        symbol: '600519.SH',
        start_date: '2025-01-01',
        end_date: '2025-12-31',
        metric: 'sharpe',
        param_grid: { rsi_low: [25, 30], rsi_high: [70, 75] },
      },
      undefined,
      undefined,
      {}
    );

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/strategies/optimize'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"strategyId":1'),
      })
    );

    expect(result.content[0]).toHaveProperty('type', 'text');
    if (result.content[0].type === 'text') {
      const content0 = result.content[0];
      if (content0.type === 'text') {
        expect(content0.text).toContain('最优参数');
      }
      const content0 = result.content[0];
      if (content0.type === 'text') {
        expect(content0.text).toContain('rsi_low: 30');
      }
      const content0 = result.content[0];
      if (content0.type === 'text') {
        expect(content0.text).toContain('2.15');
      }
    }
  });

  it('should validate required parameters', async () => {
    const result = await (strategyOptimizeTool.execute as any)(
      'test-id',
      {
        symbol: '600519.SH',
        param_grid: { rsi_low: [30] },
      },
      undefined,
      undefined,
      {}
    );

    expect(result.content[0]).toHaveProperty('type', 'text');
    if (result.content[0].type === 'text') {
      const content0 = result.content[0];
      if (content0.type === 'text') {
        expect(content0.text).toContain('strategy_id');
      }
    }
  });

  it('should handle API errors gracefully', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: false,
        error: '参数组合过多',
      }),
    } as Response);

    const result = await (strategyOptimizeTool.execute as any)(
      'test-id',
      {
        strategy_id: 1,
        symbol: '600519.SH',
        param_grid: { p1: [1, 2, 3], p2: [1, 2, 3] },
      },
      undefined,
      undefined,
      {}
    );

    expect(result.content[0]).toHaveProperty('type', 'text');
    if (result.content[0].type === 'text') {
      const content0 = result.content[0];
      if (content0.type === 'text') {
        expect(content0.text).toContain('失败');
      }
      const content0 = result.content[0];
      if (content0.type === 'text') {
        expect(content0.text).toContain('参数组合过多');
      }
    }
  });

  it('should support optional parameters', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        results: [
          {
            params: { rsi_low: 30 },
            sharpeRatio: 1.5,
            totalReturn: 0.15,
            winRate: 0.55,
          }
        ],
        totalCombinations: 1,
        successfulCombinations: 1,
      }),
    } as Response);

    await (strategyOptimizeTool.execute as any)(
      'test-id',
      {
        strategy_id: 1,
        symbol: '600519.SH',
        param_grid: { rsi_low: [30] },
        metric: 'win_rate',
        initial_capital: 2000000,
        max_combinations: 100,
      },
      undefined,
      undefined,
      {}
    );

    const callBody = JSON.parse(mockFetch.mock.calls[0]?.[1]?.body as string);
    expect(callBody.sortBy).toBe('win_rate');
    expect(callBody.initialCash).toBe(2000000);
    expect(callBody.maxCombinations).toBe(100);
  });

  it('should format output with top results', async () => {
    const mockResponse = {
      success: true,
      results: [
        {
          params: { rsi_low: 30, rsi_high: 70 },
          sharpeRatio: 2.15,
          totalReturn: 0.23,
          maxDrawdown: -0.08,
          winRate: 0.62,
          totalTrades: 50,
        },
        {
          params: { rsi_low: 25, rsi_high: 75 },
          sharpeRatio: 1.8,
          totalReturn: 0.18,
          maxDrawdown: -0.10,
          winRate: 0.58,
          totalTrades: 48,
        },
      ],
      totalCombinations: 4,
      successfulCombinations: 4,
    };

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const result = await (strategyOptimizeTool.execute as any)(
      'test-id',
      {
        strategy_id: 1,
        symbol: '600519.SH',
        param_grid: { rsi_low: [25, 30], rsi_high: [70, 75] },
      },
      undefined,
      undefined,
      {}
    );

    expect(result.content[0]).toHaveProperty('type', 'text');
    if (result.content[0].type === 'text') {
      const text = result.content[0].text;
      expect(text).toContain('最优参数');
      expect(text).toContain('23.00%');
      expect(text).toContain('-8.00%');
      expect(text).toContain('62.00%');
    }
  });
});
