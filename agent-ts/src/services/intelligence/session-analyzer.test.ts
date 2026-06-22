import { describe, it, expect } from '@jest/globals';
import { parseSessionEvents, evaluateToolEfficiency } from './session-analyzer.js';
import type { DecisionChain } from '../../types/evolution.js';

describe('SessionAnalyzer - parseSessionEvents', () => {
  it('应该解析 session events 文件', () => {
    const events = [
      { ts: 1000, event: 'user_message', data: { content: '分析招商银行' } },
      { ts: 1001, event: 'tool_call', data: { tool: 'get_stock_realtime_price', args: { symbol: '600036' } } },
      { ts: 1002, event: 'tool_result', data: { result: { price: 45.2 } } },
      { ts: 1003, event: 'assistant_message', data: { content: '建议买入' } }
    ];

    const result = parseSessionEvents('20260511T02554_bd095f2b', events);

    expect(result.session_id).toBe('20260511T02554_bd095f2b');
    expect(result.user_query).toBe('分析招商银行');
    expect(result.tool_calls).toHaveLength(1);
    expect(result.tool_calls[0].tool_name).toBe('get_stock_realtime_price');
    expect(result.decision.action).toBe('buy');
  });

  it('应该处理多个工具调用', () => {
    const events = [
      { ts: 1000, event: 'user_message', data: { content: '分析紫金矿业' } },
      { ts: 1001, event: 'tool_call', data: { tool: 'get_stock_realtime_price', args: { symbol: '601899' } } },
      { ts: 1002, event: 'tool_call', data: { tool: 'calculate_technical_indicators', args: { symbol: '601899' } } },
      { ts: 1003, event: 'tool_call', data: { tool: 'get_financial_data', args: { symbol: '601899' } } },
      { ts: 1004, event: 'assistant_message', data: { content: '建议持有' } }
    ];

    const result = parseSessionEvents('test_session', events);

    expect(result.tool_calls).toHaveLength(3);
    expect(result.tool_calls.map(t => t.tool_name)).toEqual([
      'get_stock_realtime_price',
      'calculate_technical_indicators',
      'get_financial_data'
    ]);
  });
});

describe('SessionAnalyzer - evaluateToolEfficiency', () => {
  it('应该计算工具效能指标', () => {
    const sessions: DecisionChain[] = [
      {
        session_id: 's1',
        timestamp: '2026-05-10T10:00:00Z',
        user_query: '分析股票',
        tool_calls: [
          { tool_name: 'get_stock_realtime_price', arguments: {}, timestamp: '2026-05-10T10:00:00Z' },
          { tool_name: 'calculate_technical_indicators', arguments: {}, timestamp: '2026-05-10T10:00:01Z' }
        ],
        decision: { action: 'buy', symbol: '600036', reason: '买入' },
        resources: { tokens: 1000, cost: 0.01, duration_ms: 2000 }
      },
      {
        session_id: 's2',
        timestamp: '2026-05-11T10:00:00Z',
        user_query: '分析股票',
        tool_calls: [
          { tool_name: 'get_stock_realtime_price', arguments: {}, timestamp: '2026-05-11T10:00:00Z' }
        ],
        decision: { action: 'sell', symbol: '600036', reason: '卖出' },
        resources: { tokens: 800, cost: 0.008, duration_ms: 1500 }
      }
    ];

    const trades = [
      { session_id: 's1', symbol: '600036', return: 0.05 },  // 5% 收益
      { session_id: 's2', symbol: '600036', return: -0.02 }  // -2% 亏损
    ];

    const result = evaluateToolEfficiency(sessions, trades);

    expect(result).toHaveLength(2);

    const priceToolStats = result.find(t => t.tool_name === 'get_stock_realtime_price');
    expect(priceToolStats).toBeDefined();
    expect(priceToolStats!.call_count).toBe(2);
    expect(priceToolStats!.decisions_after_call).toBe(2);
    expect(priceToolStats!.win_rate).toBe(0.5);

    const techToolStats = result.find(t => t.tool_name === 'calculate_technical_indicators');
    expect(techToolStats).toBeDefined();
    expect(techToolStats!.call_count).toBe(1);
    expect(techToolStats!.win_rate).toBe(1.0);
  });

  it('应该计算 ROI', () => {
    const sessions: DecisionChain[] = [
      {
        session_id: 's1',
        timestamp: '2026-05-10T10:00:00Z',
        user_query: '分析',
        tool_calls: [
          { tool_name: 'get_financial_data', arguments: {}, timestamp: '2026-05-10T10:00:00Z' }
        ],
        decision: { action: 'buy', symbol: '600036', reason: '买入' },
        resources: { tokens: 2000, cost: 0.02, duration_ms: 3000 }
      }
    ];

    const trades = [
      { session_id: 's1', symbol: '600036', return: 0.10 }  // 10% 收益
    ];

    const result = evaluateToolEfficiency(sessions, trades);
    const toolStats = result[0];

    expect(toolStats.avg_return).toBe(0.10);
    expect(toolStats.cost_per_call).toBe(0.02);
    expect(toolStats.roi).toBeCloseTo(5.0, 1);  // 10% / 0.02 = 5.0
  });
});
