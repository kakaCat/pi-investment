/**
 * Chan Analyze Tool - 测试
 * 缠论分析工具：调 v2 POST /api/chan/analyze，返回结构化解读（走势/买卖点/历史胜率）。
 * 模式跟随 watch-manage-tool.test.ts（@jest/globals + unstable_mockModule）。
 */
import { beforeEach, describe, expect, it, jest } from "@jest/globals";

const mockRun = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule("../../adapters/quant/quant-v2-client.js", () => ({
  runQuantV2: mockRun,
}));

const { chanAnalyzeTool } = await import("./chan-analyze-tool.js");

beforeEach(() => { mockRun.mockReset(); });

function chanData(overrides: any = {}) {
  return {
    symbol: '600519.SH',
    trend_type: '上涨',
    bis: [{ direction: 'up', start_index: 1, end_index: 8, start_price: 1600, end_price: 1650, high: 1650, low: 1600, length: 8, price_change: 0.031 }],
    segments: [],
    zhongshus: [],
    buypoints: [
      { type: '1买', price: 1620.5, index: 100, date: '2026-08-03', confidence: 0.9, position_ratio: 1.0, reason: '下跌背驰',
        knowledge: { win_rate: 0.62, samples: 37, suggested_confidence: '中高' } },
    ],
    klines: [],
    ...overrides,
  };
}

describe('chan_analyze tool', () => {
  it('should have correct metadata', () => {
    expect(chanAnalyzeTool.name).toBe('chan_analyze');
    expect(chanAnalyzeTool.description).toContain('缠论');
  });

  it('should call chan.analyze with symbol and format result', async () => {
    mockRun.mockResolvedValue({ ok: true, command: 'chan.analyze', data: chanData() } as any);
    const result = await chanAnalyzeTool.execute('t1', { symbol: '600519.SH' });

    expect(mockRun).toHaveBeenCalledWith('chan.analyze', expect.objectContaining({ symbol: '600519.SH' }));
    const text = (result.content[0] as any).text as string;
    expect(text).toContain('上涨');
    expect(text).toContain('1买');
    expect(text).toContain('1620.5');
    expect(text).toContain('62%');       // knowledge 块历史胜率透传
    expect(text).toContain('37');
  });

  it('should work when knowledge is null (蒸馏未运行)', async () => {
    const data = chanData();
    data.buypoints[0].knowledge = null;
    mockRun.mockResolvedValue({ ok: true, command: 'chan.analyze', data } as any);
    const result = await chanAnalyzeTool.execute('t2', { symbol: '600519.SH' });
    const text = (result.content[0] as any).text as string;
    expect(text).toContain('1买');
    expect(text).not.toContain('62%');
  });

  it('should pass date range as camelCase body keys', async () => {
    mockRun.mockResolvedValue({ ok: true, command: 'chan.analyze', data: chanData() } as any);
    await chanAnalyzeTool.execute('t4', { symbol: '600519.SH', start_date: '2026-01-01', end_date: '2026-08-01' });
    expect(mockRun).toHaveBeenCalledWith('chan.analyze', {
      symbol: '600519.SH', startDate: '2026-01-01', endDate: '2026-08-01',
    });
  });

  it('should reject missing symbol', async () => {
    const result = await chanAnalyzeTool.execute('t3', {});
    expect((result.details as any)?.success).toBe(false);
  });
});
