/**
 * Verify Judgments Tool - 测试文件
 *
 * agent 判断自校验：调 /api/market/heatmap，把信号/池操作/行业判断与验证窗实际涨跌对照，
 * 返回结论（✅/❌ + 统计 + 学习提示）而非数据堆。
 */
import { describe, it, expect, jest } from '@jest/globals';

const mockRunQuantV2 = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule('../../adapters/quant/quant-v2-client.js', () => ({
  runQuantV2: mockRunQuantV2,
}));

const { verifyJudgmentsTool } = await import('./verify-judgments-tool.js');

function heatmapPayload(overrides: any = {}) {
  return {
    ok: true,
    command: 'market.heatmap',
    data: {
      date: '2026-07-24',
      window: 5,
      actualEndDate: '2026-07-31',
      partial: false,
      scopeDegraded: false,
      excludedCount: 0,
      industries: [
        {
          name: '半导体', changePct: 4.2, agentStance: 'bullish',
          stocks: [
            {
              symbol: '688981', name: '中芯国际', changePct: 8.2, marketCap: 4.5e11,
              inScope: true,
              signals: [{ type: 'buy', date: '2026-07-23', strategy: 'v13' }],
            },
            {
              symbol: '002371', name: '北方华创', changePct: 6.7, marketCap: 2e11,
              inScope: true,
              poolEvents: [{ action: 'add', pool: '高质量池', date: '2026-07-22' }],
            },
            {
              symbol: '000858', name: '五粮液', changePct: -4.4, marketCap: 5e11,
              inScope: true,
              signals: [{ type: 'buy', date: '2026-07-22', strategy: 'v13' }],
            },
            { symbol: '300999', name: '池外股', changePct: 1.1, marketCap: 2e10, inScope: false },
          ],
        },
      ],
      ...overrides,
    },
    error: null,
  };
}

describe('verify_judgments tool', () => {
  it('should have correct metadata', () => {
    expect(verifyJudgmentsTool.name).toBe('verify_judgments');
    expect(verifyJudgmentsTool.description).toContain('校验');
  });

  it('should call market.heatmap with window param', async () => {
    const spy = mockRunQuantV2.mockResolvedValue(heatmapPayload());
    await verifyJudgmentsTool.execute('test', { window: 5 }, undefined, undefined, {} as any);
    expect(spy).toHaveBeenCalledWith('market.heatmap', expect.objectContaining({ window: 5 }));
  });

  it('should judge signals, pool events and industry stance with stats', async () => {
    mockRunQuantV2.mockResolvedValue(heatmapPayload());
    const result = await verifyJudgmentsTool.execute('test', { window: 5 }, undefined, undefined, {} as any);
    const text = (result.content[0] as any).text as string;

    // 区间头
    expect(text).toContain('2026-07-24');
    expect(text).toContain('2026-07-31');
    // 信号判断：中芯国际 买+涨=✅；五粮液 买+跌=❌
    expect(text).toMatch(/✅.*中芯国际/);
    expect(text).toMatch(/❌.*五粮液/);
    // 池操作：北方华创 调入+涨=✅
    expect(text).toMatch(/✅.*北方华创/);
    // 行业：半导体 看好+涨=✅
    expect(text).toMatch(/✅.*半导体/);
    // 统计：对 3 / 错 1
    expect(text).toContain('对 3');
    expect(text).toContain('错 1');
    // 池外股不参与判断
    expect(text).not.toContain('池外股');
  });

  it('should hint when nothing to verify', async () => {
    mockRunQuantV2.mockResolvedValue(heatmapPayload({
      industries: [{
        name: '医药', changePct: -1.0, agentStance: 'neutral',
        stocks: [{ symbol: '600276', name: '恒瑞医药', changePct: -1.0, marketCap: 3e11, inScope: true }],
      }],
    }));
    const result = await verifyJudgmentsTool.execute('test', {}, undefined, undefined, {} as any);
    const text = (result.content[0] as any).text as string;
    expect(text).toContain('无可校验判断');
  });

  it('should warn on partial window', async () => {
    mockRunQuantV2.mockResolvedValue(heatmapPayload({ partial: true }));
    const result = await verifyJudgmentsTool.execute('test', {}, undefined, undefined, {} as any);
    const text = (result.content[0] as any).text as string;
    expect(text).toContain('验证窗未满');
  });

  it('should return error content when backend fails', async () => {
    mockRunQuantV2.mockResolvedValue({ ok: false, error: 'window 必须是 (1, 5, 20) 之一' } as any);
    const result = await verifyJudgmentsTool.execute('test', { window: 7 }, undefined, undefined, {} as any);
    const text = (result.content[0] as any).text as string;
    expect(text).toContain('失败');
  });
});
