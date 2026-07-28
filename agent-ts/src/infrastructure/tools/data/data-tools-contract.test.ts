/**
 * 数据工具契约测试（2026-07-28 数据链路修复）
 *
 * 验证三个修复后的工具按真实后端契约渲染：
 * - data_fetch_market_sentiment：up_count/down_count + degraded_dimensions
 * - data_fetch_north_flow：CCASS 季度持股估算语义
 * - opponent_behavior：degraded 时显式「数据不可用」，不再显示 +0.00亿
 */

import { describe, it, expect, beforeEach, jest } from '@jest/globals';

// ESM 模式必须用 unstable_mockModule + 动态 import（jest.mock 不提升）
jest.unstable_mockModule('../../adapters/quant/quant-v2-client.js', () => ({
  runQuantV2: jest.fn()
}));

const { runQuantV2 } = await import('../../adapters/quant/quant-v2-client.js');
const { dataFetchMarketSentimentTool } = await import('./fetch-market-sentiment-tool.js');
const { dataFetchNorthFlowTool } = await import('./fetch-north-flow-tool.js');
const { opponentBehaviorTool } = await import('../game/opponent-behavior-tool.js');

const mockRunQuantV2 = runQuantV2 as jest.MockedFunction<typeof runQuantV2>;

function textOf(result: any): string {
  return result.content.map((c: any) => c.text).join('\n');
}

describe('data_fetch_market_sentiment', () => {
  beforeEach(() => { jest.clearAllMocks(); });

  it('按真实契约渲染涨跌统计与降级警告', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      data: {
        sentiment_score: 62,
        sentiment_level: 'neutral_positive',
        fear_greed_index: 62,
        market_phase: 'recovery',
        recommendation: '市场偏乐观',
        degraded: true,
        degraded_dimensions: [{ dimension: 'new_high_low', reason: '数据不可用' }],
        indicators: {
          advance_decline: {
            data_date: '2026-07-27', up_count: 2800, down_count: 2100,
            flat_count: 300, ratio: 1.33, up_percentage: 53.8,
          },
          volume: { data_date: '2026-07-27', volume_ratio: 1.15, status: 'normal' },
          index_performance: {
            data_date: '2026-07-27', positive_count: 3,
            total_count: 5, avg_return_5d_pct: 0.4, market_trend: 'up',
          },
          volatility: { volatility: 1.2, level: 'normal' },
          new_high_low: { error: '数据不可用' },
        },
      },
      error: null,
    } as any);

    const result = await dataFetchMarketSentimentTool.execute('t', {} as any);
    const text = textOf(result);

    expect(text).toContain('2800');          // up_count 真实渲染
    expect(text).toContain('2100');          // down_count
    expect(text).toContain('2026-07-27');    // 数据日期
    expect(text).toContain('部分维度数据不可用'); // 降级警告必须展示
    expect(text).not.toContain('undefined');
    expect(text).not.toContain('NaN');
  });

  it('兼容后端 api_response 的 camelCase 键名（snakeize 转换）', async () => {
    // 后端 api_response 用 convert_keys_to_camel 序列化——真实响应是 camelCase
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      data: {
        sentimentScore: 58,
        sentimentLevel: 'neutral_positive',
        fearGreedIndex: 58,
        degraded: false,
        degradedDimensions: [],
        indicators: {
          advanceDecline: {
            dataDate: '2026-07-27', upCount: 2600, downCount: 2200,
            flatCount: 400, ratio: 1.18, upPercentage: 50.0,
          },
          volume: { dataDate: '2026-07-27', volumeRatio: 0.95, status: 'normal' },
        },
      },
      error: null,
    } as any);

    const result = await dataFetchMarketSentimentTool.execute('t', {} as any);
    const text = textOf(result);

    expect(text).toContain('2600');
    expect(text).toContain('2200');
    expect(text).not.toContain('undefined');
    expect(text).not.toContain('NaN');
  });
});

describe('data_fetch_north_flow', () => {
  beforeEach(() => { jest.clearAllMocks(); });

  it('按 CCASS 季度估算契约渲染，强调季度语义', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      data: {
        success: true,
        data: [{ trade_date: '2026-06-30', net_flow: 5.44e10, sh_net_flow: 3e10, sz_net_flow: 2.44e10 }],
        summary: {
          total_net_flow: 5.44e10,
          latest_date: '2026-06-30',
          prev_date: '2025-12-31',
          method: 'ccass_holdings_change',
          disclosure_frequency: 'quarterly',
          estimated: true,
          coverage: 0.85,
          top_inflows: [{ symbol: '300750', name: '宁德时代', delta_shares: 2.6e7, estimated_value: 3.74e10 }],
          top_outflows: [{ symbol: '603259', name: '药明康德', delta_shares: -1.3e7, estimated_value: -8.87e9 }],
        },
      },
      error: null,
    } as any);

    const result = await dataFetchNorthFlowTool.execute('t', {} as any);
    const text = textOf(result);

    expect(text).toContain('季度');            // 必须强调季度语义
    expect(text).toContain('+544.0 亿元');
    expect(text).toContain('宁德时代');
    expect(text).toContain('药明康德');
    expect(text).not.toContain('undefined');
  });
});

describe('opponent_behavior', () => {
  beforeEach(() => { jest.clearAllMocks(); });

  it('degraded 时显式展示数据不可用，不显示 +0.00亿', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      data: {
        retail: {
          behavior: 'unknown', net_flow: null, emotion_index: null,
          degraded: true, reason: 'stock_fund_flow 无数据',
          description: '资金流数据不可用', common_mistakes: [],
        },
        institution: {
          behavior: 'unknown', net_flow: null, target_sectors: [],
          position_change: 'unknown', degraded: true,
          reason: 'stock_fund_flow 无数据', description: '资金流数据不可用',
        },
        hot_money: { behavior: 'inactive', activity_level: 'low', estimated: true },
        market_phase: 'unknown',
        risk_appetite: 'unknown',
        opportunity_map: {},
        degraded: true,
      },
      error: null,
    } as any);

    const result = await opponentBehaviorTool.execute('t', {} as any);
    const text = textOf(result);

    expect(text).toContain('数据不可用');
    expect(text).not.toContain('+0.00亿');     // 旧 bug：恒显示 +0.00亿
  });

  it('有数据时正常渲染资金流向', async () => {
    mockRunQuantV2.mockResolvedValue({
      ok: true,
      data: {
        retail: {
          behavior: 'neutral', net_flow: -8.58e8, emotion_index: 50,
          description: '散户观望', common_mistakes: [],
        },
        institution: {
          behavior: 'distributing', net_flow: -5.3e10,
          target_sectors: ['电子', '电气'], position_change: 'decreasing',
          description: '机构出货',
        },
        hot_money: { behavior: 'inactive', activity_level: 'low', estimated: true },
        market_phase: 'consolidation',
        risk_appetite: 'medium',
        opportunity_map: {},
        degraded: false,
      },
      error: null,
    } as any);

    const result = await opponentBehaviorTool.execute('t', {} as any);
    const text = textOf(result);

    expect(text).toContain('-530.00亿元');
    expect(text).toContain('电子');
  });
});
