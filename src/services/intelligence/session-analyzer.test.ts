import { describe, it, expect } from '@jest/globals';
import { parseSessionEvents } from './session-analyzer.js';

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
