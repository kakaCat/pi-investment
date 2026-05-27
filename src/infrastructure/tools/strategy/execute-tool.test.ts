/**
 * Strategy Execute Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';

const mockExecuteStrategy = jest.fn<(params: any) => Promise<any>>();

jest.unstable_mockModule('../../quant/quant-v2-client.js', () => ({
  executeStrategy: mockExecuteStrategy
}));

const { strategyExecuteTool } = await import('./execute-tool.js');

describe('strategyExecuteTool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should execute strategy successfully with full risk management', async () => {
    const mockSignal = {
      success: true,
      symbol: '600519.SH',
      name: '贵州茅台',
      strategy: 'VolatilityBreakout',
      action: 'buy' as const,
      confidence: 0.85,
      reason: '突破上阈值',
      risk_management: {
        stop_loss: {
          type: 'atr' as const,
          price: 1650.50,
          params: { atr_value: 25.30, atr_multiplier: 2.0 }
        },
        position_sizing: {
          method: 'kelly' as const,
          value: null,
          params: { win_rate: 0.55, profit_loss_ratio: 2.0, kelly_fraction: 0.25 }
        }
      },
      indicators: { atr: 25.30, rsi: 45.20 },
      timestamp: '2026-05-27T10:30:00'
    };

    mockExecuteStrategy.mockResolvedValue(mockSignal);

    const result = await (strategyExecuteTool.execute as any)('test-call-id', {
      symbol: '600519',
      strategy: 'VolatilityBreakout'
    });

    expect((result.content[0] as any).text).toContain('贵州茅台');
    expect((result.content[0] as any).text).toContain('买入');
    expect((result.content[0] as any).text).toContain('85.0%');
    expect((result.content[0] as any).text).toContain('止损价格: 1,650.50');
    expect((result.content[0] as any).text).toContain('Kelly准则');
    expect(result.details).toEqual(mockSignal);
  });

  it('should normalize symbol without suffix', async () => {
    mockExecuteStrategy.mockResolvedValue({
      success: true,
      symbol: '600519.SH',
      name: '贵州茅台',
      strategy: 'Turtle',
      action: 'hold' as const,
      confidence: 0.5,
      reason: '无信号',
      timestamp: '2026-05-27T10:30:00'
    });

    await (strategyExecuteTool.execute as any)('test-call-id', {
      symbol: '600519',
      strategy: 'Turtle'
    });

    expect(mockExecuteStrategy).toHaveBeenCalledWith({
      symbol: '600519.SH',
      strategy_name: 'Turtle',
      date: undefined
    });
  });

  it('should handle missing symbol parameter', async () => {
    const result = await (strategyExecuteTool.execute as any)('test-call-id', {
      strategy: 'Turtle'
    });

    expect((result.content[0] as any).text).toContain('错误：缺少必需参数 symbol');
  });

  it('should handle missing strategy parameter', async () => {
    const result = await (strategyExecuteTool.execute as any)('test-call-id', {
      symbol: '600519'
    });

    expect((result.content[0] as any).text).toContain('错误：缺少必需参数 strategy');
  });

  it('should handle API errors gracefully', async () => {
    mockExecuteStrategy.mockRejectedValue(
      new Error('K线数据不足')
    );

    const result = await (strategyExecuteTool.execute as any)('test-call-id', {
      symbol: '600519',
      strategy: 'Turtle'
    });

    expect((result.content[0] as any).text).toContain('策略执行失败');
    expect((result.content[0] as any).text).toContain('K线数据不足');
  });

  it('should support optional date parameter', async () => {
    mockExecuteStrategy.mockResolvedValue({
      success: true,
      symbol: '600519.SH',
      name: '贵州茅台',
      strategy: 'Momentum',
      action: 'sell' as const,
      confidence: 0.75,
      reason: '动量减弱',
      timestamp: '2026-01-15T10:30:00'
    });

    await (strategyExecuteTool.execute as any)('test-call-id', {
      symbol: '600519.SH',
      strategy: 'Momentum',
      date: '2026-01-15'
    });

    expect(mockExecuteStrategy).toHaveBeenCalledWith({
      symbol: '600519.SH',
      strategy_name: 'Momentum',
      date: '2026-01-15'
    });
  });
});
